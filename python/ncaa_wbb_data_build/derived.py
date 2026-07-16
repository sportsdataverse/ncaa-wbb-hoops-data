"""Derived datasets -- the 3 non-family datasets: schedule, rosters, team_ids.

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
"""

from __future__ import annotations

import logging

import polars as pl

logger = logging.getLogger(__name__)


def team_ids(season: int) -> pl.DataFrame:
    """Stats.ncaa.org team-id crosswalk for one season.

    ``season`` is the ending year (2026 -> the "2025-26" season row).

    Note: the bundled WBB crosswalk only covers the 2009-10..2024-25
    seasons (no 2025-26+ row yet), so ``team_ids(2026)`` returns an empty
    frame -- expected, not a bug. Callers of the season build should not
    assume every requested season has crosswalk rows.
    """
    from sportsdataverse.wbb.wbb_ncaa_team_ids import ncaa_wbb_team_ids

    season_str = f"{season - 1}-{str(season)[-2:]}"
    df = ncaa_wbb_team_ids()
    return df.filter(pl.col("season") == season_str).with_columns(pl.col("id").cast(pl.Utf8))


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
            logger.warning("skipping schedule row for %s: empty pbp", final.get("contest_id"))
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
        pl.DataFrame(final["player_box"]).select("team", "player", "game_id")
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
