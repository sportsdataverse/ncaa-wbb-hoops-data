"""The pooled RAPM estimator's leakage boundary and its season-``t`` frame contract.

A multi-season fit is the point at which "season ``t``'s rating" can quietly
become "season ``t``'s rating, with hindsight". Two properties have to hold, and
prose in a docstring is not evidence of either:

1. **No possession or box-score input for a season after ``t`` reaches the fit
   for ``t``** -- proved by instrumenting every input read of a REAL season
   across a whole ``run_season`` and checking the season set, not by reading the
   code. The claim is scoped on purpose: the cross-season identity bridge IS
   built from every roster season, including seasons after ``t``, so the spy is
   cleared after ``person_bridge`` and a ``person_id`` merge can in principle be
   informed by a later roster. That channel carries identity only, never
   performance data. Narrowing the bridge to seasons ``<= t`` is open work, not
   something this test currently proves.
2. **The published season-``t`` frame is season ``t``'s** -- a pooled fit rates
   everyone in the window on window-length exposure, so the per-season asset must
   be cut back to season-``t`` participants carrying season-``t`` possessions.

Test 1 touches this repo's real published trees and is skipped when they are not
checked out; it runs a full survey-mode fit, so it costs a few minutes on a
pooled season. Test 2 is exact on synthetic frames, where "this player played
only in the previous season" can be stated unambiguously.

The whole module is skipped when the installed ``sportsdataverse`` predates the
pooled-estimator helpers: the producer imports them at module scope, so without
them there is nothing here to test and a collection error would say so far less
clearly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"


def _load_build():
    sys.path.insert(0, str(OPS))
    spec = importlib.util.spec_from_file_location(
        "build_rapm_league", OPS / "build_rapm_league.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


try:
    bl = _load_build()
except ImportError as exc:  # pragma: no cover - environment-dependent
    pytest.skip(
        f"the pooled estimator needs a newer sportsdataverse ({exc}); re-lock with "
        "`uv lock --upgrade-package sportsdataverse` once sportsdataverse-py#441 "
        "is on main",
        allow_module_level=True,
    )

LEAGUE = "mbb" if (ROOT / "mbb").is_dir() else "wbb"
TARGET = 2019
_HAVE_DATA = bl._data_file(LEAGUE, "possessions", TARGET + 1).is_file()


@pytest.mark.skipif(
    not _HAVE_DATA, reason="needs this repo's published trees checked out"
)
def test_no_season_after_the_target_is_ever_read(monkeypatch, tmp_path):
    """Instrument EVERY input read of a real ``run_season`` and check the season set.

    ``_data_file`` is the single door to every input this pipeline has
    (possessions, team_rosters, player_box, name_changes), so recording its
    season argument records everything the fit could possibly have seen. The
    seasons AFTER the target are present on disk -- the assertion is that the
    build does not touch them, not that they are unavailable.

    Survey mode is used so the run computes every gate and writes nothing; it
    still performs the whole fit, including the split-half refit's per-predecessor
    re-resolve, which is exactly the read surface a `choose_estimator`-only check
    would miss.
    """
    seen: set[int] = set()
    real = bl._data_file

    def spy(league, dataset, season=None):
        if season is not None:
            seen.add(int(season))
        return real(league, dataset, season)

    monkeypatch.setattr(bl, "_data_file", spy)
    bridge = bl.person_bridge(LEAGUE)
    # The bridge reads every roster season by construction, INCLUDING seasons
    # after the target; clearing here is what scopes this test to the
    # possession/box-score inputs. See the module docstring -- the scope is
    # deliberate and disclosed, not an oversight being hidden by a clear().
    seen.clear()
    # One cache for both calls: choose_estimator resolves the predecessors and
    # run_season would otherwise resolve them again, doubling the slowest part of
    # this test for no extra coverage. The spy still records every read.
    cache: dict = {}
    chosen = bl.choose_estimator(LEAGUE, TARGET, bridge, cache)
    passed, _rec = bl.run_season(
        LEAGUE, TARGET, tmp_path, bridge, bl.SPEARMAN_FLOOR[LEAGUE], cache, survey=True
    )
    assert passed, (
        "the survey run must clear every gate for this assertion to mean anything"
    )
    assert not list(tmp_path.iterdir()), "survey mode must write nothing"

    future = {s for s in seen if s > TARGET}
    assert not future, f"the fit for {TARGET} read future seasons {sorted(future)}"
    if LEAGUE in bl.POOLED_LEAGUES:
        assert chosen["estimator"] == "pooled"
        assert sorted(chosen["pool"]) == [TARGET - 2, TARGET - 1]
        assert seen >= {TARGET - 2, TARGET - 1, TARGET}, (
            "a pooled run must actually read its predecessors"
        )
    else:
        # A league that does not pool must not even look at a predecessor's
        # possessions -- the leakage claim is then trivially true, and this
        # branch exists so the test still fails if that stops being so.
        assert chosen["estimator"] == "flat" and not chosen["pool"]


def _stints(ids, n_poss, pts):
    """One stint frame: ``ids`` are the five offensive players, defence is fixed."""
    return pl.DataFrame(
        {
            "off_ids": [ids],
            "def_ids": [["d1", "d2", "d3", "d4", "d5"]],
            "off_team": ["A"],
            "def_team": ["B"],
            "is_home_offense": [True],
            "n_poss": [n_poss],
            "pts": [pts],
        },
        schema_overrides={"off_ids": pl.List(pl.Utf8), "def_ids": pl.List(pl.Utf8)},
    )


def test_stacking_a_future_season_raises():
    """The engine refuses it; this pins that the producer inherits the refusal."""
    from sportsdataverse.mbb.mbb_ncaa_rapm_league import stack_seasons

    per = {2018: _stints(["a", "b", "c", "d", "e"], 100, 100)}
    per[2019] = per[2018]
    per[2020] = per[2018]
    with pytest.raises(ValueError, match="after target 2019"):
        stack_seasons(per, 2019, 0.5)


def test_published_frame_is_season_t_participants_on_season_t_exposure():
    from sportsdataverse.mbb.mbb_ncaa_rapm_league import (
        season_slice,
        solve_rapm_league,
        stack_seasons,
        stint_exposure,
    )

    gone = ["a", "b", "c", "d", "gone"]  # "gone" played only in 2018
    now = ["a", "b", "c", "d", "here"]  # "here" only in 2019
    prev = pl.concat([_stints(gone, 400, 400), _stints(now[:4] + ["x"], 400, 380)])
    cur = pl.concat([_stints(now, 300, 330), _stints(now[:4] + ["x"], 300, 300)])

    pooled = stack_seasons({2018: prev, 2019: cur}, 2019, 0.5)
    players, _info = solve_rapm_league(pooled, ridge_lambda=100.0, compute_se=False)
    assert "gone" in players["player_id"].to_list(), "the pooled fit does rate him"

    out = season_slice(players, cur)
    assert "gone" not in out["player_id"].to_list()
    assert "here" in out["player_id"].to_list()

    # Exposure is season 2019's, not the two-season sum. "a" played 600 offensive
    # possessions in 2019 and 800 in 2018; the pooled frame says 1400.
    pooled_a = players.filter(pl.col("player_id") == "a")["off_poss"].item()
    sliced_a = out.filter(pl.col("player_id") == "a")["off_poss"].item()
    assert pooled_a == 1400
    assert sliced_a == 600
    want = stint_exposure(cur).sort("player_id")
    got = out.select("player_id", "off_poss", "def_poss").sort("player_id")
    assert got.equals(
        want.select("player_id", "off_poss", "def_poss").sort("player_id")
    )
