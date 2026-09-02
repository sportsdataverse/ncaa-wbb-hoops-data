"""The stabilization summariser must refuse anything that is not the registered run.

These guards exist because the summariser's output is read as a pre-registered
verdict. Every way a record set can look registered without being registered is
covered here: a partial season set, re-tuned hyperparameters, and malformed
fields (a JSON string ``"false"`` is truthy, so a presence-only check would score
it). Synthetic records are correct for this file -- it tests the VALIDATION, not
any model number.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[1] / "ops" / "experiments"


def _load(name: str):
    sys.path.insert(0, str(OPS))
    spec = importlib.util.spec_from_file_location(name, OPS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


summarize = _load("summarize_rapm_stabilization")
harness = _load("rapm_stabilization")
LEAGUE = harness.FROZEN_HYPERPARAMS and next(iter(sorted(harness.FROZEN_HYPERPARAMS)))


def _record(season: int, league: str, **over):
    decay, shrink_k = harness.FROZEN_HYPERPARAMS[league]
    rec = {
        "season": season,
        "league": league,
        "decay": decay,
        "shrink_k": shrink_k,
        "frozen": True,
        "variants": {},
    }
    rec.update(over)
    return rec


def _write(tmp_path: Path, recs: list) -> str:
    p = tmp_path / "r.json"
    p.write_text(json.dumps(recs), encoding="utf-8")
    return str(p)


def _registered(league: str) -> list:
    return [_record(s, league) for s in harness.EVAL_SEASONS]


@pytest.mark.parametrize("league", sorted(harness.FROZEN_HYPERPARAMS))
def test_registered_run_passes_every_protocol_check(league):
    assert summarize._protocol_violations(_registered(league), league) == []


def test_partial_season_set_is_refused():
    league = LEAGUE
    recs = _registered(league)[:3]
    problems = summarize._protocol_violations(recs, league)
    assert any("seasons incomplete" in p for p in problems)


def test_retuned_hyperparameters_are_refused():
    league = LEAGUE
    recs = [_record(s, league, decay=0.9, frozen=False) for s in harness.EVAL_SEASONS]
    problems = summarize._protocol_violations(recs, league)
    assert len(problems) >= 2  # both the frozen flag and the pair mismatch


def test_string_false_frozen_is_rejected_not_scored(tmp_path):
    # "false" is a truthy string: a presence-only check would let it through.
    recs = [_record(s, LEAGUE, frozen="false") for s in harness.EVAL_SEASONS]
    with pytest.raises(SystemExit, match="JSON boolean"):
        summarize.load([_write(tmp_path, recs)])


def test_non_string_league_is_rejected(tmp_path):
    recs = [dict(_record(s, LEAGUE), league=["mbb"]) for s in harness.EVAL_SEASONS]
    with pytest.raises(SystemExit, match="must be a string"):
        summarize.load([_write(tmp_path, recs)])


def test_unknown_league_is_rejected(tmp_path):
    recs = [dict(_record(s, LEAGUE), league="nba") for s in harness.EVAL_SEASONS]
    with pytest.raises(SystemExit, match="unknown league"):
        summarize.load([_write(tmp_path, recs)])


def test_empty_input_is_rejected_not_divided_by_zero():
    with pytest.raises(SystemExit, match="usage:"):
        summarize.load([])


def test_records_missing_the_stamp_are_rejected(tmp_path):
    recs = [{"season": s, "variants": {}} for s in harness.EVAL_SEASONS]
    with pytest.raises(SystemExit, match="predate"):
        summarize.load([_write(tmp_path, recs)])
