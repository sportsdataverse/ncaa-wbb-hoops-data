"""Publish LEAGUE-WIDE NCAA RAPM seasons to the ``ncaa_{lg}_rapm`` tag.

Stage 3 of the league-RAPM chain (``ops/build_rapm_league.py`` is stages
1-2). The build already ran the gates and wrote a completion manifest per
season; this publisher RE-VALIDATES deny-by-default -- a manifest that
merely parses is not evidence -- and refuses any season whose gate record
is missing, failed, or inconsistent with the parquet on disk.

**The estimand is LEAGUE-WIDE** (one common D-I scale per season). The
``ncaa_{lg}_rapm_within_team`` tag is a different estimand; the two must
never be cross-joined. Every published row carries ``estimand="league"``.

DRY RUN BY DEFAULT. ``sportsdataverse_save`` uploads to a LIVE release tag
with no confirmation of its own. It also never CREATES a release -- a new
tag must be ``gh release create``d first or every upload fails.

Refusal conditions per season: missing/invalid completion manifest
(``check_run_manifest``); ``gates_passed`` not literally ``True``;
``estimand`` not ``"league"`` in both manifest and every parquet row;
``external_gate`` neither ``"passed"`` (with a finite ``torvik_spearman``
at/above the frozen floor and ``torvik_teams >= 250``) nor
``"ungated_no_oracle"`` (allowed ONLY for the WBB 2011-2020 allowlist --
Torvik has no women's ratings before 2021); ``player_id`` not Utf8. Across
the publish set, the median Spearman of externally-gated seasons must be
>= 0.95 (observed medians: mbb 0.9653, wbb 0.9823) when 3+ gated seasons
are present.

Usage::

    uv run python ops/publish_rapm_league.py --league mbb            # dry run
    uv run python ops/publish_rapm_league.py --league mbb --publish
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_rapm_league import (  # noqa: E402
    MIN_ORACLE_TEAMS,
    SPEARMAN_FLOOR,
    UNGATED_SEASONS,
)
from publish_rapm import check_run_manifest  # noqa: E402

MEDIAN_FLOOR = 0.95
_STEM = {"mbb": "ncaa_mbb", "wbb": "ncaa_wbb"}


def check_league_gate_record(mf: dict, league: str, season: int) -> "str | None":
    """Validate the league-gate fields of a manifest. Returns a refusal reason."""
    if mf.get("gates_passed") is not True:
        return "manifest does not record gates_passed=true"
    if mf.get("estimand") != "league":
        return f"manifest estimand is {mf.get('estimand')!r}, expected 'league'"
    ext = mf.get("external_gate")
    if ext == "passed":
        rho = mf.get("torvik_spearman")
        n = mf.get("torvik_teams")
        if not isinstance(rho, float) or not math.isfinite(rho):
            return f"external_gate='passed' but torvik_spearman={rho!r}"
        if rho < SPEARMAN_FLOOR[league]:
            return f"torvik_spearman {rho:.4f} below the frozen floor {SPEARMAN_FLOOR[league]}"
        if not isinstance(n, int) or isinstance(n, bool) or n < MIN_ORACLE_TEAMS:
            return f"torvik_teams={n!r} below {MIN_ORACLE_TEAMS}"
        return None
    if ext == "ungated_no_oracle":
        if season not in UNGATED_SEASONS[league]:
            return (
                f"season {season} claims ungated_no_oracle but is not on the allowlist"
            )
        return None
    return f"unrecognized external_gate {ext!r}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=["mbb", "wbb"], required=True)
    ap.add_argument(
        "--rapm-dir", default=str(Path(__file__).resolve().parent / "out_league")
    )
    ap.add_argument(
        "--publish", action="store_true", help="actually upload (default: dry run)"
    )
    a = ap.parse_args()

    stem = _STEM[a.league]
    tag = f"ncaa_{a.league}_rapm"
    rapm_dir = Path(a.rapm_dir)
    seasons = sorted(
        int(m.group(1))
        for f in rapm_dir.glob(f"{stem}_rapm_league_*.parquet")
        if (m := re.search(r"rapm_league_(\d{4})\.parquet$", f.name))
    )
    if not seasons:
        print(
            f"ERROR: no {stem}_rapm_league_*.parquet under {rapm_dir}", file=sys.stderr
        )
        return 2

    import json

    frames: "list[tuple[int, pl.DataFrame]]" = []
    gated_rhos: "list[float]" = []
    for season in seasons:
        f = rapm_dir / f"{stem}_rapm_league_{season}.parquet"
        df = pl.read_parquet(f)
        reason = check_run_manifest(f, df.height, league=a.league, season=season)
        if reason is None:
            mf = json.loads(f.with_suffix(".manifest.json").read_text(encoding="utf-8"))
            reason = check_league_gate_record(mf, a.league, season)
        if reason is None and df.schema["player_id"] != pl.Utf8:
            reason = f"player_id dtype {df.schema['player_id']} != Utf8"
        if reason is None and not (df["estimand"] == "league").all():
            reason = "parquet rows are not all estimand='league'"
        if reason is not None:
            print(f"  {season}: REFUSED -- {reason}")
            return 1
        if mf["external_gate"] == "passed":
            gated_rhos.append(mf["torvik_spearman"])
        frames.append((season, df))
        print(
            f"  {season}: rows={df.height:,} {mf['external_gate']}"
            + (f" rho={mf['torvik_spearman']:.4f}" if mf["torvik_spearman"] else "")
        )

    if len(gated_rhos) >= 3:
        med = sorted(gated_rhos)[len(gated_rhos) // 2]
        if med < MEDIAN_FLOOR:
            print(f"FAIL: median gated spearman {med:.4f} < {MEDIAN_FLOOR}")
            return 1
        print(f"median gated spearman {med:.4f} (floor {MEDIAN_FLOOR})")

    if not a.publish:
        print(f"\nDRY RUN -- would publish {len(frames)} seasons to tag '{tag}'")
        print("Re-run with --publish to upload. NOTE: a NEW tag must be")
        print(f"  gh release create {tag} --repo sportsdataverse/sportsdataverse-data")
        print("d first -- sportsdataverse_save uploads but never creates a release.")
        return 0

    from sportsdataverse.release import DEFAULT_REPO, sportsdataverse_save

    for season, df in frames:
        sportsdataverse_save(
            df,
            f"{tag}_{season}",
            tag,
            tag,
            f"ops/publish_rapm_league.py --league {a.league}",
            file_types=("rds", "csv.gz", "parquet"),
            repo=DEFAULT_REPO,
        )
        print(f"  published {tag}_{season}")
    print(f"\npublished {len(frames)} seasons to {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
