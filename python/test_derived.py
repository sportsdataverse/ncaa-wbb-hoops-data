"""Tests for derived.py -- the 5 non-family datasets, hermetic (real fixtures, no network)."""

import json
from pathlib import Path

import polars as pl

from ncaa_wbb_data_build.derived import (
    _key_name,
    lineup_key,
    matchup_stints,
    rosters,
    schedule,
    team_ids,
    team_rosters,
)
from ncaa_wbb_data_build.reshapers import extract_family

RAW_ROOT = Path(__file__).parent / "tests" / "fixtures" / "raw_root"
FIXTURES_DIR = RAW_ROOT / "wbb" / "json"


def _load_finals() -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(FIXTURES_DIR.glob("*.json"))
    ]


def test_team_ids_2025_season_is_non_empty():
    """Guard against a season slip silently shipping an empty team_ids dataset --
    the WBB crosswalk only covers 2009-10..2024-25, so this must stay non-empty
    for season 2025 ("2024-25") specifically, not just return a frame."""
    df = team_ids(2025)

    assert df.height > 0
    assert df.schema["id"] == pl.Utf8
    assert "team" in df.columns
    assert "season" in df.columns
    assert df.schema["season"] == pl.Int64
    assert (df.get_column("season") == 2025).all()


def test_team_ids_season_is_int64_and_joins_direct_dataset():
    """The real bug Fix 1 prevents: team_ids's season must actually JOIN
    against a DIRECT dataset's season (Int64 ending-year), not just carry
    the right dtype in isolation -- a Utf8 "2024-25" season here would
    silently zero-row every such join (pbp.join(team_ids, on="season"))."""
    finals = _load_finals()
    pbp = pl.concat(
        [
            extract_family(f, "pbp", season=2025, contest_id=f["contest_id"])
            for f in finals
        ],
        how="diagonal_relaxed",
    )
    ids = team_ids(2025)

    assert ids.schema["season"] == pl.Int64
    assert ids.get_column("season").unique().to_list() == [2025]

    joined = pbp.join(ids, on="season", how="inner")
    assert joined.height > 0


def test_team_ids_2026_season_is_populated():
    """The former ceiling, now lifted: the bundled WBB crosswalk gained its
    2025-26 rows, so season 2026 resolves like every other season. (The old
    assertion pinned `height == 0` and asked to be revisited rather than go
    stale when the crosswalk was refreshed -- this is that revisit.)"""
    df = team_ids(2026)

    assert df.height > 0
    assert df.get_column("season").unique().to_list() == [2026]
    assert df.get_column("id").null_count() == 0


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


def test_key_name_is_immune_to_source_name_format():
    """The whole point of _key_name: the box "Last, First" form and the pbp
    "FIRST.LAST" form must hash to the same signature, through suffixes,
    hyphens, apostrophes and diacritics."""
    assert _key_name("Belinga, Arielle-Vadrelle") == _key_name(
        "ARIELLEVADRELLE.BELINGA"
    )
    assert _key_name("Hall, Bree") == _key_name("BREE.HALL")
    assert _key_name("Talton Jr, Derrick") == _key_name("DERRICK.TALTON")
    assert _key_name("Je'Kel Smith") == _key_name("JEKEL.SMITH")
    assert _key_name("Núñez, Ana") == _key_name("ANA.NUNEZ")
    assert _key_name("Hall, Bree") != _key_name("BREE.HALLE")


def test_lineup_key_is_team_scoped_and_order_free():
    five = ["Hall, Bree", "Edwards, Joyce", "Dauda, Maryam", "Feagin, Sania", "X, Y"]
    k = lineup_key("South Carolina", five)

    assert k is not None and len(k) == 16
    assert lineup_key("South Carolina", list(reversed(five))) == k
    assert lineup_key(" south   carolina ", five) == k  # whitespace/case folded
    assert lineup_key("Coppin St.", five) != k  # team-scoped
    assert lineup_key("South Carolina", []) is None
    assert lineup_key(None, five) is None


def test_matchup_stints_partition_scores_exactly():
    """Every game's segment points must sum to that game's final score --
    the invariant that proves the segments partition the pbp with no
    double-counted or dropped scoring event."""
    finals = _load_finals()
    df = matchup_stints(finals, 2025)

    assert df.height > 0
    assert df.schema["contest_id"] == pl.Utf8
    assert (df.get_column("season") == 2025).all()
    assert df.get_column("home_lineup_key").null_count() == 0
    assert df.get_column("away_lineup_key").null_count() == 0
    for c in ("home_1", "home_5", "away_1", "away_5", "matchup_key", "n_events"):
        assert c in df.columns

    sched = schedule(finals, 2025)
    totals = df.group_by("contest_id").agg(
        pl.col("home_pts").sum(), pl.col("away_pts").sum()
    )
    joined = totals.join(sched, on="contest_id", how="inner", suffix="_final")
    assert joined.height == totals.height
    assert (joined.get_column("home_pts") == joined.get_column("home_score")).all()
    assert (joined.get_column("away_pts") == joined.get_column("away_score")).all()


def test_matchup_stints_skips_a_bad_game_without_aborting():
    finals = _load_finals()
    bad = {"contest_id": "ZZZ", "pbp": [{"period": 1}]}  # no on-court columns

    df = matchup_stints([*finals, bad], 2025)

    assert df.height == matchup_stints(finals, 2025).height
    assert "ZZZ" not in df.get_column("contest_id").to_list()


def test_team_rosters_reads_the_raw_checkout_tree():
    df = team_rosters(2025, RAW_ROOT)

    assert df.height > 0
    assert df.schema["team_id"] == pl.Utf8  # id discipline: Utf8 everywhere
    assert df.schema["player_id"] == pl.Utf8
    assert df.schema["season"] == pl.Int64
    assert (df.get_column("season") == 2025).all()
    assert df.get_column("team_id").to_list() == ["591724"] * df.height
    # `player` is the FIRST.LAST key that byte-matches pbp name normalization
    assert "ANGEL.JONES" in df.get_column("player").to_list()


def test_team_rosters_absent_tree_returns_the_typed_empty_frame():
    populated = team_rosters(2025, RAW_ROOT)
    empty = team_rosters(1999, RAW_ROOT)

    assert empty.height == 0
    assert empty.schema == populated.schema
