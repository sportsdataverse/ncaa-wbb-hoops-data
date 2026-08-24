"""Build LEAGUE-WIDE NCAA RAPM seasons (Path B) -- gated, manifested.

Stages 1-2 of the league-RAPM chain (``ops/publish_rapm_league.py`` is
stage 3)::

    possessions + team_rosters + name_changes (this repo's published trees)
      -> mbb_ncaa_rapm_input   (xwalk -> alias expansion -> slot resolution)
      -> mbb_ncaa_rapm_league  (matchup stints -> sparse joint O/D ridge)
      -> team_aggregate -> GATES -> parquet + completion manifest

**The estimand is LEAGUE-WIDE** -- every D-I player on one common scale per
season (tag ``ncaa_{lg}_rapm``). The published ``ncaa_{lg}_rapm_within_team``
is a DIFFERENT estimand (relative to teammates); the ``estimand`` column
stamped into every row keeps a detached frame distinguishable.

## Gates (publish-blocking; a failed season writes NOTHING)

Floors are frozen from the observed values of the full 2026-08-24 validation
sweep (34 league-seasons, non_di=drop, lambda=1000) and are NEVER lowered to
make a season pass -- debug the season instead. ``--min-spearman`` may RAISE
the floor only.

1. usable-possession fraction >= 0.65
   (observed 2011+ minima: mbb 0.7414, wbb 0.7609. 2010 sits at 0.046/0.284
   -- the pbp substitution corpus barely exists that year -- and is excluded
   by THIS mechanism, not by a season list.)
2. intercept inside the era band: mbb [95, 112] (observed 99.24..107.97),
   wbb [83, 98] (observed 87.31..92.80); hca inside [1.0, 4.0]
   (observed 1.84..3.07; COVID 2021 lows ~1.8-2.0). Spearman is scale-blind
   -- these catch a per-poss-vs-per-100 factor bug it cannot (the CFB
   ratings-scale incident class).
3. Torvik team-aggregate external gate: join the season's team_aggregate to
   ``ops/oracle/ncaa_{lg}_torvik.parquet`` on the stats.ncaa.org name;
   REQUIRE >= 250 joined teams and Spearman(team_net, adjem) >= floor
   (mbb 0.93, observed min 0.9434; wbb 0.89, observed min 0.9039 = the 2021
   COVID season). A NaN rho or an undersized/missing/absent-season oracle is
   a FAILURE, never a skip.
4. Ungated allowlist: Torvik has NO women's ratings before 2021, so WBB
   2011-2020 are published WITHOUT the external gate -- explicitly listed in
   ``UNGATED_SEASONS``, still subject to gates 1-2, and marked
   ``external_gate="ungated_no_oracle"`` in the manifest. Every other
   oracle-less season fails.

Usage::

    uv run python ops/build_rapm_league.py --league mbb --season 2024
    uv run python ops/build_rapm_league.py --league mbb --all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import polars as pl
from sportsdataverse.mbb.mbb_ncaa_rapm_input import (
    build_person_keys,
    build_player_xwalk,
    expand_xwalk_aliases,
    observed_pairs,
    resolve_possessions,
)
from sportsdataverse.mbb.mbb_ncaa_rapm_league import (
    DEFAULT_RIDGE_LAMBDA,
    aggregate_stints,
    solve_rapm_league,
    team_aggregate,
)

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA = {
    "mbb": ("hoopR-dev/ncaa-mbb-hoops-data", "mbb", "ncaa_mbb"),
    "wbb": ("wehoop-dev/ncaa-wbb-hoops-data", "wbb", "ncaa_wbb"),
}
_HERE = Path(__file__).resolve().parent

SEASONS = list(range(2011, 2027))

#: Frozen gate floors -- observed-value provenance in the module docstring.
#: NEVER lowered to make a season pass.
SPEARMAN_FLOOR = {"mbb": 0.93, "wbb": 0.89}
USABLE_FRACTION_FLOOR = 0.65
INTERCEPT_BAND = {"mbb": (95.0, 112.0), "wbb": (83.0, 98.0)}
HCA_BAND = (1.0, 4.0)
MIN_ORACLE_TEAMS = 250

#: Seasons published WITHOUT the external Torvik gate, because the oracle
#: does not exist there (Torvik women's coverage starts 2021). Internal
#: gates (usable fraction, level bands) still apply. Nothing else may skip
#: the external gate.
UNGATED_SEASONS = {"mbb": set(), "wbb": set(range(2011, 2021))}


def _data_file(league: str, dataset: str, season: "int | None" = None) -> Path:
    repo, lg, stem = _DATA[league]
    name = (
        f"{stem}_{dataset}_{season}.parquet" if season else f"{stem}_{dataset}.parquet"
    )
    return _ROOT / repo / lg / dataset / "parquet" / name


def _fail(season: int, reason: str) -> None:
    print(f"  {season}: GATE FAIL -- {reason}", flush=True)


def torvik_rho(
    league: str, season: int, teams: pl.DataFrame
) -> "tuple[int, float] | str":
    """Return (joined_teams, spearman) or a failure reason string."""
    from scipy.stats import spearmanr

    path = _HERE / "oracle" / f"ncaa_{league}_torvik.parquet"
    if not path.is_file():
        return f"oracle parquet missing: {path}"
    oracle = pl.read_parquet(path).filter(pl.col("season") == str(season))
    if oracle.height == 0:
        return f"oracle has no season {season}"
    oracle = oracle.select(pl.col("team").cast(pl.Utf8), "adjem")
    assert teams.schema["team"] == oracle.schema["team"], "team join dtype mismatch"
    j = teams.join(oracle, on="team", how="inner")
    if j.height < MIN_ORACLE_TEAMS:
        return f"oracle join too small: {j.height} < {MIN_ORACLE_TEAMS}"
    rho = float(spearmanr(j["team_net"].to_numpy(), j["adjem"].to_numpy()).statistic)
    if math.isnan(rho):
        return "spearman is NaN"
    return (j.height, rho)


def person_bridge(league: str) -> pl.DataFrame:
    """(season, player_id) -> person_id across every local roster season."""
    frames = []
    for season in range(2010, 2027):
        f = _data_file(league, "team_rosters", season)
        if f.is_file():
            frames.append(pl.read_parquet(f))
    rosters = pl.concat(frames, how="diagonal_relaxed")
    nc_f = _data_file(league, "name_changes")
    changes = pl.read_parquet(nc_f) if nc_f.is_file() else None
    keys = build_person_keys(rosters, name_changes=changes)
    return keys.select(
        pl.col("season").cast(pl.Utf8),
        pl.col("player_id").cast(pl.Utf8),
        pl.col("person_id").cast(pl.Utf8),
    ).unique(subset=["season", "player_id"])


def run_season(
    league: str,
    season: int,
    out_dir: Path,
    bridge: pl.DataFrame,
    min_spearman: float,
) -> bool:
    poss_f = _data_file(league, "possessions", season)
    ros_f = _data_file(league, "team_rosters", season)
    if not poss_f.is_file() or not ros_f.is_file():
        _fail(
            season,
            f"missing input {poss_f.name if not poss_f.is_file() else ros_f.name}",
        )
        return False
    possessions = pl.read_parquet(poss_f)
    rosters = pl.read_parquet(ros_f)
    nc_f = _data_file(league, "name_changes")
    name_changes = None
    if nc_f.is_file():
        name_changes = pl.read_parquet(nc_f).filter(
            pl.col("season").cast(pl.Utf8) == str(season)
        )

    xwalk = build_player_xwalk(rosters)
    xwalk = expand_xwalk_aliases(
        xwalk, observed_pairs(possessions), name_changes=name_changes
    )
    resolved = resolve_possessions(possessions, xwalk, non_di="drop")
    stints = aggregate_stints(resolved)
    usable = int(stints["n_poss"].sum() or 0)
    frac = usable / possessions.height if possessions.height else 0.0

    # Gate 1: usable fraction. This -- not a season list -- is what excludes
    # 2010's near-empty substitution corpus.
    if frac < USABLE_FRACTION_FLOOR:
        _fail(season, f"usable fraction {frac:.4f} < {USABLE_FRACTION_FLOOR}")
        return False

    players, info = solve_rapm_league(stints, ridge_lambda=DEFAULT_RIDGE_LAMBDA)

    # Gate 2: level bands (Spearman is scale-blind).
    lo, hi = INTERCEPT_BAND[league]
    if not (lo <= info["intercept"] <= hi):
        _fail(season, f"intercept {info['intercept']:.2f} outside [{lo}, {hi}]")
        return False
    if not (HCA_BAND[0] <= info["hca"] <= HCA_BAND[1]):
        _fail(season, f"hca {info['hca']:.3f} outside {HCA_BAND}")
        return False

    # Gate 3/4: external oracle, or the explicit ungated allowlist.
    teams = team_aggregate(stints, players)
    if season in UNGATED_SEASONS[league]:
        external_gate = "ungated_no_oracle"
        rho_n, rho = None, None
    else:
        got = torvik_rho(league, season, teams)
        if isinstance(got, str):
            _fail(season, got)
            return False
        rho_n, rho = got
        if rho < min_spearman:
            _fail(season, f"torvik spearman {rho:.4f} < floor {min_spearman}")
            return False
        external_gate = "passed"

    # Augment: identity + provenance columns.
    ros = rosters.select(
        pl.col("player_id").cast(pl.Utf8),
        pl.col("team").cast(pl.Utf8),
        pl.col("player").cast(pl.Utf8),
    ).unique(subset=["player_id"], keep="first")
    assert players.schema["player_id"] == ros.schema["player_id"], (
        "player_id dtype mismatch"
    )
    out = (
        players.join(ros, on="player_id", how="left")
        .join(
            bridge.filter(pl.col("season") == str(season)).drop("season"),
            on="player_id",
            how="left",
        )
        .with_columns(
            pl.lit(season, dtype=pl.Int32).alias("season"),
            pl.lit("league").alias("estimand"),
        )
        .select(
            "season",
            "player_id",
            "person_id",
            "player",
            "team",
            "orapm",
            "drapm",
            "rapm_net",
            "off_poss",
            "def_poss",
            "estimand",
        )
        .sort("rapm_net", descending=True)
    )
    n_games = int(possessions["contest_id"].n_unique())

    stem = _DATA[league][2]
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"{stem}_rapm_league_{season}.parquet"
    # Remove any prior manifest BEFORE the parquet changes -- an interruption
    # between the two writes must leave NO manifest (-> refused), never a
    # stale manifest beside a new parquet.
    mf_path = f.with_suffix(".manifest.json")
    mf_path.unlink(missing_ok=True)
    out.write_parquet(f)
    manifest = {
        "league": league,
        "season": season,
        "parquet": f.name,
        "partial": False,
        "games_available": n_games,
        "games_processed": n_games,
        "games_failed": 0,
        "rows": out.height,
        "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
        # League-RAPM gate record (validated again by the publisher):
        "estimand": "league",
        "non_di": "drop",
        "ridge_lambda": float(DEFAULT_RIDGE_LAMBDA),
        "usable_fraction": frac,
        "intercept": info["intercept"],
        "hca": info["hca"],
        "lsqr_istop": info["lsqr_istop"],
        "external_gate": external_gate,
        "torvik_teams": rho_n,
        "torvik_spearman": rho,
        "gates_passed": True,
    }
    mf_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    g = f"rho={rho:.4f} (n={rho_n})" if rho is not None else external_gate
    print(
        f"  {season}: usable={frac:.2%} players={out.height} mu={info['intercept']:.2f} "
        f"hca={info['hca']:.3f} person_id null={out['person_id'].null_count()} | {g} | wrote {f.name}",
        flush=True,
    )
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=["mbb", "wbb"], required=True)
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default=str(_HERE / "out_league"))
    ap.add_argument(
        "--min-spearman",
        type=float,
        default=None,
        help="RAISE the external-gate floor (never lower; default = frozen floor).",
    )
    a = ap.parse_args()
    floor = SPEARMAN_FLOOR[a.league]
    if a.min_spearman is not None:
        # A NaN would compare False against every rho and wave everything
        # through; an attempt to lower the floor is refused outright.
        if not math.isfinite(a.min_spearman) or not (floor <= a.min_spearman <= 1.0):
            print(
                f"ERROR: --min-spearman must be finite in [{floor}, 1] -- the "
                "frozen floor can be raised, never lowered.",
                file=sys.stderr,
            )
            return 2
        floor = a.min_spearman
    seasons = SEASONS if a.all else [a.season]
    if seasons == [None]:
        ap.error("pass --season or --all")
    print(
        f"{a.league} league-wide RAPM lambda={DEFAULT_RIDGE_LAMBDA} floor={floor}",
        flush=True,
    )
    bridge = person_bridge(a.league)
    ok = [run_season(a.league, s, Path(a.out), bridge, floor) for s in seasons]
    print(f"{sum(ok)}/{len(ok)} seasons passed all gates", flush=True)
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
