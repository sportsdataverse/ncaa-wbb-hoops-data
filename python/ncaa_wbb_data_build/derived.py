"""Derived datasets -- the 5 non-family datasets.

Unlike the 6 DIRECT datasets (see ``reshapers.extract_family``), these are
not a straight extract of a parsed-JSON top-level key:

- ``team_ids``: the bundled stats.ncaa.org crosswalk from sdv-py
  (``sportsdataverse.wbb.wbb_ncaa_team_ids.ncaa_wbb_team_ids``), filtered to
  one season.
- ``schedule``: one row per game, built from each game's ``pbp`` rows
  (home/away/date/final score).
- ``rosters``: distinct ``(team, player)`` pairs per season. The parsed JSON
  has no roster family, and sdv-py's roster parser needs separately-captured
  roster HTML this tree doesn't hold -- so distinct players from
  ``player_box`` (which every game carries) is the only faithful season
  roster source available here. See :func:`rosters`.
- ``matchup_stints``: one row per constant-10-man floor segment, from pbp.
- ``team_rosters``: season rosters WITH stats.ncaa.org player ids, read from
  the raw checkout's roster-capture tree.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

_NAME_SPLIT = re.compile(r"[^a-z0-9']+")
_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _key_name(name: str) -> str:
    """Format-immune canonical form of one player name for hashing.

    The two lineup sources render the same player differently -- the box
    lineup keeps display form (``"Talton Jr, Derrick"`` / ``"B.J. Edwards"``)
    while pbp on-court columns carry the engine's ``"DERRICK.TALTON"`` /
    ``"BJ.EDWARDS"`` normalization, which DROPS suffixes and collapses
    initials. So: strip diacritics, casefold, split on non-alphanumerics,
    drop suffix tokens, then take the sorted-letter signature.
    """
    import unicodedata

    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    words = [w for w in _NAME_SPLIT.split(ascii_name.casefold()) if w]
    words = [w for w in words if w not in _NAME_SUFFIXES]
    # Sorted-letter signature: immune to word order, hyphen/space-collapsed
    # compound surnames (PORTERBROWN vs Porter-Brown), apostrophes (JEKEL vs
    # Je'Kel), and collapsed initials. Collision = exact-anagram teammates,
    # which at team-season scope is negligible.
    return "".join(sorted("".join(words).replace("'", "")))


def lineup_key(team: str | None, players: "list[str]") -> str | None:
    """Stable 16-hex id for one team's five-man unit.

    ``md5(team|p1|p2|...)`` over the SORTED player names, team-scoped so two
    programs fielding identical name-sets never collide. This is THE join key
    of the lineup index: the same function stamps ``lineups.lineup_key`` and
    ``matchup_stints.{home,away}_lineup_key``, so any aggregate built from
    either dataset can be joined back on it.
    """
    if not team or not players:
        return None
    # Normalize INSIDE the key so input order, case, whitespace, and even the
    # SOURCE's name format ("Last, First" vs "FIRST.LAST") can never mint a
    # phantom "new" lineup -- see _key_name.
    norm = sorted(_key_name(p) for p in players)
    src = " ".join(team.split()).casefold() + "|" + "|".join(norm)
    return hashlib.md5(src.encode("utf-8")).hexdigest()[:16]


_ON_COURT = [f"home_{i}" for i in range(1, 6)] + [f"away_{i}" for i in range(1, 6)]


def _matchup_stints_game(
    pbp: pl.DataFrame, contest_id: str, season: int
) -> pl.DataFrame | None:
    """One game's pbp -> matchup-stint segments (constant 10-man floor units).

    Segments are maximal runs of consecutive events where BOTH lineups (and
    the period) are unchanged. Scores partition exactly: a segment's points
    are the difference between its last running score and the previous
    segment's last running score.
    """
    need = {
        "period",
        "game_seconds",
        "home_score",
        "away_score",
        "home",
        "away",
        *_ON_COURT,
    }
    if not need.issubset(pbp.columns):
        return None
    df = pbp.drop_nulls(subset=_ON_COURT)
    if df.height == 0:
        return None
    df = df.with_columns(
        pl.concat_list([pl.col(f"home_{i}") for i in range(1, 6)])
        .list.sort()
        .alias("_hl"),
        pl.concat_list([pl.col(f"away_{i}") for i in range(1, 6)])
        .list.sort()
        .alias("_al"),
    ).with_columns(
        pl.col("_hl").list.join("|").alias("home_lineup"),
        pl.col("_al").list.join("|").alias("away_lineup"),
    )
    df = df.with_columns(
        (
            (pl.col("home_lineup") != pl.col("home_lineup").shift(1))
            | (pl.col("away_lineup") != pl.col("away_lineup").shift(1))
            | (pl.col("period") != pl.col("period").shift(1))
        )
        .fill_null(True)
        .cum_sum()
        .alias("_seg")
    )
    poss_col = (
        pl.col("poss_num").drop_nulls().n_unique().cast(pl.Int64)
        if "poss_num" in df.columns
        else pl.lit(0, dtype=pl.Int64)
    )
    seg = (
        df.group_by("_seg", maintain_order=True)
        .agg(
            pl.first("game_date")
            if "game_date" in df.columns
            else pl.lit(None, dtype=pl.Utf8).alias("game_date"),
            pl.first("home"),
            pl.first("away"),
            pl.first("period"),
            pl.first("game_seconds").alias("start_seconds"),
            pl.last("game_seconds").alias("end_seconds"),
            pl.last("home_score").alias("end_home_score"),
            pl.last("away_score").alias("end_away_score"),
            pl.first("home_lineup"),
            pl.first("away_lineup"),
            pl.first("_hl").alias("_hl"),
            pl.first("_al").alias("_al"),
            pl.len().cast(pl.Int64).alias("n_events"),
            poss_col.alias("n_possessions"),
        )
        .with_columns(
            pl.int_range(1, pl.len() + 1).alias("game_stint_num"),
            pl.col("end_home_score").shift(1, fill_value=0).alias("start_home_score"),
            pl.col("end_away_score").shift(1, fill_value=0).alias("start_away_score"),
        )
        .with_columns(
            (pl.col("end_home_score") - pl.col("start_home_score")).alias("home_pts"),
            (pl.col("end_away_score") - pl.col("start_away_score")).alias("away_pts"),
            (pl.col("end_seconds") - pl.col("start_seconds")).alias("duration_seconds"),
        )
    )
    # split the sorted lists into home_1..5 / away_1..5 positional columns
    seg = seg.with_columns(
        *[pl.col("_hl").list.get(i).alias(f"home_{i + 1}") for i in range(5)],
        *[pl.col("_al").list.get(i).alias(f"away_{i + 1}") for i in range(5)],
    ).drop("_hl", "_al", "_seg")
    seg = seg.with_columns(
        pl.struct("home", "home_lineup")
        .map_elements(
            lambda s: lineup_key(s["home"], s["home_lineup"].split("|")),
            return_dtype=pl.Utf8,
        )
        .alias("home_lineup_key"),
        pl.struct("away", "away_lineup")
        .map_elements(
            lambda s: lineup_key(s["away"], s["away_lineup"].split("|")),
            return_dtype=pl.Utf8,
        )
        .alias("away_lineup_key"),
    ).with_columns(
        (pl.col("home_lineup_key") + "_" + pl.col("away_lineup_key")).alias(
            "matchup_key"
        ),
        pl.lit(contest_id, dtype=pl.Utf8).alias("contest_id"),
        pl.lit(season, dtype=pl.Int64).alias("season"),
    )
    return seg


_TEAM_ROSTERS_SCHEMA: "dict[str, type]" = {
    "season": pl.Int64,
    "team_id": pl.Utf8,
    "team": pl.Utf8,
    "player_id": pl.Utf8,
    "player": pl.Utf8,
    "clean_name": pl.Utf8,
    "name": pl.Utf8,
    "jersey": pl.Utf8,
    "class": pl.Utf8,
    "position": pl.Utf8,
    "height": pl.Utf8,
    "ht_inches": pl.Int64,
    "hometown": pl.Utf8,
    "high_school": pl.Utf8,
    "gp": pl.Utf8,
    "gs": pl.Utf8,
}


def team_rosters(season: int, raw_root: "str | Path") -> pl.DataFrame:
    """Season rosters WITH stats.ncaa.org player ids, from the raw checkout.

    Reads the per-team JSONs the raw repo's ``ncaa_rosters.py`` stage captures
    from each team's ``teams/{id}/roster`` page (one row per player; the
    ``player_id`` comes from the row's ``/players/{id}`` link, and ``player``
    is the FIRST.LAST key that byte-matches pbp name normalization -- the id
    crosswalk the name-only ``rosters`` dataset can't provide). Requires a
    local sibling checkout; returns an empty typed frame when the tree is
    absent for *season*.
    """
    import json

    base = Path(raw_root) / "wbb" / "team_rosters" / str(season)
    rows: "list[dict]" = []
    if base.is_dir():
        for f in sorted(base.glob("*.json")):
            try:
                p = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("team_rosters: unreadable %s", f)
                continue
            for r in p.get("players") or []:
                rows.append(
                    {
                        "season": season,
                        "team_id": str(p.get("team_id")),
                        "team": p.get("team"),
                        **{
                            k: r.get(k)
                            for k in _TEAM_ROSTERS_SCHEMA
                            if k not in ("season", "team_id", "team")
                        },
                    }
                )
    if not rows:
        return pl.DataFrame(schema=_TEAM_ROSTERS_SCHEMA)
    return (
        pl.DataFrame(rows, schema=_TEAM_ROSTERS_SCHEMA, infer_schema_length=None)
        .sort("team", "name")
        .select(list(_TEAM_ROSTERS_SCHEMA))
    )


def matchup_stints(finals: list[dict], season: int) -> pl.DataFrame:
    """Season matchup-stint index: one row per constant-10-man floor segment.

    The finest lineup-level grain: every row is a (home five, away five)
    pairing over a contiguous span of events, with exact score/possession
    deltas. ``home_lineup_key``/``away_lineup_key`` join to
    ``lineups.lineup_key``; ``matchup_key`` indexes the pairing itself.
    Games with no on-court columns (the vs-non-NCAA one-team-page games)
    are skipped.
    """
    frames: list[pl.DataFrame] = []
    for final in finals:
        rows = final.get("pbp") or []
        if not rows:
            continue
        try:
            game = _matchup_stints_game(
                pl.DataFrame(rows, infer_schema_length=None),
                str(final["contest_id"]),
                season,
            )
        except Exception as e:  # one bad game must not abort the season
            logger.warning(
                "matchup_stints: game %s failed: %s", final.get("contest_id"), e
            )
            continue
        if game is not None and game.height:
            frames.append(game)
    if not frames:
        return pl.DataFrame(schema={"contest_id": pl.Utf8, "season": pl.Int64})
    out = pl.concat(frames, how="diagonal_relaxed").sort("contest_id", "game_stint_num")
    front = [
        "contest_id",
        "season",
        "game_date",
        "home",
        "away",
        "game_stint_num",
        "period",
        "start_seconds",
        "end_seconds",
        "duration_seconds",
        "matchup_key",
        "home_lineup_key",
        "away_lineup_key",
        "home_lineup",
        "away_lineup",
    ]
    return out.select(
        [c for c in front if c in out.columns]
        + [c for c in out.columns if c not in front]
    )


def team_ids(season: int) -> pl.DataFrame:
    """Stats.ncaa.org team-id crosswalk for one season.

    ``season`` is the ending year (2026 -> the "2025-26" season row), and the
    output ``season`` column is that same Int64 ending-year -- consistent
    with every other dataset (so e.g. ``pbp.join(team_ids(2025), on="season")``
    actually matches). The crosswalk's own ``"YYYY-YY"`` string label is only
    used internally to filter; it's a bijection with the ending year, so
    replacing it loses no information.

    Note: the bundled WBB crosswalk only covers the 2009-10..2024-25
    seasons (no 2025-26+ row yet), so ``team_ids(2026)`` returns an empty
    frame -- expected, not a bug. Callers of the season build should not
    assume every requested season has crosswalk rows.
    """
    from sportsdataverse.wbb.wbb_ncaa_team_ids import ncaa_wbb_team_ids

    season_str = f"{season - 1}-{str(season)[-2:]}"
    df = ncaa_wbb_team_ids()
    return df.filter(pl.col("season") == season_str).with_columns(
        pl.col("id").cast(pl.Utf8),
        pl.lit(season, dtype=pl.Int64).alias("season"),
    )


def schedule(finals: list[dict], season: int) -> pl.DataFrame:
    """One row per game: contest_id, date, home/away, final score.

    Built from each game's ``pbp`` rows (the parsed JSON has no dedicated
    schedule family). A game with an empty ``pbp`` list is skipped -- a
    headerless game must not abort the whole season build.
    """
    rows = []
    for final in finals:
        pbp = final.get("pbp") or []
        if not pbp:
            logger.warning(
                "skipping schedule row for %s: empty pbp", final.get("contest_id")
            )
            continue
        home_score = max((r.get("home_score") or 0) for r in pbp)
        away_score = max((r.get("away_score") or 0) for r in pbp)
        rows.append(
            {
                "contest_id": str(final["contest_id"]),
                "game_date": pbp[0]["game_date"],
                "home": pbp[0]["home"],
                "away": pbp[0]["away"],
                "home_score": home_score,
                "away_score": away_score,
                "season": season,
            }
        )
    schema = {
        "contest_id": pl.Utf8,
        "game_date": pl.Utf8,
        "home": pl.Utf8,
        "away": pl.Utf8,
        "home_score": pl.Int64,
        "away_score": pl.Int64,
        "season": pl.Int64,
    }
    df = pl.DataFrame(rows, schema=schema) if rows else pl.DataFrame(schema=schema)
    return df.sort("contest_id")


def rosters(finals: list[dict], season: int) -> pl.DataFrame:
    """Distinct ``(team, player)`` rows for one season, with a games-played count.

    Source decision: the parsed JSON has no roster family, and sdv-py's
    roster parser needs separately-captured roster HTML that this tree
    doesn't hold. Distinct players from ``player_box`` -- present on every
    game -- is the only faithful season-roster source available here.
    """
    frames = [
        pl.DataFrame(final["player_box"], infer_schema_length=None).select(
            "team", "player", "game_id"
        )
        for final in finals
        if final.get("player_box")
    ]
    if not frames:
        return pl.DataFrame(
            schema={
                "season": pl.Int64,
                "team": pl.Utf8,
                "player": pl.Utf8,
                "games": pl.Int64,
            }
        )
    combined = pl.concat(frames, how="diagonal_relaxed")
    return (
        combined.group_by("team", "player")
        # n_unique() returns UInt32; cast to Int64 so the populated path matches
        # the empty-fallback schema above (stable season parquet dtype).
        .agg(pl.col("game_id").n_unique().cast(pl.Int64).alias("games"))
        .with_columns(pl.lit(season, dtype=pl.Int64).alias("season"))
        .select("season", "team", "player", "games")
        .sort("team", "player")
    )
