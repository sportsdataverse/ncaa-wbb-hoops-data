"""Does each stabilisation lever keep the PUBLISHED standard errors calibrated?

``rapm_stabilization.py`` measured the two levers' POINT ESTIMATES and both won
on every pre-registered criterion. That is a different question from whether the
uncertainty a lever publishes is honest, and the producer's gate 5(d) -- the
sampling-SE split-half calibration frozen on 2026-09-01, band ``[0.92, 0.98]``
against a 0.954 nominal -- is where that question is asked.

This script asks it for each lever SEPARATELY, which is what makes the answer
actionable: it refits odd-vs-even ``contest_id`` halves under flat / pooled /
SPM-prior / both and reports the sampling coverage of ``orapm``, ``drapm`` and
``rapm_net``. Every pooled season is split by the SAME parity, so the two halves
share no possession; the SPM prior is refit per half from that half's games
only, because a prior fitted on all the games would see the other half and the
coverage would be inflated by exactly the leak the split is there to avoid.

Observed (2026-09-02) -- and the reason the producer's default is ``pooled`` and
not ``pooled_spm``::

    mbb 2024   flat 0.9465 0.9561 0.9517   pooled 0.9604 0.9724 0.9660
               spm  0.7979 0.9136 0.8259   both   0.8419 0.9375 0.8650
    mbb 2019   flat 0.9545 0.9536 0.9542   pooled 0.9674 0.9688 0.9634
               spm  0.8152 0.9187 0.8473   both   0.8525 0.9369 0.8798

The SPM prior fails, and structurally rather than by a tuning miss:
``solve_rapm_league`` treats the prior mean ``b0`` as a fixed constant, so the
published SE describes ``beta - b0`` only. ``b0`` is itself estimated from this
season's box scores, so a refit on other games moves it too and the split-half
spread is wider than the SE admits (z-sd 1.39-1.53 against a nominal 1.0).
Publishing it would ship intervals ~35% too narrow. Propagating ``Var(b0)`` into
the posterior covariance is the fix; until then the lever's point estimates are
better and its uncertainty is not publishable.

Usage::

    uv run python ops/experiments/rapm_se_calibration.py --league mbb --season 2024
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl
from sportsdataverse.mbb.mbb_ncaa_rapm_league import (
    DEFAULT_RIDGE_LAMBDA,
    aggregate_stints,
    season_slice,
    solve_rapm_league,
    split_half_se_check,
    stack_seasons,
)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
from build_rapm_league import (  # noqa: E402
    DECAY,
    MULTI_YEAR_WINDOW,
    SE_SAMPLING_COVERAGE_BAND,
    USABLE_FRACTION_FLOOR,
    person_bridge,
    resolve_season,
)
from rapm_stabilization import (  # noqa: E402
    SPM_SHRINK_GRID,
    _exposure,
    _file,
    _fit,
    box_features,
    fit_spm,
    spm_prior,
)

#: The exposure shrink each league's development grid chose (rapm_stabilization).
SHRINK_K = {"mbb": 100.0, "wbb": 0.0}
assert set(SHRINK_K.values()) <= set(SPM_SHRINK_GRID), (
    "shrink k must come from the frozen grid"
)


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--league", default="mbb", choices=("mbb", "wbb"))
    ap.add_argument("--season", type=int, required=True)
    a = ap.parse_args(argv)
    lg, season = a.league, a.season
    decay, k = DECAY[lg], SHRINK_K[lg]

    bridge = person_bridge(lg)
    target = resolve_season(lg, season, bridge)
    if target is None:
        raise SystemExit(f"{lg} {season}: inputs missing")

    pool_res = {}
    for s in range(season - MULTI_YEAR_WINDOW + 1, season):
        got = resolve_season(lg, s, bridge)
        if got is not None and got["usable_fraction"] >= USABLE_FRACTION_FLOOR:
            pool_res[s] = got["resolved"]
    if len(pool_res) != MULTI_YEAR_WINDOW - 1:
        raise SystemExit(f"{lg} {season}: no full pool -- this season publishes flat")

    baselines = {}
    for s in range(season - 3, season):
        if (
            _file(lg, "possessions", s).is_file()
            and _file(lg, "player_box", s).is_file()
        ):
            got = resolve_season(lg, s, bridge)
            if got is not None and got["usable_fraction"] >= USABLE_FRACTION_FLOOR:
                baselines[s] = _fit(got["stints"])[0]
    spm = fit_spm(lg, season, bridge, baselines)

    def make(use_pool: bool, use_prior: bool):
        def refit(part: pl.DataFrame, half: int):
            st = aggregate_stints(part)
            design = st
            if use_pool:
                design = stack_seasons(
                    {
                        **{
                            s: aggregate_stints(
                                r.filter(pl.col("contest_id") % 2 == half)
                            )
                            for s, r in pool_res.items()
                        },
                        season: st,
                    },
                    season,
                    decay,
                )
            prior = None
            if use_prior:
                ids = set(part.get_column("contest_id").unique().to_list())
                prior = spm_prior(
                    spm,
                    box_features(lg, season, bridge, ids),
                    _exposure(st),
                    k,
                )
            fitted, info = solve_rapm_league(
                design, ridge_lambda=DEFAULT_RIDGE_LAMBDA, prior_mean=prior
            )
            return (season_slice(fitted, st) if use_pool else fitted), info

        return refit

    lo, hi = SE_SAMPLING_COVERAGE_BAND
    print(
        f"{lg} {season} gate-5(d) sampling-SE coverage, band [{lo}, {hi}]", flush=True
    )
    for name, (p, q) in {
        "flat": (False, False),
        "pooled": (True, False),
        "spm_prior": (False, True),
        "pooled_spm": (True, True),
    }.items():
        _pp, s = split_half_se_check(
            target["resolved"], ridge_lambda=DEFAULT_RIDGE_LAMBDA, refit=make(p, q)
        )
        cov = [s[f"coverage_sampling_{c}"] for c in ("orapm", "drapm", "rapm_net")]
        verdict = "PASS" if all(lo <= v <= hi for v in cov) else "FAIL"
        print(
            f"  {name:11s} {cov[0]:.4f} {cov[1]:.4f} {cov[2]:.4f}  "
            f"z_sd_net={s['z_sd_sampling_rapm_net']:.3f}  {verdict}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
