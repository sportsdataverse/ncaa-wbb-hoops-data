"""Tests for reshapers.py -- direct family extractor, hermetic (real fixture, no network)."""

import json
from pathlib import Path

import polars as pl

from ncaa_wbb_data_build.reshapers import extract_family

FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "raw_root" / "wbb" / "json" / "5722355.json"

FAMILY_HEIGHTS = {
    "pbp": 460,
    "lineups": 44,
    "player_box": 22,
    "team_box": 2,
    "shots": 129,
    "possessions": 142,
}


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_extract_family_all_six_families_from_real_fixture():
    final = _load_fixture()
    for fam, expected_height in FAMILY_HEIGHTS.items():
        df = extract_family(final, fam, season=2025, contest_id="5722355")
        assert df.height == expected_height, f"{fam}: expected {expected_height}, got {df.height}"
        assert df.height > 0
        assert "contest_id" in df.columns
        assert "season" in df.columns
        assert df.schema["contest_id"] == pl.Utf8
        assert (df.get_column("contest_id") == "5722355").all()
        assert (df.get_column("season") == 2025).all()


def test_extract_family_empty_family_is_concat_safe():
    df = extract_family({"pbp": []}, "pbp", season=2025, contest_id="X")

    assert df.height == 0
    assert "contest_id" in df.columns
    assert "season" in df.columns
    assert df.schema["contest_id"] == pl.Utf8


def test_extract_family_empty_and_nonempty_concat_diagonal_relaxed():
    final = _load_fixture()
    non_empty = extract_family(final, "pbp", season=2025, contest_id="5722355")
    empty = extract_family({"pbp": []}, "pbp", season=2025, contest_id="X")

    out = pl.concat([empty, non_empty], how="diagonal_relaxed")

    assert out.height == non_empty.height
