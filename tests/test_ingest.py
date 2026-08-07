"""Tests for ingest.py -- LOCAL mode, plus hermetic HTTP-branch tests that
stub ``requests.get`` (no real network)."""

import io
import json

import polars as pl

from ncaa_wbb_data_build.ingest import read_parsed, season_contest_ids

PARSED = {
    "contest_id": "12345",
    "pbp": [{"a": 1}],
    "lineups": [],
    "player_box": [{"b": 2}],
    "team_box": [{"c": 3}],
    "shots": [],
    "possessions": [{"d": 4}],
}


def test_read_parsed_returns_exact_dict(tmp_path):
    json_dir = tmp_path / "wbb" / "json"
    json_dir.mkdir(parents=True)
    (json_dir / "12345.json").write_text(json.dumps(PARSED), encoding="utf-8")

    result = read_parsed("12345", raw_root=tmp_path)

    assert result == PARSED
    assert isinstance(result["contest_id"], str)


def test_read_parsed_missing_file_returns_none(tmp_path):
    assert read_parsed("00000", raw_root=tmp_path) is None


def test_read_parsed_malformed_json_returns_none(tmp_path):
    json_dir = tmp_path / "wbb" / "json"
    json_dir.mkdir(parents=True)
    (json_dir / "99999.json").write_text("{not valid json", encoding="utf-8")

    assert read_parsed("99999", raw_root=tmp_path) is None


def _master_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "contest_id": ["b", "a", "c"],
            "season": ["2025", "2025", "2024"],
            "captured": ["true", "true", "true"],
        },
        schema={"contest_id": pl.Utf8, "season": pl.Utf8, "captured": pl.Utf8},
    )


def test_season_contest_ids_filters_and_sorts(tmp_path):
    (tmp_path / "wbb").mkdir()
    _master_df().write_parquet(tmp_path / "wbb" / "wbb_schedule_master.parquet")

    ids = season_contest_ids(2025, raw_root=tmp_path)

    assert ids == ["a", "b"]
    assert all(isinstance(i, str) for i in ids)


def test_season_contest_ids_legacy_unprefixed_name_fallback(tmp_path):
    # The raw repo still writes the pre-D33 unprefixed name; the reader must
    # keep working against it until the writer renames.
    (tmp_path / "wbb").mkdir()
    _master_df().write_parquet(tmp_path / "wbb" / "schedule_master.parquet")

    assert season_contest_ids(2025, raw_root=tmp_path) == ["a", "b"]


def test_season_contest_ids_missing_parquet_returns_empty(tmp_path):
    assert season_contest_ids(2025, raw_root=tmp_path) == []


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code


def test_read_parsed_http_honors_custom_raw_root(monkeypatch, tmp_path):
    """Fix 4: an explicit URL raw_root= must drive the HTTP fetch -- previously
    the HTTP branch hardcoded config.RAW_HTTP_BASE and silently discarded it."""
    monkeypatch.setenv("NCAA_WBB_CACHE", str(tmp_path / "cache"))
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _FakeResponse(json.dumps(PARSED).encode("utf-8"))

    monkeypatch.setattr("requests.get", fake_get)

    result = read_parsed("12345", raw_root="https://example.com/custom/wbb")

    assert calls == ["https://example.com/custom/wbb/json/12345.json"]
    assert result == PARSED


def test_season_contest_ids_http_honors_custom_raw_root(monkeypatch):
    """Fix 4, season_contest_ids side of the same bug."""
    df = pl.DataFrame(
        {
            "contest_id": ["b", "a"],
            "season": ["2025", "2025"],
            "captured": ["true", "true"],
        },
        schema={"contest_id": pl.Utf8, "season": pl.Utf8, "captured": pl.Utf8},
    )
    buf = io.BytesIO()
    df.write_parquet(buf)
    parquet_bytes = buf.getvalue()
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _FakeResponse(parquet_bytes)

    monkeypatch.setattr("requests.get", fake_get)

    ids = season_contest_ids(2025, raw_root="https://example.com/custom/wbb")

    # The prefixed D33 name is tried first (and here found first).
    assert calls == ["https://example.com/custom/wbb/wbb_schedule_master.parquet"]
    assert ids == ["a", "b"]


def test_read_parsed_http_default_falls_back_to_raw_http_base(monkeypatch, tmp_path):
    """No raw_root= -> falls back to whatever NCAA_WBB_RAW_ROOT resolves to
    (RAW_HTTP_BASE in production) unchanged, same as before Fix 4."""
    from ncaa_wbb_data_build.config import RAW_HTTP_BASE

    monkeypatch.setenv("NCAA_WBB_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("NCAA_WBB_RAW_ROOT", RAW_HTTP_BASE)
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _FakeResponse(json.dumps(PARSED).encode("utf-8"))

    monkeypatch.setattr("requests.get", fake_get)

    result = read_parsed("12345")

    assert calls == [f"{RAW_HTTP_BASE}/json/12345.json"]
    assert result == PARSED
