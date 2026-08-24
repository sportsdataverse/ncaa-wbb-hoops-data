"""Augment the Path A RAPM output and publish it as a release dataset.

Stage 3 of the RAPM chain (``ops/build_rapm.py`` is stages 1-2)::

    build_rapm.py        -> per-season RAPM, keyed on team + a DISPLAY NAME
    augment (this file)  -> + season, team_id, player_id, person_id
    publish (this file)  -> ncaa_{lg}_rapm_within_team release assets

**The estimand is WITHIN-TEAM.** This apportions one team's performance across
that team's own players from its lineup splits -- NOT the league-wide form that
regresses every lineup in the league jointly. The tag name says so on purpose;
``ncaa_{lg}_rapm`` is left free for the league-wide (Path B) dataset.

**The join is the hard part.** The driver writes ``player_code`` as a display
name ("Wright-Forde, Dian"); rosters write FIRST.MIDDLE.LAST uppercase, with
whitespace as dots and hyphens collapsed. Measured on real 2024 MBB data:

    naive comma split                        93.04%
    + suffix / quoted-nickname strip         98.07%
    + whitespace -> dots (multi-token names) 99.08%
    + uniqueness-gated surname fallback      99.83% (full corpus)

Ambiguity is NULLED, never guessed -- both when a surname matches more than one
unclaimed roster row, and when a fallback would hand one roster player to two
RAPM rows in the same team-season. A missing id is recoverable; a wrong
attribution silently is not.

DRY RUN BY DEFAULT. ``sportsdataverse_save`` uploads to a LIVE release tag with
no confirmation of its own, and a careless local run has overwritten live tags
before. Pass ``--publish`` to actually upload.

    python ops/publish_rapm.py --league mbb --rapm-dir dev/ncaa_rapm/out
    python ops/publish_rapm.py --league mbb --rapm-dir dev/ncaa_rapm/out --publish
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import polars as pl

SUFFIX = re.compile(r"(?i)^(jr|sr|ii|iii|iv|v)\.?$")
NICKNAME = re.compile(r'["“”].*?["“”]')
DEFAULT_REPO = "sportsdataverse/sportsdataverse-data"
#: Hard release floor. --min-match-rate may RAISE this, never lower it.
RELEASE_FLOOR = 0.99


def _clean_token(tok: str) -> str:
    tok = unicodedata.normalize("NFKD", tok)
    tok = "".join(c for c in tok if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z]", "", tok).upper()


def display_name_to_roster_key(name: str | None) -> str:
    """``'Ballisager Webb, Jermaine'`` -> ``'JERMAINE.BALLISAGER.WEBB'``."""
    if not name:
        return ""
    name = NICKNAME.sub(" ", name)
    parts = [p.strip() for p in name.split(",")]
    parts = [p for p in parts if p and not SUFFIX.fullmatch(p)]
    if len(parts) < 2:
        return ""
    first, last = parts[-1], " ".join(parts[:-1])
    toks = [_clean_token(t) for t in (first.split() + last.split())]
    toks = [t for t in toks if t and not SUFFIX.fullmatch(t)]
    return ".".join(toks)


def _surname(key: str) -> str:
    return key.rsplit(".", 1)[-1] if key else ""


def augment_season(
    rapm: pl.DataFrame, rosters: pl.DataFrame, season: int
) -> pl.DataFrame:
    """Attach season / team_id / player_id to one season's RAPM frame."""
    rapm = rapm.with_columns(
        pl.lit(season, dtype=pl.Int32).alias("season"),
        pl.col("player_code")
        .map_elements(display_name_to_roster_key, return_dtype=pl.Utf8)
        .alias("player_key"),
    )
    ros = (
        rosters.select(
            pl.col("team").cast(pl.Utf8),
            pl.col("player")
            .cast(pl.Utf8)
            .str.to_uppercase()
            .str.strip_chars_end(".")
            .alias("player_key"),
            pl.col("player_id").cast(pl.Utf8),
            pl.col("team_id").cast(pl.Utf8),
        )
        .filter(pl.col("player_key") != "")
        .unique()
    )
    # A normalized key resolving to MORE THAN ONE player_id is two people
    # sharing a rendering. `unique(keep="first")` would hand the RAPM row an
    # ARBITRARY one of them -- the same wrong-attribution class this pipeline
    # exists to avoid, and the reason `build_player_xwalk` drops these too.
    # Exclude the key entirely BEFORE the join so the row stays unresolved.
    unambiguous = (
        ros.group_by(["team", "player_key"])
        .agg(pl.col("player_id").n_unique().alias("_n"))
        .filter(pl.col("_n") == 1)
        .select(["team", "player_key"])
    )
    ros = ros.join(unambiguous, on=["team", "player_key"], how="inner").unique(
        subset=["team", "player_key"], keep="first"
    )
    out = rapm.join(ros, on=["team", "player_key"], how="left")

    matched = out.filter(pl.col("player_id").is_not_null())
    claimed = set(zip(matched["team"], matched["player_key"]))
    by_surname: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for t, k, pid, tid in zip(
        ros["team"], ros["player_key"], ros["player_id"], ros["team_id"]
    ):
        if (t, k) in claimed:
            continue
        by_surname.setdefault((t, _surname(k)), []).append((pid, tid))

    pids: list[str | None] = []
    tids: list[str | None] = []
    for t, k, pid, tid in zip(
        out["team"], out["player_key"], out["player_id"], out["team_id"]
    ):
        if pid is not None:
            pids.append(pid)
            tids.append(tid)
            continue
        cands = by_surname.get((t, _surname(k)), [])
        if len(cands) == 1:  # uniqueness gate -- 0 or >1 stays unresolved
            pids.append(cands[0][0])
            tids.append(cands[0][1])
        else:
            pids.append(None)
            tids.append(None)
    out = out.with_columns(
        pl.Series("player_id", pids, dtype=pl.Utf8),
        pl.Series("team_id", tids, dtype=pl.Utf8),
    )

    # One roster player must not be handed to two RAPM rows in a team-season.
    dup = (
        out.filter(pl.col("player_id").is_not_null())
        .group_by(["season", "team", "player_id"])
        .len()
        .filter(pl.col("len") > 1)
        .select(["season", "team", "player_id"])
    )
    if dup.height:
        out = (
            out.join(
                dup.with_columns(pl.lit(True).alias("_d")),
                on=["season", "team", "player_id"],
                how="left",
            )
            .with_columns(
                pl.when(pl.col("_d").fill_null(False))
                .then(None)
                .otherwise(pl.col("player_id"))
                .alias("player_id"),
                pl.when(pl.col("_d").fill_null(False))
                .then(None)
                .otherwise(pl.col("team_id"))
                .alias("team_id"),
            )
            .drop("_d")
        )
    return out.drop("player_key")


def check_run_manifest(parquet: Path, frame_rows: int) -> "str | None":
    """Validate a season's completion manifest. Returns a reason to REFUSE, or None.

    The filename suffix proves a run was DECLARED partial. It cannot prove a run
    that claimed to be full actually finished -- an interrupted or truncated
    full run writes the canonical name with fewer teams and is otherwise
    indistinguishable from a complete season. The manifest closes that gap.
    """
    mf = parquet.with_suffix(".manifest.json")
    if not mf.exists():
        return f"no completion manifest ({mf.name}); re-run ops/build_rapm.py for this season"
    try:
        m = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"unreadable manifest {mf.name}: {exc}"
    if m.get("partial"):
        return f"manifest marks this a PARTIAL run (team={m.get('team')!r} limit={m.get('limit')!r})"
    avail, done = m.get("games_available"), m.get("games_processed")
    if isinstance(avail, int) and isinstance(done, int) and avail and done < avail:
        return f"manifest shows a TRUNCATED run: {done:,}/{avail:,} games processed"
    if isinstance(m.get("rows"), int) and m["rows"] != frame_rows:
        return f"manifest rows={m['rows']:,} but the parquet holds {frame_rows:,} -- file changed after the run"
    return None

def fetch_rosters(league: str, dest: Path, seasons: "set[int] | None" = None) -> Path:
    """Ensure EVERY required roster season is present, not merely one.

    A cache holding a single season used to satisfy the old `any(...)` check;
    every other season then had no roster, was skipped, and the match rate was
    computed over the surviving subset -- so a partial cache could publish an
    incomplete release that still cleared the floor.
    """
    dest.mkdir(parents=True, exist_ok=True)
    have = {
        int(f.stem.rsplit("_", 1)[1])
        for f in dest.glob(f"ncaa_{league}_team_rosters_*.parquet")
        if f.stem.rsplit("_", 1)[1].isdigit()
    }
    missing = (seasons - have) if seasons else (set() if have else {0})
    if missing:
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                f"ncaa_{league}_team_rosters",
                "--repo",
                DEFAULT_REPO,
                "--pattern",
                f"ncaa_{league}_team_rosters_*.parquet",
                "--dir",
                str(dest),
                "--clobber",
            ],
            check=True,
            capture_output=True,
        )
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=["mbb", "wbb"], required=True)
    ap.add_argument("--rapm-dir", required=True)
    ap.add_argument("--roster-dir", default=None)
    ap.add_argument("--min-match-rate", type=float, default=RELEASE_FLOOR)
    ap.add_argument(
        "--name-changes",
        default=None,
        help="Path to ncaa_{lg}_name_changes.parquet (default: search the canonical "
             "<repo>/<league>/name_changes/parquet dir, then --rapm-dir).",
    )
    ap.add_argument(
        "--publish", action="store_true", help="actually upload (default: dry run)"
    )
    ap.add_argument(
        "--allow-unmanifested",
        action="store_true",
        help="Publish seasons that have NO completion manifest. For the "
        "pre-manifest corpus only -- it WAIVES the completeness proof, it does "
        "not supply one. Never silences a manifest that says PARTIAL or "
        "TRUNCATED.",
    )
    a = ap.parse_args()
    # `rate < float("nan")` is False, so a NaN floor would wave through a zero
    # match rate. Reject any non-finite or out-of-range floor outright.
    if not math.isfinite(a.min_match_rate) or not (RELEASE_FLOOR <= a.min_match_rate <= 1.0):
        print(
            f"ERROR: --min-match-rate must be a finite fraction in "
            f"[{RELEASE_FLOOR}, 1]; got {a.min_match_rate!r}. The release floor "
            f"cannot be lowered -- it is the publish gate, not a preference.",
            file=sys.stderr,
        )
        return 2

    tag = f"ncaa_{a.league}_rapm_within_team"
    roster_root = (
        Path(a.roster_dir)
        if a.roster_dir
        else Path(tempfile.gettempdir()) / f"rapm_rosters_{a.league}"
    )
    # Only the canonical per-season files are publishable inputs; partial runs
    # carry a __team-/__limit- suffix and must not be mistaken for a season.
    required = {
        int(m.group(1))
        for f in Path(a.rapm_dir).glob(f"ncaa_{a.league}_rapm_*.parquet")
        if (m := re.search(r"rapm_(\d{4})\.parquet$", f.name))
    }
    if not required:
        print(f"ERROR: no canonical season files in {a.rapm_dir}", file=sys.stderr)
        return 2
    rosters_dir = fetch_rosters(a.league, roster_root, required)

    from sportsdataverse.mbb.mbb_ncaa_rapm_input import build_person_keys

    all_ros = pl.concat(
        [
            pl.read_parquet(f)
            for f in sorted(rosters_dir.glob(f"ncaa_{a.league}_team_rosters_*.parquet"))
        ],
        how="diagonal_relaxed",
    )
    # build_name_changes.py writes to <repo>/<league>/name_changes/parquet, NOT
    # to the RAPM output dir -- looking only in --rapm-dir silently built the
    # person keys with no crosswalk, so a renamed player became two people.
    nc_candidates = (
        [Path(a.name_changes)]
        if a.name_changes
        else [
            Path(__file__).resolve().parents[1] / a.league / "name_changes" / "parquet"
            / f"ncaa_{a.league}_name_changes.parquet",
            Path(a.rapm_dir) / f"ncaa_{a.league}_name_changes.parquet",
        ]
    )
    nc = next((c for c in nc_candidates if c.exists()), nc_candidates[-1])
    if not nc.exists():
        # Without the crosswalk a renamed player becomes TWO person_ids, and
        # the id match-rate floor cannot see it -- every row still matches a
        # roster entry, so the release looks healthy while cross-season
        # identity is silently wrong. A dry run may proceed; publishing may not.
        msg = (
            f"no name-change crosswalk found (looked in "
            f"{[str(c) for c in nc_candidates]}); person_id would treat a "
            f"renamed player as two people"
        )
        if a.publish:
            print(f"ERROR: {msg}. Refusing to publish. Pass --name-changes.", file=sys.stderr)
            return 2
        print(f"WARNING: {msg}.", file=sys.stderr)
    keys = build_person_keys(
        all_ros, name_changes=pl.read_parquet(nc) if nc.exists() else None
    )
    bridge = keys.select(
        pl.col("season").cast(pl.Int32),
        pl.col("team").cast(pl.Utf8),
        pl.col("player_id").cast(pl.Utf8),
        pl.col("person_id").cast(pl.Utf8),
    ).unique(subset=["season", "team", "player_id"], keep="first")

    tot = 0
    hit = 0
    frames: list[tuple[int, pl.DataFrame]] = []
    for f in sorted(Path(a.rapm_dir).glob(f"ncaa_{a.league}_rapm_*.parquet")):
        m = re.search(r"rapm_(\d{4})\.parquet$", f.name)
        if not m:
            continue
        season = int(m.group(1))
        rp = rosters_dir / f"ncaa_{a.league}_team_rosters_{season}.parquet"
        if not rp.exists():
            print(f"  {season}: NO ROSTER -> skipped")
            continue
        aug = augment_season(pl.read_parquet(f), pl.read_parquet(rp), season)
        assert aug.schema["player_id"] == bridge.schema["player_id"], (
            "player_id dtype disagreement"
        )
        aug = aug.join(bridge, on=["season", "team", "player_id"], how="left")
        reason = check_run_manifest(f, pl.read_parquet(f).height)
        # The escape hatch covers ONLY a missing manifest (the pre-manifest
        # corpus). A manifest that exists and says PARTIAL or TRUNCATED is
        # positive evidence of incompleteness and is never waivable.
        if reason and a.allow_unmanifested and reason.startswith("no completion manifest"):
            print(f"  {season}: WARNING -- unmanifested, publishing anyway (--allow-unmanifested)", file=sys.stderr)
            reason = None
        if reason:
            if a.publish:
                print(f"ERROR: {season}: {reason}. Refusing to publish.", file=sys.stderr)
                return 2
            print(f"  {season}: WOULD REFUSE -- {reason}", file=sys.stderr)
        n = aug.height
        h = int(aug["player_id"].is_not_null().sum())
        tot += n
        hit += h
        frames.append((season, aug))
        pct = (h / n) if n else 0.0
        print(f"  {season}: rows={n:,} id-matched={h:,} ({pct:.2%})")

    rate = hit / tot if tot else 0.0
    print(
        f"\n{a.league}: rows={tot:,} matched={hit:,} rate={rate:.4%} floor={a.min_match_rate:.2%}"
    )
    if rate < a.min_match_rate:
        print("FAIL: below match-rate floor -- refusing to publish")
        return 1

    if not a.publish:
        print(f"\nDRY RUN -- would publish {len(frames)} seasons to tag '{tag}'")
        print("Re-run with --publish to upload.")
        return 0

    from sportsdataverse.release import sportsdataverse_save

    for season, df in frames:
        sportsdataverse_save(
            df,
            f"{tag}_{season}",
            tag,
            tag,
            f"ops/publish_rapm.py --league {a.league}",
            file_types=("rds", "csv.gz", "parquet"),
            repo=DEFAULT_REPO,
        )
        print(f"  published {tag}_{season}")
    print(f"\npublished {len(frames)} seasons to {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
