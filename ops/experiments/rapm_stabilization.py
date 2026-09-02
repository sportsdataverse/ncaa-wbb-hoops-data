"""Measure two RAPM stabilisation levers against the shipped flat-ridge baseline.

This is an EVALUATION, not a producer. It writes no release asset and touches no
published tree; it reads this repo's published ``possessions`` / ``team_rosters`` /
``name_changes`` / ``player_box`` and prints (and parquet-dumps) a table of
baseline-vs-variant numbers. "It did not help" is a valid outcome and is what the
decision rule below is written to detect.

The design was pre-registered before any model code was written; the authoritative
copy is ``ClaudeCowork/ledgers/2026-09-01-writeup-improvements/reports/rapm-stabilization.md``.
The short version:

**Lever 1 — multi-year RAPM.** A decayed-weight STACKED design: pool seasons
``t-2 .. t`` into one fit whose columns are cross-season ``person_id``s, each stint
weighted ``decay ** (t - s)`` and offset to season ``t``'s scoring level
(``fit_weight`` / ``y_offset`` on the stints frame).

**Lever 2 — SPM-prior RAPM.** Shrink toward a box-score-plus-minus point estimate
instead of toward zero (``solve_rapm_league(prior_mean=...)``). The SPM is fitted
HERE, in this repo's own id space, by ridge regression of baseline RAPM on per-100
box rates -- see ``fit_spm`` for why the ESPN-keyed ``player_value`` artifact in
hoopR-mbb-data / wehoop-wbb-data was rejected as the coefficient source.

**Criteria** (all reported for every variant):

* ``C3`` out-of-sample game-margin MAE on held-out games -- PRIMARY, and the only
  one immune to the shared-information inflation below.
* ``C2`` next-season Spearman against the BASELINE season ``t+1`` fit, overall and
  by season-``t`` possession bin.
* ``C1`` split-half (odd/even ``contest_id``) reliability -- DIAGNOSTIC ONLY. Any
  lever that shrinks both halves toward a shared non-zero point raises this
  mechanically. For lever 1 the parity split is applied to every pooled season so
  the halves share no possession; for lever 2 the prior is common to both halves by
  construction and C1 is inflated. It decides nothing.
* ``torvik`` team-aggregate Spearman guardrail (the existing publish floor).

**Leakage boundaries**, enforced in code, not assumed:

* a fit for target season ``t`` pools only seasons ``<= t``;
* SPM coefficients come from baseline RAPM of seasons ``t-3 .. t-1`` only;
* SPM features for season ``t`` are aggregated over the FIT's games only, so a
  held-out game cannot reach the prior through the box score;
* the C2 target is always the baseline ``t+1`` fit, identical for every variant.

Usage::

    uv run python ops/experiments/rapm_stabilization.py --league mbb
    uv run python ops/experiments/rapm_stabilization.py --league mbb --seasons 2016 2017
    uv run python ops/experiments/rapm_stabilization.py --league mbb --stage dev   # decay grid
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path

import numpy as np
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

_ROOT = Path(__file__).resolve().parents[4]
_DATA = {
    "mbb": ("hoopR-dev/ncaa-mbb-hoops-data", "mbb", "ncaa_mbb"),
    "wbb": ("wehoop-dev/ncaa-wbb-hoops-data", "wbb", "ncaa_wbb"),
}
_ORACLE = Path(__file__).resolve().parents[1] / "oracle"

#: Pre-registered. Hyperparameters are chosen on DEV and never revisited after.
DEV_SEASONS = [2014, 2015]
EVAL_SEASONS = list(range(2016, 2026))

#: The hyperparameters FROZEN on the development seasons (see the report). An
#: ``--stage eval`` run with any other pair is stamped ``frozen: false``, written to a
#: separate ``*_experimental`` file, and REFUSED by the summariser -- otherwise an
#: arbitrary re-run could overwrite the result file and be read as the verdict.
FROZEN_HYPERPARAMS = {"mbb": (0.5, 100.0), "wbb": (0.75, 0.0)}

#: Pre-registered evaluation constants.
MULTI_YEAR_WINDOW = 3  # seasons t-2 .. t
DECAY_GRID = (0.25, 0.5, 0.75)
SPM_SHRINK_GRID = (0.0, 100.0, 300.0)  # prior scaled by poss / (poss + k)
TEST_GAME_MODULUS = 4  # a game is held out iff int(contest_id) % 4 == 0
SPM_TARGET_SEASONS = 3  # SPM coefficients fitted on baseline RAPM of t-3 .. t-1
SPM_MIN_POSS = 400  # target-noise floor on the SPM training rows
BOOTSTRAP_DRAWS = 2000
POSS_BINS = ((0, 200), (200, 500), (500, 1000), (1000, 10**9))

#: DESCRIPTIVE ONLY, not part of the decision rule: finer bins used to locate the
#: possession threshold at which a lever stops helping. The registered POSS_BINS
#: above are what the verdict is computed on and are unchanged.
FINE_BINS = ((0, 100), (100, 200), (200, 300), (300, 400), (400, 600), (600, 800), (800, 1100), (1100, 1500), (1500, 10**9))

#: Identity-integrity floor: the (season, player_id) -> person_id bridge must cover
#: essentially every on-floor slot, or the pooled design is silently merging or
#: dropping people. Observed on MBB 2011-2026: 1.000.
PERSON_BRIDGE_FLOOR = 0.999

#: Existing publish-blocking Torvik floor, copied from ops/build_rapm_league.py.
#: Never lowered here -- this script only reports whether a variant still clears it.
#: WBB RE-PROBE: Torvik publishes NO women's ratings before 2021 (the producer's
#: UNGATED_SEASONS is wbb 2011-2020), so ``torvik_rho`` returns NaN for evaluation
#: seasons 2016-2020 and the guardrail is only informative from 2021 on. It is NOT
#: silently satisfied there -- a NaN is reported as NaN in the table.
SPEARMAN_FLOOR = {"mbb": 0.93, "wbb": 0.89}
MIN_ORACLE_TEAMS = 250

_SLOTS = [f"{side}_{i}_id" for side in ("home", "away") for i in range(1, 6)]
_HOME, _AWAY = _SLOTS[:5], _SLOTS[5:]


# --------------------------------------------------------------------------- io


def _file(league: str, dataset: str, season: "int | None" = None) -> Path:
    repo, lg, stem = _DATA[league]
    name = (
        f"{stem}_{dataset}_{season}.parquet" if season else f"{stem}_{dataset}.parquet"
    )
    return _ROOT / repo / lg / dataset / "parquet" / name


def _cache_dir() -> Path:
    d = Path(
        os.environ.get("RAPM_STAB_CACHE", Path(__file__).resolve().parent / "_cache")
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def person_bridge(league: str) -> pl.DataFrame:
    """``(season, player_id) -> person_id`` across every local roster season."""
    frames = [
        pl.read_parquet(f)
        for s in range(2010, 2027)
        if (f := _file(league, "team_rosters", s)).is_file()
    ]
    rosters = pl.concat(frames, how="diagonal_relaxed")
    nc = _file(league, "name_changes")
    keys = build_person_keys(
        rosters, name_changes=pl.read_parquet(nc) if nc.is_file() else None
    )
    return keys.select(
        pl.col("season").cast(pl.Int64),
        pl.col("player_id").cast(pl.Utf8),
        pl.col("person_id").cast(pl.Utf8),
    ).unique(subset=["season", "player_id"])


def _input_fingerprint(paths: "list[Path]", bridge: pl.DataFrame) -> str:
    """Short digest of the inputs a cached resolve depends on.

    Keyed into the cache FILENAME, so a corrected possessions tree, roster,
    name_changes table or person bridge produces a DIFFERENT cache entry instead
    of silently re-serving stale ``person_id`` mappings -- and silently skipping
    the coverage check that would have caught them.
    """
    parts = [str(int(bridge.hash_rows().sum()))]
    for p in paths:
        st = p.stat() if p.is_file() else None
        parts.append(f"{p.name}:{st.st_size}:{st.st_mtime_ns}" if st else f"{p.name}:absent")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def resolved_person(league: str, season: int, bridge: pl.DataFrame) -> pl.DataFrame:
    """Slim, person_id-keyed resolved possessions for one season (cached)."""
    poss_f, ros_f = _file(league, "possessions", season), _file(league, "team_rosters", season)
    fp = _input_fingerprint([poss_f, ros_f, _file(league, "name_changes")], bridge)
    cache = _cache_dir() / f"{league}_resolved_person_{season}_{fp}.parquet"
    if cache.is_file():
        return pl.read_parquet(cache)
    poss_f, ros_f = (
        _file(league, "possessions", season),
        _file(league, "team_rosters", season),
    )
    if not poss_f.is_file() or not ros_f.is_file():
        raise FileNotFoundError(
            f"{league} {season}: missing {poss_f.name if not poss_f.is_file() else ros_f.name}"
        )
    poss, ros = pl.read_parquet(poss_f), pl.read_parquet(ros_f)
    nc_f = _file(league, "name_changes")
    nc = (
        pl.read_parquet(nc_f).filter(pl.col("season").cast(pl.Utf8) == str(season))
        if nc_f.is_file()
        else None
    )
    xwalk = expand_xwalk_aliases(
        build_player_xwalk(ros), observed_pairs(poss), name_changes=nc
    )
    res = resolve_possessions(poss, xwalk, non_di="drop")

    key = bridge.filter(pl.col("season") == season).select("player_id", "person_id")
    assert key.schema["player_id"] == pl.Utf8, "bridge player_id must be Utf8"
    out = res.select("contest_id", "home", "away", "poss_team", "pts", *_SLOTS)
    for slot in _SLOTS:
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
    # Identity-integrity: every non-null slot id must have found a person.
    before = res.select(
        pl.sum_horizontal([pl.col(c).is_not_null() for c in _SLOTS]).sum()
    ).item()
    after = out.select(
        pl.sum_horizontal([pl.col(c).is_not_null() for c in _SLOTS]).sum()
    ).item()
    cover = after / before if before else 0.0
    if cover < PERSON_BRIDGE_FLOOR:
        raise RuntimeError(
            f"{league} {season}: person bridge covers {cover:.4f} of slots < {PERSON_BRIDGE_FLOOR}"
        )
    out = out.select(
        pl.col("contest_id").cast(pl.Int64, strict=False),
        "home",
        "away",
        "poss_team",
        "pts",
        *_SLOTS,
    )
    if out.get_column("contest_id").null_count():
        raise RuntimeError(f"{league} {season}: contest_id is not integer-like")
    out.write_parquet(cache)
    return out


# ------------------------------------------------------------------- stint math


def _sided(res: pl.DataFrame) -> pl.DataFrame:
    """Add off_ids / def_ids / is_home_offense, dropping unusable possessions."""
    usable = res.filter(
        pl.all_horizontal([pl.col(c).is_not_null() for c in _SLOTS])
        & (
            (pl.col("poss_team") == pl.col("home"))
            | (pl.col("poss_team") == pl.col("away"))
        )
    )
    is_home = pl.col("poss_team") == pl.col("home")
    return usable.with_columns(
        pl.when(is_home)
        .then(pl.concat_list([pl.col(c) for c in _HOME]).list.sort())
        .otherwise(pl.concat_list([pl.col(c) for c in _AWAY]).list.sort())
        .alias("off_ids"),
        pl.when(is_home)
        .then(pl.concat_list([pl.col(c) for c in _AWAY]).list.sort())
        .otherwise(pl.concat_list([pl.col(c) for c in _HOME]).list.sort())
        .alias("def_ids"),
        is_home.alias("is_home_offense"),
    )


def game_stints(res: pl.DataFrame) -> pl.DataFrame:
    """Like ``aggregate_stints`` but keeping ``contest_id`` in the group key.

    Needed only for scoring held-out GAMES; the fits all use the engine's own
    ``aggregate_stints`` so nothing under test depends on this function.
    """
    shaped = _sided(res)
    return (
        shaped.with_columns(
            pl.col("off_ids").list.join("|").alias("_ok"),
            pl.col("def_ids").list.join("|").alias("_dk"),
        )
        .group_by(["contest_id", "_ok", "_dk", "is_home_offense"], maintain_order=True)
        .agg(
            pl.col("off_ids").first(),
            pl.col("def_ids").first(),
            pl.len().cast(pl.Int64).alias("n_poss"),
            pl.col("pts").cast(pl.Int64).sum().alias("pts"),
        )
        .select("contest_id", "off_ids", "def_ids", "is_home_offense", "n_poss", "pts")
    )


def _season_level(stints: pl.DataFrame) -> float:
    """Possession-weighted mean pts/100 of a stint set (the season's scoring level)."""
    return float(100.0 * stints["pts"].sum() / stints["n_poss"].sum())


def stacked_stints(
    per_season: "dict[int, pl.DataFrame]", target: int, decay: float
) -> pl.DataFrame:
    """One pooled design: ``fit_weight = decay ** (t - s)``, ``y_offset`` = level drift."""
    level_t = _season_level(per_season[target])
    parts = []
    for s, st in sorted(per_season.items()):
        if s > target:  # leakage guard: a season never sees its own future
            raise ValueError(f"stacked_stints: season {s} > target {target}")
        parts.append(
            st.with_columns(
                pl.lit(float(decay ** (target - s))).alias("fit_weight"),
                pl.lit(_season_level(st) - level_t).alias("y_offset"),
            )
        )
    return pl.concat(parts, how="vertical")


# ------------------------------------------------------------------------- spm


_BOX_COUNTS = [
    "pts", "orb", "drb", "ast", "stl", "blk", "tov", "pf",
    "fga", "fgm", "tpa", "tpm", "fta", "ftm",
    "rima", "rimm", "mida", "midm", "pbacka", "pbackm",
    "blk_rim", "blk_mid", "blk_three", "fgm_ast",
]  # fmt: skip
SPM_FEATURES = [f"{c}_p100" for c in _BOX_COUNTS] + [
    "ts_pct",
    "efg_pct",
    "tp_rate",
    "ft_rate",
    "mins_per_poss",
]


def box_features(
    league: str,
    season: int,
    bridge: pl.DataFrame,
    contest_ids: "set[int] | None" = None,
) -> pl.DataFrame:
    """Per-100-possession box rates per ``person_id`` for one season.

    ``contest_ids`` restricts the aggregation to those games -- the leakage
    boundary that keeps a held-out game out of the SPM prior.
    """
    f = _file(league, "player_box", season)
    if not f.is_file():
        raise FileNotFoundError(f"{league} {season}: no player_box")
    pb = pl.read_parquet(f).select(
        "contest_id", "player_id", "mins", "o_poss", *_BOX_COUNTS
    )
    pb = pb.with_columns(pl.col("contest_id").cast(pl.Int64, strict=False))
    if contest_ids is not None:
        pb = pb.filter(pl.col("contest_id").is_in(list(contest_ids)))
    key = bridge.filter(pl.col("season") == season).select("player_id", "person_id")
    pb = pb.join(key, on="player_id", how="inner")
    tot = pb.group_by("person_id").agg(
        pl.col("o_poss").sum().alias("o_poss"),
        pl.col("mins").sum().alias("mins"),
        *[pl.col(c).sum().alias(c) for c in _BOX_COUNTS],
    )
    tot = tot.filter(pl.col("o_poss") > 0)
    p100 = 100.0 / pl.col("o_poss")
    return tot.select(
        "person_id",
        pl.col("o_poss"),
        *[(pl.col(c) * p100).alias(f"{c}_p100") for c in _BOX_COUNTS],
        (pl.col("pts") / (2.0 * (pl.col("fga") + 0.44 * pl.col("fta")))).alias(
            "ts_pct"
        ),
        ((pl.col("fgm") + 0.5 * pl.col("tpm")) / pl.col("fga")).alias("efg_pct"),
        (pl.col("tpa") / pl.col("fga")).alias("tp_rate"),
        (pl.col("fta") / pl.col("fga")).alias("ft_rate"),
        (pl.col("mins") / pl.col("o_poss")).alias("mins_per_poss"),
    ).with_columns(
        # A player with zero FGA makes every shooting ratio 0/0 or x/0: polars gives
        # NaN for the first and +/-inf for the second, and fill_nan alone would let
        # the inf through into the design matrix.
        [
            pl.when(pl.col(c).is_finite()).then(pl.col(c)).otherwise(0.0).alias(c)
            for c in SPM_FEATURES
        ]
    )


def fit_spm(
    league: str, target: int, bridge: pl.DataFrame, baselines: "dict[int, pl.DataFrame]"
) -> dict:
    """Ridge box-score plus/minus, fitted on baseline RAPM of seasons ``t-3 .. t-1``.

    Rejected alternative: the fitted box-Plus/Minus coefficient vector published by
    hoopR-mbb-data / wehoop-wbb-data ``player_value``. That artifact is ESPN-keyed,
    this pipeline is stats.ncaa.org-keyed, and ``team_rosters`` carries no ESPN
    athlete id -- a name bridge would inject an uncontrolled match-rate error into
    the exact quantity under test. Fitting on this repo's own ``player_box`` keeps
    the id space, the era and the target identical.
    """
    rows = []
    for s in range(target - SPM_TARGET_SEASONS, target):
        if s not in baselines:
            continue
        feats = box_features(
            league, s, bridge
        )  # full season: it is strictly in the past
        tgt = baselines[s].select(
            pl.col("player_id").alias("person_id"),
            "orapm",
            "drapm",
            (pl.col("off_poss") + pl.col("def_poss")).alias("poss"),
        )
        rows.append(
            feats.join(tgt, on="person_id", how="inner")
            .filter(pl.col("poss") >= SPM_MIN_POSS)
            .with_columns(pl.lit(s).alias("_season"))
        )
    if not rows:
        raise RuntimeError(
            f"fit_spm: no prior-season baselines available for target {target}"
        )
    train = pl.concat(rows, how="vertical")
    x = train.select(SPM_FEATURES).to_numpy().astype(np.float64)
    w = train["poss"].to_numpy().astype(np.float64)
    seasons = train["_season"].to_numpy()
    mean = np.average(x, axis=0, weights=w)
    sd = np.sqrt(np.average((x - mean) ** 2, axis=0, weights=w))
    sd[sd == 0] = 1.0
    z = (x - mean) / sd
    models = {}
    for side in ("orapm", "drapm"):
        y = train[side].to_numpy().astype(np.float64)
        alpha = _pick_alpha(z, y, w, seasons)
        models[side] = (*_ridge(z, y, w, alpha), alpha)
    return {
        "models": models,
        "mean": mean,
        "sd": sd,
        "n_train": train.height,
        "alphas": {k: v[2] for k, v in models.items()},
        "seasons": sorted(set(int(s) for s in seasons)),
    }


def _ridge(
    z: np.ndarray, y: np.ndarray, w: np.ndarray, alpha: float
) -> "tuple[np.ndarray, float]":
    """Weighted ridge on already-standardised features; intercept unpenalised."""
    y0 = float(np.average(y, weights=w))
    zw = z * w[:, None]
    g = z.T @ zw + alpha * np.eye(z.shape[1])
    return np.linalg.solve(g, zw.T @ (y - y0)), y0


def _pick_alpha(
    z: np.ndarray, y: np.ndarray, w: np.ndarray, seasons: np.ndarray
) -> float:
    """Leave-one-SEASON-out weighted MSE. Grouping by season, never a bare KFold:
    the panel repeats people within a season, and a random split would leak them."""
    grid = np.logspace(-2, 5, 29)
    uniq = sorted(set(seasons.tolist()))
    if len(uniq) < 2:
        return float(grid[len(grid) // 2])
    best, best_mse = grid[0], math.inf
    for a in grid:
        num = den = 0.0
        for s in uniq:
            te = seasons == s
            coef, y0 = _ridge(z[~te], y[~te], w[~te], float(a))
            err = y[te] - (z[te] @ coef + y0)
            num += float(np.sum(w[te] * err**2))
            den += float(np.sum(w[te]))
        if num / den < best_mse:
            best, best_mse = float(a), num / den
    return float(best)


def spm_prior(
    spm: dict, feats: pl.DataFrame, exposure: pl.DataFrame, shrink_k: float = 0.0
) -> pl.DataFrame:
    """Apply an SPM fit to a season's box rates -> a ``prior_mean`` frame.

    ``shrink_k`` scales each prediction by ``poss / (poss + k)``: a 20-possession
    player's box RATES are noise, and an unshrunk prior would hand the ridge that
    noise as a confident centre. ``k = 0`` is the unshrunk SPM; the value used is
    picked on the development seasons (:data:`SPM_SHRINK_GRID`).

    Predictions are then re-centred to possession-weighted mean zero on the players
    the fit will actually rate, because the RAPM scale is centred by construction;
    an off-centre prior would shift the whole league.
    """
    z = (feats.select(SPM_FEATURES).to_numpy().astype(np.float64) - spm["mean"]) / spm[
        "sd"
    ]
    pred = {side: z @ coef + y0 for side, (coef, y0, _a) in spm["models"].items()}
    out = feats.select(
        pl.col("person_id").alias("player_id"),
        pl.Series("orapm_prior", pred["orapm"]),
        pl.Series("drapm_prior", pred["drapm"]),
    ).join(exposure, on="player_id", how="inner")
    if shrink_k > 0:
        out = out.with_columns(
            [
                (pl.col(c) * pl.col("poss") / (pl.col("poss") + shrink_k)).alias(c)
                for c in ("orapm_prior", "drapm_prior")
            ]
        )
    w = out["poss"].to_numpy().astype(np.float64)
    return out.select(
        "player_id",
        *[
            (pl.col(c) - float(np.average(out[c].to_numpy(), weights=w))).alias(c)
            for c in ("orapm_prior", "drapm_prior")
        ],
    )


# -------------------------------------------------------------------- criteria


def predict_games(
    stints: pl.DataFrame, players: pl.DataFrame, info: dict
) -> pl.DataFrame:
    """Per-game predicted vs actual margin (home perspective) over usable possessions."""
    coef = players.select(pl.col("player_id").alias("pid"), "orapm", "drapm")
    s = stints.with_row_index("_r")

    def _sum(ids: str, col: str) -> pl.DataFrame:
        return (
            s.select("_r", pl.col(ids).alias("pid"))
            .explode("pid", empty_as_null=False)
            .join(coef, on="pid", how="left")
            .group_by("_r")
            .agg(pl.col(col).fill_null(0.0).sum().alias(f"_{col}"))
        )

    joined = (
        s.join(_sum("off_ids", "orapm"), on="_r", how="left")
        .join(_sum("def_ids", "drapm"), on="_r", how="left")
        .with_columns(
            (
                info["intercept"]
                + pl.col("_orapm")
                - pl.col("_drapm")
                + info["hca"]
                * pl.when(pl.col("is_home_offense")).then(1.0).otherwise(-1.0)
            ).alias("_pred100")
        )
        .with_columns(
            pl.when(pl.col("is_home_offense")).then(1.0).otherwise(-1.0).alias("_sign"),
        )
    )
    return (
        joined.group_by("contest_id")
        .agg(
            (pl.col("_sign") * pl.col("_pred100") * pl.col("n_poss") / 100.0)
            .sum()
            .alias("pred_margin"),
            (pl.col("_sign") * pl.col("pts"))
            .sum()
            .cast(pl.Float64)
            .alias("actual_margin"),
            pl.col("n_poss").sum().alias("n_poss"),
        )
        .with_columns(
            (pl.col("pred_margin") - pl.col("actual_margin")).abs().alias("abs_err")
        )
        .sort("contest_id")
    )


def cluster_bootstrap(
    diff: np.ndarray, draws: int = BOOTSTRAP_DRAWS, seed: int = 20260902
) -> "tuple[float, float]":
    """95% CI of the mean paired per-GAME difference, resampling games (never rows)."""
    rng = np.random.default_rng(seed)
    n = len(diff)
    means = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(draws)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import spearmanr

    if len(a) < 3:
        return float("nan")
    return float(spearmanr(a, b).statistic)


def next_season_corr(
    est: pl.DataFrame, nxt: pl.DataFrame, poss_t: pl.DataFrame
) -> dict:
    """Spearman of a season-t estimate against the BASELINE season t+1 estimate.

    ``poss_t`` is season-``t`` exposure only, and is the SAME frame for every
    variant. Binning on the variant's own ``off_poss + def_poss`` would put a
    multi-year player in a higher bin than the baseline puts the same player,
    and the low-possession comparison -- the whole claim of lever 1 -- would be
    between different sets of players.
    """
    j = (
        est.select("player_id", "rapm_net")
        .join(poss_t, on="player_id", how="inner")
        .join(
            nxt.select("player_id", pl.col("rapm_net").alias("net_next")),
            on="player_id",
            how="inner",
        )
    )
    out = {
        "n": j.height,
        "overall": spearman(j["rapm_net"].to_numpy(), j["net_next"].to_numpy()),
    }
    for lo, hi in POSS_BINS:
        b = j.filter((pl.col("poss") >= lo) & (pl.col("poss") < hi))
        out[f"bin_{lo}"] = spearman(b["rapm_net"].to_numpy(), b["net_next"].to_numpy())
        out[f"bin_{lo}_n"] = b.height
    for lo, hi in FINE_BINS:
        b = j.filter((pl.col("poss") >= lo) & (pl.col("poss") < hi))
        out[f"fine_{lo}"] = spearman(b["rapm_net"].to_numpy(), b["net_next"].to_numpy())
        out[f"fine_{lo}_n"] = b.height
    return out


def torvik_rho(league: str, season: int, teams: pl.DataFrame) -> float:
    path = _ORACLE / f"ncaa_{league}_torvik.parquet"
    if not path.is_file():
        return float("nan")
    oracle = (
        pl.read_parquet(path)
        .filter(pl.col("season") == str(season))
        .select(pl.col("team").cast(pl.Utf8), "adjem")
    )
    if oracle.height == 0:
        return float("nan")
    j = teams.join(oracle, on="team", how="inner")
    if j.height < MIN_ORACLE_TEAMS:
        return float("nan")
    return spearman(j["team_net"].to_numpy(), j["adjem"].to_numpy())


# ------------------------------------------------------------------------ runs


def _fit(
    stints: pl.DataFrame,
    prior: "pl.DataFrame | None" = None,
    lam: float = DEFAULT_RIDGE_LAMBDA,
):
    players, info = solve_rapm_league(
        stints, ridge_lambda=lam, prior_mean=prior, compute_se=False
    )
    assert isinstance(players, pl.DataFrame)
    return players, info


def _exposure(stints: pl.DataFrame) -> pl.DataFrame:
    s = stints.with_row_index("_r")
    parts = [
        s.select(pl.col(c).alias("pid"), "n_poss").explode("pid", empty_as_null=False)
        for c in ("off_ids", "def_ids")
    ]
    return (
        pl.concat(parts, how="vertical")
        .group_by("pid")
        .agg(pl.col("n_poss").sum().alias("poss"))
        .rename({"pid": "player_id"})
    )


def run_season(
    league: str,
    target: int,
    bridge: pl.DataFrame,
    decay: float,
    shrink_k: float,
    cache: dict,
) -> dict:
    """Every variant, every criterion, for one target season."""
    t0 = time.time()

    def get_res(s: int) -> pl.DataFrame:
        k = ("res", league, s)
        if k not in cache:
            cache[k] = resolved_person(league, s, bridge)
        return cache[k]

    def get_st(s: int) -> pl.DataFrame:
        k = ("st", league, s)
        if k not in cache:
            cache[k] = aggregate_stints(get_res(s))
        return cache[k]

    seasons = [s for s in range(target - MULTI_YEAR_WINDOW + 1, target + 1)]
    res = {s: get_res(s) for s in seasons if _file(league, "possessions", s).is_file()}
    full_st = {s: get_st(s) for s in res}

    games = sorted(res[target].get_column("contest_id").unique().to_list())
    test_ids = {g for g in games if g % TEST_GAME_MODULUS == 0}
    train_res = res[target].filter(~pl.col("contest_id").is_in(list(test_ids)))
    test_res = res[target].filter(pl.col("contest_id").is_in(list(test_ids)))
    train_st = aggregate_stints(train_res)
    test_gs = game_stints(test_res)

    # baseline full-season fits, cached (they are also the SPM target and the C2 target)
    def baseline_full(s: int) -> pl.DataFrame:
        k = ("base", league, s)
        if k not in cache:
            cache[k] = _fit(get_st(s))[0]
        return cache[k]

    baselines = {}
    for s in range(target - SPM_TARGET_SEASONS, target):
        if (
            _file(league, "possessions", s).is_file()
            and _file(league, "player_box", s).is_file()
        ):
            baselines[s] = baseline_full(s)
    spm = fit_spm(league, target, bridge, baselines)

    variants: dict[str, dict] = {}

    # --- BASELINE -----------------------------------------------------------
    p_tr, i_tr = _fit(train_st)
    p_fu, i_fu = _fit(full_st[target])
    variants["baseline"] = {"train": (p_tr, i_tr), "full": (p_fu, i_fu)}

    # --- LEVER 1: multi-year ------------------------------------------------
    my_train = stacked_stints(
        {**{s: full_st[s] for s in res if s < target}, target: train_st}, target, decay
    )
    my_full = stacked_stints({s: full_st[s] for s in res}, target, decay)
    variants["multi_year"] = {"train": _fit(my_train), "full": _fit(my_full)}

    # --- LEVER 2: SPM prior -------------------------------------------------
    # features restricted to the FIT's games: a held-out game must not reach the prior
    prior_tr = spm_prior(
        spm,
        box_features(league, target, bridge, set(games) - test_ids),
        _exposure(train_st),
        shrink_k,
    )
    prior_fu = spm_prior(
        spm, box_features(league, target, bridge), _exposure(full_st[target]), shrink_k
    )
    variants["spm_prior"] = {
        "train": _fit(train_st, prior_tr),
        "full": _fit(full_st[target], prior_fu),
    }

    # --- LEVER 1+2 combined -------------------------------------------------
    variants["multi_year_spm"] = {
        "train": _fit(my_train, prior_tr),
        "full": _fit(my_full, prior_fu),
    }

    # --- criteria -----------------------------------------------------------
    nxt = (
        baseline_full(target + 1)
        if _file(league, "possessions", target + 1).is_file()
        else None
    )
    base_games = predict_games(test_gs, *variants["baseline"]["train"])
    # ONE season-t exposure frame, shared by every variant's possession bins.
    poss_t = _exposure(full_st[target])
    out = {
        "season": target,
        "league": league,
        "decay": decay,
        "shrink_k": shrink_k,
        "frozen": (decay, shrink_k) == FROZEN_HYPERPARAMS[league],
        "n_test_games": base_games.height,
        "spm_n_train": spm["n_train"],
        "variants": {},
    }

    for name, v in variants.items():
        pg = predict_games(test_gs, *v["train"])
        j = base_games.join(
            pg.select("contest_id", pl.col("abs_err").alias("err_v")),
            on="contest_id",
            how="inner",
        )
        diff = (j["err_v"] - j["abs_err"]).to_numpy()
        lo, hi = cluster_bootstrap(diff) if name != "baseline" else (0.0, 0.0)
        rec = {
            "c3_mae": float(pg["abs_err"].mean()),
            "c3_diff_mean": float(diff.mean()),
            "c3_diff_ci": [lo, hi],
            # per-GAME paired differences, kept so the summariser can run the
            # pre-registered POOLED cluster bootstrap over every evaluation
            # season's games at once, not one season at a time.
            "c3_diff_games": [float(x) for x in diff],
            "prior_mad": float(v["full"][1].get("prior_mean_mad", 0.0)),
            "n_players": v["full"][0].height,
        }
        if nxt is not None:
            rec["c2"] = next_season_corr(v["full"][0], nxt, poss_t)
        rec["torvik"] = torvik_rho(
            league, target, team_aggregate(full_st[target], v["full"][0])
        )
        out["variants"][name] = rec

    # --- C1 split-half (diagnostic) ----------------------------------------
    out["c1"] = split_half(
        league, target, res, full_st, decay, spm, bridge, poss_t, shrink_k
    )
    out["secs"] = round(time.time() - t0, 1)
    return out


def split_half(
    league, target, res, full_st, decay, spm, bridge, poss_t, shrink_k
) -> dict:
    """Odd/even-contest_id reliability. For multi-year, EVERY pooled season is split."""
    halves = {}
    for h in (0, 1):
        parts = {
            s: aggregate_stints(r.filter(pl.col("contest_id") % 2 == h))
            for s, r in res.items()
        }
        ids = {
            s: set(
                r.filter(pl.col("contest_id") % 2 == h)
                .get_column("contest_id")
                .unique()
                .to_list()
            )
            for s, r in res.items()
        }
        pri = spm_prior(
            spm,
            box_features(league, target, bridge, ids[target]),
            _exposure(parts[target]),
            shrink_k,
        )
        halves[h] = {
            "baseline": _fit(parts[target])[0],
            "multi_year": _fit(stacked_stints(parts, target, decay))[0],
            "spm_prior": _fit(parts[target], pri)[0],
            "multi_year_spm": _fit(stacked_stints(parts, target, decay), pri)[0],
        }
    out = {}
    for name in halves[0]:
        # Bins come from the shared FULL-season-t exposure, so every variant's
        # low-possession bin holds the same players.
        j = (
            halves[0][name]
            .select("player_id", "rapm_net")
            .join(
                halves[1][name].select(
                    "player_id", pl.col("rapm_net").alias("rapm_net_b")
                ),
                on="player_id",
                how="inner",
            )
            .join(poss_t, on="player_id", how="inner")
        )
        out[name] = {
            "n": j.height,
            "r": spearman(j["rapm_net"].to_numpy(), j["rapm_net_b"].to_numpy()),
        }
        for lo, hi in POSS_BINS:
            b = j.filter((pl.col("poss") >= lo) & (pl.col("poss") < hi))
            out[name][f"bin_{lo}"] = spearman(
                b["rapm_net"].to_numpy(), b["rapm_net_b"].to_numpy()
            )
    return out


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--league", default="wbb", choices=sorted(_DATA))
    ap.add_argument("--seasons", type=int, nargs="*")
    ap.add_argument("--stage", choices=("dev", "eval"), default="eval")
    ap.add_argument("--decay", type=float, default=0.5)
    ap.add_argument("--shrink-k", type=float, default=0.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    seasons = a.seasons or (DEV_SEASONS if a.stage == "dev" else EVAL_SEASONS)
    bridge = person_bridge(a.league)
    cache: dict = {}
    grid = (
        [(d, k) for d in DECAY_GRID for k in SPM_SHRINK_GRID]
        if a.stage == "dev"
        else [(a.decay, a.shrink_k)]
    )
    records = []
    for d, k in grid:
        for s in seasons:
            r = run_season(a.league, s, bridge, d, k, cache)
            records.append(r)
            v = r["variants"]
            print(
                f"{a.league} {s} decay={d} k={k}: "
                + " | ".join(f"{n} C3={x['c3_mae']:.4f}" for n, x in v.items())
                + f"  ({r['secs']}s)",
                flush=True,
            )
    # "Registered" is the WHOLE protocol, not just the hyperparameters: the frozen
    # pair AND every evaluation season. `--seasons 2014` with the frozen pair would
    # otherwise stamp frozen:true, take the canonical filename, and score a verdict
    # on a hyperparameter-SELECTION season.
    registered = (
        a.stage == "eval"
        and all(r["frozen"] for r in records)
        and {r["season"] for r in records} == set(EVAL_SEASONS)
    )
    experimental = a.stage == "eval" and not registered
    if experimental:
        print(
            f"WARNING: --stage eval with (decay={a.decay}, shrink_k={a.shrink_k}) over "
            f"{sorted({r['season'] for r in records})} is NOT the registered protocol "
            f"(frozen pair {FROZEN_HYPERPARAMS[a.league]} over {EVAL_SEASONS}); writing an "
            "*_experimental* file that the summariser will refuse to score.",
            flush=True,
        )
    stem = f"{a.league}_{a.stage}{'_experimental' if experimental else ''}_results.json"
    out = Path(a.out or (_cache_dir() / stem))
    if experimental and "_experimental" not in out.name:
        # An explicit --out must not be able to park an unregistered run on the
        # canonical artifact's path.
        out = out.with_name(out.stem + "_experimental" + out.suffix)
    out.write_text(json.dumps(records, indent=2, default=float), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
