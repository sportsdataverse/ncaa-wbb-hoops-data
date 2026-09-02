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
5. Standard-error sanity (2026-09-01). sdv-py ``solve_rapm_league`` returns
   the ridge-POSTERIOR standard errors ``orapm_se`` / ``drapm_se`` /
   ``rapm_net_se`` = ``sqrt(sigma2 * diag((X'WX + lambda I)^-1))`` (net with
   the O/D covariance), published here as additive columns, plus the
   sampling (sandwich) SEs ``sqrt(diag(sigma2 * (M - lambda M^2)))`` used
   ONLY by this gate -- ``sigma2 * (M - lambda M^2)`` is the sampling
   COVARIANCE matrix; the SEs are the square roots of its diagonal. Floors frozen from the 2026-09-01 sweep (16 seasons per league,
   ``dev``-born survey, values in the module constants):
   a. ``sigma2`` inside the era band -- mbb [11000, 15000] (observed
      12562..13332), wbb [10000, 14000] (observed 11634..12408). It is the
      per-100 residual variance = 1e4 x the per-possession points variance,
      so it is the SE-machinery scale-bug catcher.
   b. Spearman(possessions, rapm_net_se) <= -0.80 (observed mbb
      -0.965..-0.898, wbb -0.950..-0.872): the SE must fall with playing time.
   c. median rapm_net_se of the top possession decile < the bottom decile's
      (observed ratio 0.788..0.819). Strict decile monotonicity is NOT required and
      NOT observed: the top deciles flatten at a collinearity floor (a
      starter who never sits is confounded with his team's total).
   d. Split-half refit (odd vs even ``contest_id``; ``split_half_se_check``):
      the other half's estimate lies within 2*sqrt(se_A^2 + se_B^2) for
      >= 0.95 of players under the POSTERIOR SE (observed >= 0.9995 -- a
      credible interval over-covers a refit by construction, so this is a
      one-sided guard against SEs that shrank) AND inside [0.92, 0.98] for
      each of orapm / drapm / rapm_net under the SAMPLING SE (observed mbb
      0.9465..0.9601, wbb 0.9397..0.9563 against the 0.954 nominal -- the
      two-sided calibration of sigma2 and the inverse). The POSTERIOR SE is
      ~2.5x conservative (split-half z-sd ~0.38, not 1.0), so 5d's posterior
      leg can never be read as nominal calibration.

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
    possession_deciles,
    solve_rapm_league,
    split_half_se_check,
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

#: Gate 5 (standard errors) -- frozen from the 2026-09-01 sweep, provenance in
#: the module docstring. NEVER loosened to make a season pass.
SIGMA2_BAND = {"mbb": (11000.0, 15000.0), "wbb": (10000.0, 14000.0)}
SE_SPEARMAN_CEILING = -0.80
SE_POSTERIOR_COVERAGE_FLOOR = 0.95
SE_SAMPLING_COVERAGE_BAND = (0.92, 0.98)


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
    # Drop any prior manifest BEFORE the first gate can return: a gate failure
    # (or an interruption) must leave NO manifest, so the publisher refuses the
    # season. Otherwise a manifest from an earlier PASSING run outlives the new
    # failure and republishes stale numbers beside a stale parquet.
    stem = _DATA[league][2]
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"{stem}_rapm_league_{season}.parquet"
    mf_path = f.with_suffix(".manifest.json")
    mf_path.unlink(missing_ok=True)
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

    # Gate 5: the standard errors must behave like uncertainty (docstring item
    # 5). Every comparison is written `not (ok)` so a NaN FAILS.
    from scipy.stats import spearmanr

    lo, hi = SIGMA2_BAND[league]
    if not (lo <= info["sigma2"] <= hi):
        _fail(season, f"sigma2 {info['sigma2']:.1f} outside [{lo}, {hi}]")
        return False
    p2 = players.with_columns((pl.col("off_poss") + pl.col("def_poss")).alias("poss"))
    se_rho = float(spearmanr(p2["poss"].to_numpy(), p2["rapm_net_se"].to_numpy()).statistic)
    if not (se_rho <= SE_SPEARMAN_CEILING):
        _fail(season, f"Spearman(poss, rapm_net_se) {se_rho:.4f} > {SE_SPEARMAN_CEILING}")
        return False
    dec = possession_deciles(players)["median_rapm_net_se"]
    se_bottom, se_top = float(dec[0]), float(dec[-1])
    if not (se_top < se_bottom):
        _fail(season, f"top-decile median SE {se_top:.3f} >= bottom-decile {se_bottom:.3f}")
        return False
    _pp, se_check = split_half_se_check(resolved, ridge_lambda=DEFAULT_RIDGE_LAMBDA)
    if not (se_check["coverage_rapm_net"] >= SE_POSTERIOR_COVERAGE_FLOOR):
        _fail(
            season,
            f"posterior-SE split-half coverage {se_check['coverage_rapm_net']:.4f} "
            f"< {SE_POSTERIOR_COVERAGE_FLOOR}",
        )
        return False
    for c in ("orapm", "drapm", "rapm_net"):
        v = se_check[f"coverage_sampling_{c}"]
        if not (SE_SAMPLING_COVERAGE_BAND[0] <= v <= SE_SAMPLING_COVERAGE_BAND[1]):
            _fail(season, f"sampling-SE split-half coverage ({c}) {v:.4f} outside {SE_SAMPLING_COVERAGE_BAND}")
            return False

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
            # additive (2026-09-01): posterior standard errors
            "orapm_se",
            "drapm_se",
            "rapm_net_se",
        )
        .sort("rapm_net", descending=True)
    )
    n_games = int(possessions["contest_id"].n_unique())

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
        # Gate 5 record (standard errors):
        "sigma2": info["sigma2"],
        "df_eff": info["df_eff"],
        "hca_se": info["hca_se"],
        "solve_max_abs_dev": info["solve_max_abs_dev"],
        "se_spearman_poss": se_rho,
        "se_median_bottom_decile": se_bottom,
        "se_median_top_decile": se_top,
        "se_split_games": [se_check["n_games_a"], se_check["n_games_b"]],
        "se_split_players": se_check["n_players"],
        "se_coverage_posterior_net": se_check["coverage_rapm_net"],
        "se_coverage_sampling": {c: se_check[f"coverage_sampling_{c}"] for c in ("orapm", "drapm", "rapm_net")},
        "se_zsd_sampling_net": se_check["z_sd_sampling_rapm_net"],
        "gates_passed": True,
    }
    mf_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    g = f"rho={rho:.4f} (n={rho_n})" if rho is not None else external_gate
    print(
        f"  {season}: usable={frac:.2%} players={out.height} mu={info['intercept']:.2f} "
        f"hca={info['hca']:.3f} person_id null={out['person_id'].null_count()} | {g} | "
        f"se: sigma2={info['sigma2']:.0f} rho={se_rho:.3f} cov_post={se_check['coverage_rapm_net']:.4f} "
        f"cov_samp_net={se_check['coverage_sampling_rapm_net']:.4f} | wrote {f.name}",
        flush=True,
    )
    return True


def write_card(league: str, out_dir: Path) -> Path:
    """Evaluation card = the per-season gate record of the last full ``--all`` run.

    Read by ``docs/models/rapm.qmd``; written only when EVERY season passed,
    so a partial sweep never overwrites the frozen record.
    """
    from datetime import datetime, timezone

    stem = _DATA[league][2]
    seasons = []
    # Iterate SEASONS, never glob: a stale or hand-made manifest left in out_dir
    # would otherwise be written into the card as if it were part of this sweep.
    # A missing manifest is a failure, not a skip -- the card claims a FULL run.
    for season in SEASONS:
        mf_path = out_dir / f"{stem}_rapm_league_{season}.manifest.json"
        if not mf_path.exists():
            raise FileNotFoundError(
                f"evaluation card needs a manifest for every season in SEASONS; {mf_path.name} is missing. "
                "Re-run the full --all sweep; the card is the record of one complete run."
            )
        mf = json.loads(mf_path.read_text(encoding="utf-8"))
        rho = mf["torvik_spearman"]
        seasons.append(
            {
                "season": mf["season"],
                "usable": round(100.0 * mf["usable_fraction"], 2),
                "players": mf["rows"],
                "mu": round(mf["intercept"], 2),
                "hca": round(mf["hca"], 3),
                "rho": None if rho is None else round(rho, 4),
                "n": mf["torvik_teams"],
                "sigma2": round(mf["sigma2"], 1),
                "se_spearman_poss": round(mf["se_spearman_poss"], 4),
                "se_median_bottom_decile": round(mf["se_median_bottom_decile"], 3),
                "se_median_top_decile": round(mf["se_median_top_decile"], 3),
                "se_cov_posterior": round(mf["se_coverage_posterior_net"], 4),
                "se_cov_sampling_orapm": round(mf["se_coverage_sampling"]["orapm"], 4),
                "se_cov_sampling_drapm": round(mf["se_coverage_sampling"]["drapm"], 4),
                "se_cov_sampling_net": round(mf["se_coverage_sampling"]["rapm_net"], 4),
                "se_zsd_sampling_net": round(mf["se_zsd_sampling_net"], 4),
            }
        )
    card = {
        "model": f"{stem}_rapm (league-wide, Path B)",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sweep": f"local --all run of python/{stem}_model_01_rapm_league.py",
        "lambda": float(DEFAULT_RIDGE_LAMBDA),
        "se": (
            "posterior sqrt(sigma2 * diag((X'WX + lambda I)^-1)) published; "
            "sampling sqrt(diag(sigma2 * (M - lambda M^2))) drives the split-half gate"
        ),
        "seasons": seasons,
    }
    path = _HERE.parent / "docs" / "models" / f"{stem}_rapm_card.json"
    path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    return path


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
    if a.all and all(ok):
        print(f"evaluation card -> {write_card(a.league, Path(a.out))}", flush=True)
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
