"""Build LEAGUE-WIDE NCAA RAPM seasons (Path B) -- gated, manifested.

Stages 1-2 of the league-RAPM chain (``ops/publish_rapm_league.py`` is
stage 3)::

    possessions + team_rosters + name_changes (this repo's published trees)
      -> mbb_ncaa_rapm_input   (xwalk -> alias expansion -> slot resolution)
      -> mbb_ncaa_rapm_league  (matchup stints -> sparse joint O/D ridge)
      -> team_aggregate -> GATES -> parquet + completion manifest

and, for a season that qualifies for the pooled estimator, between the resolve
and the stints::

      -> rapm_person.to_person (per-season player_id -> cross-season person_id)
      -> stack_seasons (seasons t-2..t, weight decay ** (t - s))
      -> ... ridge ... -> season_slice (back to season t's players and exposure)

**The default estimator is the decayed-weight 3-season pool** (2026-09-02),
for the leagues in :data:`POOLED_LEAGUES`. It was measured against the flat
single-season ridge on ten held-out seasons per league before being switched
on: out-of-sample game-margin MAE 8.8849 -> 8.7900 (mbb) and 9.7711 -> 9.4912
(wbb), better in 10/10 seasons, pooled game-cluster bootstrap 95% CIs
excluding zero; harness ``ops/experiments/rapm_stabilization.py``.

Two things it deliberately does NOT do, both because a frozen publish gate says
so rather than because the work was left undone:

* **The SPM prior is not applied.** It won every point-estimate criterion and it
  FAILS gate 5(d) below -- ``solve_rapm_league`` treats the prior mean as a
  fixed constant, so the published interval omits the prior's own sampling
  variability and comes out ~35% too narrow. Measured per lever by
  ``ops/experiments/rapm_se_calibration.py``.
* **WBB does not pool.** Its pooled fit fails gate 5(b) on 2021 and 2024; see
  :data:`POOLED_LEAGUES` for the numbers and for the two ways it could be made
  to pass, both of which are refused.

A season whose 3-season window is incomplete (mbb 2011 and 2012 -- 2010 fails
gate 1) falls back to ``flat``, through the pre-2026-09-02 code path, so its
published output is unchanged rather than merely equivalent.

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
      so it is the SE-machinery scale-bug catcher. **The band is keyed by
      (league, ESTIMATOR)** (2026-09-02) and each pooled band is derived from
      its own 14-season sweep by the same rule that produced the flat bands --
      see :data:`SIGMA2_BAND`, which carries the observations that set each
      edge. No band was widened: the pooled bands come out equal to the flat
      ones because sdv-py PR #441 divides ``sigma2`` by
      ``sum(fit_weight) - df_eff`` instead of the row count, which is what
      keeps it the per-possession residual variance under a decayed weight
      instead of that variance times ``mean(decay)``.
   b. Spearman(possessions, rapm_net_se) <= -0.80 (observed flat mbb
      -0.965..-0.898, wbb -0.950..-0.872): the SE must fall with playing time.
      Under the pool the correlation weakens, because a player's SE is driven
      by his THREE-season exposure while ``off_poss`` / ``def_poss`` report the
      season's: mbb pooled -0.911..-0.861 still clears it, wbb pooled
      -0.851..-0.795 does NOT, which is why WBB is not in
      :data:`POOLED_LEAGUES`. The ceiling is unchanged.
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
      Under a non-flat estimator the refit must BE that estimator
      (``split_half_se_check(refit=...)``) and every pooled season must be split
      by the same parity, or the halves share possessions and the coverage is
      inflated by construction. This is the gate the SPM prior fails.

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
    season_slice,
    solve_rapm_league,
    split_half_se_check,
    stack_seasons,
    team_aggregate,
)

# ops/ is the script directory, but this module is also driven through
# runpy.run_path from python/ncaa_{lg}_model_01_rapm_league.py, where it is not
# on sys.path. Insert it so the sibling ops modules import either way.
sys.path.insert(0, str(Path(__file__).resolve().parent))

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

#: The person bridge must cover essentially every on-floor slot, or the pooled
#: design is silently merging or dropping people and the failure surfaces only
#: as a wrong rating. Observed on MBB and WBB 2011-2026: 1.000.
PERSON_BRIDGE_FLOOR = 0.999

#: The ten on-floor slots ``resolve_possessions`` emits.
SLOT_IDS = [f"{side}_{i}_id" for side in ("home", "away") for i in range(1, 6)]

#: Seasons published WITHOUT the external Torvik gate, because the oracle
#: does not exist there (Torvik women's coverage starts 2021). Internal
#: gates (usable fraction, level bands) still apply. Nothing else may skip
#: the external gate.
UNGATED_SEASONS = {"mbb": set(), "wbb": set(range(2011, 2021))}

#: Default estimator (2026-09-02): the decayed-weight 3-season pool, measured
#: against the flat single-season ridge over ten held-out seasons per league
#: before being switched on (see ``ops/experiments/rapm_stabilization.py`` and
#: the report it points at). The box-score-plus-minus prior is NOT applied --
#: it fails gate 5(d); see :data:`ESTIMATORS` and the module docstring.
#: Hyperparameters were FROZEN on development seasons 2014-2015 and are not
#: re-tuned here: the two leagues chose different values on the same grid.
MULTI_YEAR_WINDOW = 3  # seasons t-2 .. t
DECAY = {"mbb": 0.5, "wbb": 0.75}

#: A season publishes under ``pooled`` only when its league is in
#: :data:`POOLED_LEAGUES`, the FULL window is available, and every pooled season
#: clears gate 1 on its own. Otherwise it falls back to ``flat`` -- the previous
#: estimator, under its previous band, through the previous code path, so a flat
#: season's output is UNCHANGED rather than merely equivalent (only the pooled
#: path re-keys to ``person_id``). The pool is never partially applied: a
#: two-season pool is a third quantity that would need a third band from a sweep
#: of its own.
ESTIMATORS = ("flat", "pooled")

#: Leagues whose full-window seasons publish POOLED (2026-09-02).
#:
#: **WBB is deliberately absent.** Its pooled fit FAILS gate 5(b) -- the frozen
#: ceiling Spearman(possessions, rapm_net_se) <= -0.80 -- on 2021 (-0.7947) and
#: 2024 (-0.7953), with 2020 / 2025 / 2026 at -0.804 / -0.810 / -0.806. The
#: whole pooled range is -0.7947..-0.8507 against a flat range of
#: -0.872..-0.950, so this is not a one-season fluke: at WBB's frozen decay of
#: 0.75 a player's standard error is driven mostly by his THREE-season exposure
#: while the published ``off_poss`` / ``def_poss`` are the season's, and the
#: correlation the gate measures genuinely weakens.
#:
#: Two responses would let WBB through and BOTH are refused here:
#: lowering the ceiling to fit the new observations is exactly the widening the
#: rules forbid, and re-tuning WBB's decay to MBB's 0.5 is re-tuning a
#: hyperparameter frozen on the development seasons in order to pass a gate.
#: Re-pairing the gate (correlating the SE against the POOLED exposure it is
#: actually a function of) is arguably the estimator-consistent test, but it
#: cannot be distinguished from changing the test until it passes on the
#: evidence available, so it is written down rather than done. MBB is unaffected
#: -- its pooled Spearman is -0.8611..-0.9108, clear of the ceiling.
#:
#: Those WBB numbers stay RE-DERIVABLE. A recorded measurement that no committed
#: command reproduces is exactly how the SE-calibration script drifted, so the
#: survey-only override is written down; it writes nothing and publishes
#: nothing::
#:
#:     python -c "import sys; sys.path.insert(0, 'ops'); #:       import build_rapm_league as bl; bl.POOLED_LEAGUES = {'mbb', 'wbb'}; #:       sys.argv = ['x', '--league', 'wbb', '--all', '--survey', 'out.json']; #:       sys.exit(bl.main())"
#:
#: Verified against the merged engine (sdv-py 6bb3e29d1): 14 pooled seasons,
#: sigma2 11,742.7 (2013) .. 12,400.3 (2026), Spearman -0.8507..-0.7947, gate
#: 5(b) failing on exactly 2021 and 2024.
POOLED_LEAGUES = {"mbb"}

#: Gate 5 (standard errors) -- frozen from observed sweeps, provenance in the
#: module docstring. NEVER loosened to make a season pass.
#:
#: **Keyed by (league, estimator)**, because a pooled fit is a different fit and
#: gets its own band from its own sweep rather than borrowing or widening
#: another's. The derivation rule is the one that produced the 2026-09-01 flat
#: bands, and it reproduces BOTH of them exactly from their own observed
#: extremes: take +/-12.5% of the observed min and max and round outward to the
#: nearest 1000 (mbb flat 12562..13332 -> 10992 / 14999 -> [11000, 15000];
#: wbb flat 11634..12408 -> 10180 / 13959 -> [10000, 14000]).
#:
#: Applied to the 14 pooled seasons of the 2026-09-02 sweep
#: (``--all --survey``, every gate computed, none of them 5(a)):
#:
#:   mbb pooled  12646.5 (2014) .. 13361.0 (2026)  ->  [11000, 15000]
#:   wbb pooled  11742.7 (2013) .. 12400.3 (2026)  ->  [10000, 14000]
#:
#: Each pooled band comes out EQUAL to its league's flat band -- derived
#: independently, not inherited. That is the expected result once ``sigma2`` is
#: divided by ``sum(fit_weight) - df_eff`` rather than the row count
#: (sdv-py PR #441): the weighted residual sum and its degrees of freedom then
#: deflate together, so the statistic is the per-possession residual variance
#: under either estimator instead of that variance times ``mean(decay)``. Before
#: that fix the same pooled MBB seasons measured ~7,730 -- a 41% drop with no
#: statistical content, which is what a band widened to admit it would have
#: enshrined.
SIGMA2_BAND = {
    ("mbb", "flat"): (11000.0, 15000.0),
    ("wbb", "flat"): (10000.0, 14000.0),
    ("mbb", "pooled"): (11000.0, 15000.0),
    ("wbb", "pooled"): (10000.0, 14000.0),
}
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
        pl.col("season").cast(pl.Int64),
        pl.col("player_id").cast(pl.Utf8),
        pl.col("person_id").cast(pl.Utf8),
    ).unique(subset=["season", "player_id"])


def to_person(
    resolved: pl.DataFrame, bridge: pl.DataFrame, season: int
) -> pl.DataFrame:
    """Replace each on-floor slot's ``player_id`` with its cross-season ``person_id``.

    A multi-season design is only pooling if the same human is the same COLUMN in
    every season. Applied ONLY on the pooled path -- a flat season has no
    cross-season column to share, and re-keying it would change published rows
    for nothing.

    Raises:
        RuntimeError: bridge coverage below :data:`PERSON_BRIDGE_FLOOR`, or a
            ``contest_id`` that is not integer-like.
    """
    key = bridge.filter(pl.col("season") == season).select("player_id", "person_id")
    assert key.schema["player_id"] == pl.Utf8, "bridge player_id must be Utf8"
    out = resolved.select("contest_id", "home", "away", "poss_team", "pts", *SLOT_IDS)
    for slot in SLOT_IDS:
        assert out.schema[slot] == pl.Utf8, f"{slot} must be Utf8 to join the bridge"
        out = (
            out.join(
                key.rename({"player_id": slot, "person_id": f"_{slot}"}),
                on=slot,
                how="left",
            )
            .drop(slot)
            .rename({f"_{slot}": slot})
        )
    filled = pl.sum_horizontal([pl.col(c).is_not_null() for c in SLOT_IDS]).sum()
    before = resolved.select(filled).item()
    after = out.select(filled).item()
    cover = after / before if before else 0.0
    if cover < PERSON_BRIDGE_FLOOR:
        raise RuntimeError(
            f"season {season}: person bridge covers {cover:.4f} of on-floor slots "
            f"< {PERSON_BRIDGE_FLOOR} -- refusing to pool a mis-identified design"
        )
    out = out.select(
        pl.col("contest_id").cast(pl.Int64, strict=False),
        "home",
        "away",
        "poss_team",
        "pts",
        *SLOT_IDS,
    )
    if out.get_column("contest_id").null_count():
        raise RuntimeError(f"season {season}: contest_id is not integer-like")
    return out


def person_to_player(bridge: pl.DataFrame, season: int) -> pl.DataFrame:
    """``person_id`` -> ONE ``player_id`` for ``season`` (the lowest, deterministically).

    The bridge is many-to-one within a season for the handful of people carrying
    two ids (a mid-season name change): 1-16 per season on both leagues. A
    person-keyed fit rates them once, which is correct, so publishing needs a
    single representative id; ``person_id`` is published beside it, so no
    identity is lost.
    """
    return (
        bridge.filter(pl.col("season") == season)
        .select("person_id", "player_id")
        .sort("person_id", "player_id")
        .unique(subset=["person_id"], keep="first", maintain_order=True)
    )


def resolve_season(league: str, season: int, bridge: pl.DataFrame) -> "dict | None":
    """Resolved possessions + stints + usable fraction for one season, or None.

    Keyed by the season's own ``player_id``. :func:`to_person` re-keys to the
    cross-season ``person_id``, and is applied ONLY on the pooled path -- a
    season that publishes ``flat`` goes through exactly the code it did before
    this estimator existed, so its output is unchanged rather than merely
    equivalent.
    """
    poss_f = _data_file(league, "possessions", season)
    ros_f = _data_file(league, "team_rosters", season)
    if not poss_f.is_file() or not ros_f.is_file():
        return None
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
    return {
        "resolved": resolved,
        "stints": stints,
        "rosters": rosters,
        "usable_fraction": usable / possessions.height if possessions.height else 0.0,
        "n_games": int(possessions["contest_id"].n_unique()),
    }


def _cached_season(
    league: str, season: int, bridge: pl.DataFrame, cache: dict
) -> "dict | None":
    """A pooled PREDECESSOR season: person-keyed stints, memoised.

    An ``--all`` sweep asks for each season three times (as a target and as the
    two pooled predecessors); the resolve is the expensive half and the stints
    are the small half, so only the stints are kept. The usable fraction is
    key-independent, so it is read here and the estimator can be chosen before
    the target season is re-keyed.
    """
    k = ("season", league, season)
    if k not in cache:
        got = resolve_season(league, season, bridge)
        cache[k] = (
            None
            if got is None
            else {
                "stints": aggregate_stints(to_person(got["resolved"], bridge, season)),
                "usable_fraction": got["usable_fraction"],
                "n_games": got["n_games"],
            }
        )
    return cache[k]


def choose_estimator(
    league: str, season: int, bridge: pl.DataFrame, cache: dict
) -> dict:
    """Which estimator season ``season`` publishes under, and its inputs.

    ``pooled`` requires the league to be in :data:`POOLED_LEAGUES` and the FULL
    :data:`MULTI_YEAR_WINDOW` to be present, every predecessor clearing gate 1
    on its own. A short window is NOT down-graded to "pool what we have": a
    two-season pool is a third estimator with its own ``sigma2`` distribution
    and no sweep stands behind such a band, so the season falls all the way
    back to ``flat``.
    """
    if league not in POOLED_LEAGUES:
        return {"estimator": "flat", "pool": {}}
    pool: dict[int, pl.DataFrame] = {}
    for s in range(season - MULTI_YEAR_WINDOW + 1, season):
        got = _cached_season(league, s, bridge, cache)
        if got is not None and got["usable_fraction"] >= USABLE_FRACTION_FLOOR:
            pool[s] = got["stints"]
    if league not in POOLED_LEAGUES or len(pool) != MULTI_YEAR_WINDOW - 1:
        return {"estimator": "flat", "pool": {}}
    return {"estimator": "pooled", "pool": pool}


def run_season(
    league: str,
    season: int,
    out_dir: Path,
    bridge: pl.DataFrame,
    min_spearman: float,
    cache: "dict | None" = None,
    survey: bool = False,
) -> "tuple[bool, dict]":
    """Fit, gate and (unless ``survey``) write one season.

    ``survey=True`` runs every gate computation, writes NOTHING, and REPORTS the
    gate-5(a) ``sigma2`` instead of enforcing its band -- the mode the band is
    derived in, so the survey measures exactly the quantity the gate will later
    compare. Every OTHER gate still fails the season.
    """
    cache = {} if cache is None else cache
    # Drop any prior manifest BEFORE the first gate can return: a gate failure
    # (or an interruption) must leave NO manifest, so the publisher refuses the
    # season. Otherwise a manifest from an earlier PASSING run outlives the new
    # failure and republishes stale numbers beside a stale parquet.
    stem = _DATA[league][2]
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"{stem}_rapm_league_{season}.parquet"
    mf_path = f.with_suffix(".manifest.json")
    if not survey:
        mf_path.unlink(missing_ok=True)

    rec: dict = {"league": league, "season": season}
    got = resolve_season(league, season, bridge)
    if got is None:
        _fail(season, "missing possessions or team_rosters input")
        return False, rec
    resolved, stints, rosters = got["resolved"], got["stints"], got["rosters"]
    frac = got["usable_fraction"]
    rec["usable_fraction"] = frac

    # Gate 1: usable fraction. This -- not a season list -- is what excludes
    # 2010's near-empty substitution corpus.
    if frac < USABLE_FRACTION_FLOOR:
        _fail(season, f"usable fraction {frac:.4f} < {USABLE_FRACTION_FLOOR}")
        return False, rec

    chosen = choose_estimator(league, season, bridge, cache)
    estimator, pool = chosen["estimator"], chosen["pool"]
    decay = DECAY[league]
    rec["estimator"] = estimator
    rec["pool_seasons"] = sorted([*pool, season])

    # Only the pooled path re-keys to person_id: a pooled design has to be one
    # column per human across seasons, while a flat season has no cross-season
    # column to share and re-keying it would change published rows for nothing.
    fit_stints = stints
    if pool:
        resolved = to_person(resolved, bridge, season)
        fit_stints = aggregate_stints(resolved)
    design = (
        stack_seasons({**pool, season: fit_stints}, season, decay) if pool else stints
    )
    players_all, info = solve_rapm_league(design, ridge_lambda=DEFAULT_RIDGE_LAMBDA)
    # Assert the pool reached the SOLVER, not just the label. A first cut of this
    # change reported estimator="pooled" for sixteen seasons while every design
    # was the single-season one, and the only symptom was a sigma2 that matched
    # the flat baseline card to six digits. A label is not evidence.
    if pool and not info["n_stints"] > fit_stints.height:
        raise AssertionError(
            f"{league} {season}: estimator={estimator} but the design has "
            f"{info['n_stints']} stints, the season alone has {fit_stints.height}"
        )
    rec["n_stints"] = info["n_stints"]
    # Season-t filter: a pooled fit rates everyone in the window on three-season
    # exposure. A per-season asset must carry season-t participants and season-t
    # possessions, or off_poss / def_poss silently become window sums.
    players = season_slice(players_all, fit_stints) if pool else players_all
    rec["n_players_pooled"] = players_all.height
    rec["n_players"] = players.height

    # Gate 2: level bands (Spearman is scale-blind).
    lo, hi = INTERCEPT_BAND[league]
    rec["intercept"], rec["hca"] = info["intercept"], info["hca"]
    if not (lo <= info["intercept"] <= hi):
        _fail(season, f"intercept {info['intercept']:.2f} outside [{lo}, {hi}]")
        return False, rec
    if not (HCA_BAND[0] <= info["hca"] <= HCA_BAND[1]):
        _fail(season, f"hca {info['hca']:.3f} outside {HCA_BAND}")
        return False, rec

    # Gate 3/4: external oracle, or the explicit ungated allowlist.
    teams = team_aggregate(fit_stints, players)
    if season in UNGATED_SEASONS[league]:
        external_gate = "ungated_no_oracle"
        rho_n, rho = None, None
    else:
        result = torvik_rho(league, season, teams)
        if isinstance(result, str):
            _fail(season, result)
            return False, rec
        rho_n, rho = result
        rec["torvik_spearman"], rec["torvik_teams"] = rho, rho_n
        if rho < min_spearman:
            _fail(season, f"torvik spearman {rho:.4f} < floor {min_spearman}")
            return False, rec
        external_gate = "passed"

    # Gate 5: the standard errors must behave like uncertainty (docstring item
    # 5). Every comparison is written `not (ok)` so a NaN FAILS.
    from scipy.stats import spearmanr

    rec["sigma2"] = info["sigma2"]
    band = SIGMA2_BAND.get((league, estimator))
    if not survey:
        if band is None:
            _fail(season, f"no sigma2 band is derived for estimator {estimator!r}")
            return False, rec
        lo, hi = band
        if not (lo <= info["sigma2"] <= hi):
            _fail(
                season,
                f"sigma2 {info['sigma2']:.1f} outside [{lo}, {hi}] (estimator {estimator})",
            )
            return False, rec
    p2 = players.with_columns((pl.col("off_poss") + pl.col("def_poss")).alias("poss"))
    se_rho = float(
        spearmanr(p2["poss"].to_numpy(), p2["rapm_net_se"].to_numpy()).statistic
    )
    rec["se_spearman_poss"] = se_rho
    if not (se_rho <= SE_SPEARMAN_CEILING):
        _fail(
            season, f"Spearman(poss, rapm_net_se) {se_rho:.4f} > {SE_SPEARMAN_CEILING}"
        )
        return False, rec
    dec = possession_deciles(players)["median_rapm_net_se"]
    se_bottom, se_top = float(dec[0]), float(dec[-1])
    rec["se_median_bottom_decile"], rec["se_median_top_decile"] = se_bottom, se_top
    if not (se_top < se_bottom):
        _fail(
            season,
            f"top-decile median SE {se_top:.3f} >= bottom-decile {se_bottom:.3f}",
        )
        return False, rec

    # The split-half check must refit the estimator that is actually PUBLISHED,
    # and must split EVERY pooled season by the same parity -- pooling whole
    # predecessor seasons into both halves would let the halves share
    # possessions and inflate the coverage by construction.
    pool_resolved = {}
    for s in pool:
        got_s = resolve_season(league, s, bridge)
        assert got_s is not None, f"pooled season {s} vanished between passes"
        # person-keyed, like the design they will be stacked into
        pool_resolved[s] = to_person(got_s["resolved"], bridge, s)

    def refit(part: pl.DataFrame, half: int):
        st = aggregate_stints(part)
        if not pool_resolved:
            return solve_rapm_league(st, ridge_lambda=DEFAULT_RIDGE_LAMBDA)
        extra = {
            s: aggregate_stints(r.filter(pl.col("contest_id") % 2 == half))
            for s, r in pool_resolved.items()
        }
        fitted, fit_info = solve_rapm_league(
            stack_seasons({**extra, season: st}, season, decay),
            ridge_lambda=DEFAULT_RIDGE_LAMBDA,
        )
        return season_slice(fitted, st), fit_info

    _pp, se_check = split_half_se_check(
        resolved, ridge_lambda=DEFAULT_RIDGE_LAMBDA, refit=refit
    )
    pool_resolved.clear()
    rec["se_coverage_posterior_net"] = se_check["coverage_rapm_net"]
    rec["se_coverage_sampling"] = {
        c: se_check[f"coverage_sampling_{c}"] for c in ("orapm", "drapm", "rapm_net")
    }
    if not (se_check["coverage_rapm_net"] >= SE_POSTERIOR_COVERAGE_FLOOR):
        _fail(
            season,
            f"posterior-SE split-half coverage {se_check['coverage_rapm_net']:.4f} < {SE_POSTERIOR_COVERAGE_FLOOR}",
        )
        return False, rec
    for c in ("orapm", "drapm", "rapm_net"):
        v = se_check[f"coverage_sampling_{c}"]
        if not (SE_SAMPLING_COVERAGE_BAND[0] <= v <= SE_SAMPLING_COVERAGE_BAND[1]):
            _fail(
                season,
                f"sampling-SE split-half coverage ({c}) {v:.4f} outside {SE_SAMPLING_COVERAGE_BAND}",
            )
            return False, rec

    # Augment: identity + provenance columns. A pooled fit is person-keyed, so
    # person_id IS its key and the season's player_id is looked up from it; a
    # flat fit is player_id-keyed and person_id is attached exactly as before.
    ros = rosters.select(
        pl.col("player_id").cast(pl.Utf8),
        pl.col("team").cast(pl.Utf8),
        pl.col("player").cast(pl.Utf8),
    ).unique(subset=["player_id"], keep="first")
    if pool:
        p2p = person_to_player(bridge, season)
        assert p2p.schema["player_id"] == ros.schema["player_id"], (
            "player_id dtype mismatch"
        )
        named = players.rename({"player_id": "person_id"}).join(
            p2p, on="person_id", how="left"
        )
        if named.get_column("player_id").null_count():
            _fail(season, "a rated person_id has no season player_id in the bridge")
            return False, rec
    else:
        assert players.schema["player_id"] == ros.schema["player_id"], (
            "player_id dtype mismatch"
        )
        named = players.join(
            bridge.filter(pl.col("season") == season).select("player_id", "person_id"),
            on="player_id",
            how="left",
        )
    out = (
        named.join(ros, on="player_id", how="left")
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
    n_games = got["n_games"]
    rec["rows"] = out.height

    if survey:
        print(
            f"  {season}: SURVEY estimator={estimator} pool={rec['pool_seasons']} "
            f"sigma2={info['sigma2']:.1f} rows={out.height} mu={info['intercept']:.2f} "
            f"hca={info['hca']:.3f} se_rho={se_rho:.3f} "
            f"cov_samp_net={se_check['coverage_sampling_rapm_net']:.4f}",
            flush=True,
        )
        return True, rec

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
        # Estimator record (2026-09-02): which of ESTIMATORS ran, and on what.
        "estimator": estimator,
        "pool_seasons": rec["pool_seasons"],
        "decay": decay if pool else None,
        "n_stints": info["n_stints"],
        "n_players_pooled": players_all.height,
        "usable_fraction": frac,
        "intercept": info["intercept"],
        "hca": info["hca"],
        "lsqr_istop": info["lsqr_istop"],
        "external_gate": external_gate,
        "torvik_teams": rho_n,
        "torvik_spearman": rho,
        # Gate 5 record (standard errors):
        "sigma2": info["sigma2"],
        "sigma2_band": list(SIGMA2_BAND[(league, estimator)]),
        "df_eff": info["df_eff"],
        "hca_se": info["hca_se"],
        "solve_max_abs_dev": info["solve_max_abs_dev"],
        "se_spearman_poss": se_rho,
        "se_median_bottom_decile": se_bottom,
        "se_median_top_decile": se_top,
        "se_split_games": [se_check["n_games_a"], se_check["n_games_b"]],
        "se_split_players": se_check["n_players"],
        "se_coverage_posterior_net": se_check["coverage_rapm_net"],
        "se_coverage_sampling": {
            c: se_check[f"coverage_sampling_{c}"]
            for c in ("orapm", "drapm", "rapm_net")
        },
        "se_zsd_sampling_net": se_check["z_sd_sampling_rapm_net"],
        "gates_passed": True,
    }
    mf_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    g = f"rho={rho:.4f} (n={rho_n})" if rho is not None else external_gate
    print(
        f"  {season}: {estimator} pool={rec['pool_seasons']} usable={frac:.2%} "
        f"players={out.height} mu={info['intercept']:.2f} "
        f"hca={info['hca']:.3f} | {g} | "
        f"se: sigma2={info['sigma2']:.0f} rho={se_rho:.3f} cov_post={se_check['coverage_rapm_net']:.4f} "
        f"cov_samp_net={se_check['coverage_sampling_rapm_net']:.4f} | wrote {f.name}",
        flush=True,
    )
    return True, rec


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
                "estimator": mf["estimator"],
                "pool_seasons": mf["pool_seasons"],
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
        "--survey",
        default=None,
        metavar="PATH",
        help=(
            "Derivation mode: run every gate computation over the seasons, write "
            "NO parquet and NO manifest, REPORT gate-5(a) sigma2 instead of "
            "enforcing its band, and dump the per-season gate record to PATH. "
            "This is how a sigma2 band is derived -- from observed values under "
            "the estimator that will be gated, never by widening another one's."
        ),
    )
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
    cache: dict = {}
    ok, records = [], []
    for s in seasons:
        passed, rec = run_season(
            a.league,
            s,
            Path(a.out),
            bridge,
            floor,
            cache,
            survey=a.survey is not None,
        )
        ok.append(passed)
        records.append(rec)
        # Keep only the seasons a later target can still ask for (the pooled
        # window plus the SPM baseline window); an --all sweep otherwise holds
        # sixteen seasons of stints at once.
        for key in [k for k in cache if k[2] < s - 3]:
            del cache[key]
    print(f"{sum(ok)}/{len(ok)} seasons passed all gates", flush=True)
    if a.survey is not None:
        Path(a.survey).write_text(
            json.dumps(records, indent=2, default=float), encoding="utf-8"
        )
        print(f"survey -> {a.survey}", flush=True)
        return 0 if all(ok) else 1
    if a.all and all(ok):
        print(f"evaluation card -> {write_card(a.league, Path(a.out))}", flush=True)
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
