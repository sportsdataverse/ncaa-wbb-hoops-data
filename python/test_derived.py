"""Tests for derived.py -- the 3 non-family datasets, hermetic (real fixtures, no network)."""

import json
from pathlib import Path

import polars as pl

from ncaa_wbb_data_build.derived import rosters, schedule, team_ids

FIXTURES_DIR = Path(__file__).parent / "tests" / "fixtures" / "raw_root" / "wbb" / "json"


def _load_finals() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURES_DIR.glob("*.json"))]


def test_team_ids_2025_season_is_non_empty():
    """Guard against a season slip silently shipping an empty team_ids dataset --
    the WBB crosswalk only covers 2009-10..2024-25, so this must stay non-empty
    for season 2025 ("2024-25") specifically, not just return a frame."""
    df = team_ids(2025)

    assert df.height > 0
    assert df.schema["id"] == pl.Utf8
    assert "team" in df.columns
    assert "season" in df.columns
    assert (df.get_column("season") == "2024-25").all()


def test_team_ids_2026_season_is_empty():
    """Pins the known ceiling: the bundled WBB crosswalk has no 2025-26 row
    yet, so season 2026 returns 0 rows. This is expected behavior, not a
    lurking bug -- if the crosswalk is ever refreshed to cover 2025-26, this
    assertion should be revisited rather than silently going stale."""
    df = team_ids(2026)

    assert df.height == 0


def test_schedule_one_row_per_fixture_game():
    finals = _load_finals()
    df = schedule(finals, 2025)

    assert df.height == 4
    assert df.schema["contest_id"] == pl.Utf8
    assert "home" in df.columns
    assert "away" in df.columns
    assert "game_date" in df.columns
    assert (df.get_column("season") == 2025).all()

    expected_ids = {p.stem for p in FIXTURES_DIR.glob("*.json")}
    assert set(df.get_column("contest_id").to_list()) == expected_ids


def test_rosters_distinct_team_player_per_season():
    finals = _load_finals()
    df = rosters(finals, 2025)

    assert df.height > 0
    assert df.schema["team"] == pl.Utf8
    assert df.schema["player"] == pl.Utf8
    assert (df.get_column("season") == 2025).all()
    assert df.select("team", "player").is_duplicated().sum() == 0


def test_rosters_empty_and_populated_share_schema():
    """The empty fallback and the populated path must agree on dtypes --
    notably games is Int64 (n_unique returns UInt32), so the season parquet
    schema stays stable whether or not a season has games."""
    populated = rosters(_load_finals(), 2025)
    empty = rosters([], 2025)
    assert empty.height == 0
    assert empty.schema == populated.schema
    assert populated.schema["games"] == pl.Int64
    assert empty.schema["games"] == pl.Int64


def test_schedule_final_score_is_max_not_opening_row():
    """Locks in .max() of pbp home/away score -- not pbp[0] (which is 0-0 opening tip)."""
    finals = _load_finals()
    df = schedule(finals, 2025).filter(pl.col("contest_id") == "5722355")

    assert df.height == 1
    # Verified against the fixture's pbp rows: game final, South Carolina 92 - Coppin St. 60.
    assert df.get_column("home_score").item() == 92
    assert df.get_column("away_score").item() == 60


def test_schedule_and_rosters_skip_empty_family_without_raising():
    """A game with empty pbp/player_box must not abort the season build."""
    real = _load_finals()[0]
    finals = [real, {"contest_id": "ZZZ", "pbp": [], "player_box": []}]

    sched = schedule(finals, 2025)
    assert sched.height == 1
    assert "ZZZ" not in sched.get_column("contest_id").to_list()

    rost = rosters(finals, 2025)
    assert rost.height == rosters([real], 2025).height
