"""Tests for build.py -- build_season driver, hermetic (real fixtures, no network)."""

import json
from pathlib import Path

import polars as pl

from ncaa_wbb_data_build import reshapers
from ncaa_wbb_data_build.build import build_season

RAW_ROOT = Path(__file__).parent / "fixtures" / "raw_root"
JSON_DIR = RAW_ROOT / "wbb" / "json"


def _fixture_family_height(family: str) -> int:
    total = 0
    for p in JSON_DIR.glob("*.json"):
        final = json.loads(p.read_text(encoding="utf-8"))
        total += len(final.get(family) or [])
    return total


def test_build_season_pbp_direct(tmp_path: Path):
    out = build_season("pbp", 2025, base=tmp_path, raw_root=RAW_ROOT)

    assert out.height == _fixture_family_height("pbp")
    assert out.select("contest_id").n_unique() == 4
    assert out.schema["contest_id"] == pl.Utf8
    assert (out.get_column("season") == 2025).all()

    pq = tmp_path / "wbb" / "pbp" / "parquet" / "pbp_2025.parquet"
    assert pq.exists()
    assert pl.read_parquet(pq).height == out.height


def test_build_season_shots_direct(tmp_path: Path):
    out = build_season("shots", 2025, base=tmp_path, raw_root=RAW_ROOT)

    assert out.height == _fixture_family_height("shots")

    pq = tmp_path / "wbb" / "shots" / "parquet" / "shots_2025.parquet"
    assert pq.exists()
    assert pl.read_parquet(pq).height == out.height


def test_build_season_schedule_derived(tmp_path: Path):
    out = build_season("schedule", 2025, base=tmp_path, raw_root=RAW_ROOT)

    assert out.height == 4
    pq = tmp_path / "wbb" / "schedule" / "parquet" / "schedule_2025.parquet"
    assert pq.exists()


def test_build_season_team_ids_derived(tmp_path: Path):
    out = build_season("team_ids", 2025, base=tmp_path, raw_root=RAW_ROOT)

    assert out.height > 300
    pq = tmp_path / "wbb" / "team_ids" / "parquet" / "team_ids_2025.parquet"
    assert pq.exists()


def test_build_season_no_contest_ids_returns_empty_and_writes_nothing(tmp_path: Path):
    out = build_season("pbp", 1999, base=tmp_path, raw_root=RAW_ROOT)

    assert out.height == 0
    assert not (tmp_path / "wbb" / "pbp").exists()


def test_build_season_contest_id_is_sorted(tmp_path: Path):
    """Locks in the DIRECT-path contest_id sort in build._build_direct."""
    out = build_season("pbp", 2025, base=tmp_path, raw_root=RAW_ROOT)

    assert out.get_column("contest_id").is_sorted()


def test_build_season_skips_one_bad_game_not_whole_season(tmp_path: Path, monkeypatch):
    """A game whose extract_family raises must be skipped, not abort the season."""
    bad_cid = next(p.stem for p in JSON_DIR.glob("*.json"))
    real_extract = reshapers.extract_family

    def _flaky_extract(final, family, **kwargs):
        if kwargs.get("contest_id") == bad_cid:
            raise ValueError("simulated extract failure")
        return real_extract(final, family, **kwargs)

    monkeypatch.setattr(reshapers, "extract_family", _flaky_extract)

    out = build_season("pbp", 2025, base=tmp_path, raw_root=RAW_ROOT)

    good_games_height = _fixture_family_height("pbp") - len(
        json.loads((JSON_DIR / f"{bad_cid}.json").read_text(encoding="utf-8")).get(
            "pbp"
        )
        or []
    )
    assert out.height == good_games_height
    assert bad_cid not in out.get_column("contest_id").to_list()
