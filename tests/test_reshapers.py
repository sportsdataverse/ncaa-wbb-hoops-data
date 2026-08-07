"""Tests for reshapers.py -- direct family extractor, hermetic (real fixture, no network)."""

import json
from pathlib import Path

import polars as pl

from ncaa_wbb_data_build.reshapers import extract_family

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "raw_root"
    / "wbb"
    / "json"
    / "5722355.json"
)

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
        assert df.height == expected_height, (
            f"{fam}: expected {expected_height}, got {df.height}"
        )
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


def test_lineups_flatten_real_shape():
    """Nested engine lineup row -> all-scalar flat row; absent branches -> None."""
    from ncaa_wbb_data_build.reshapers import _flatten_lineup_row

    row = {
        "date": "2024-11-14T17:00:00",
        "location_type": "Home",
        "start_min": 0.0,
        "end_min": 3.47,
        "duration_mins": 3.47,
        "score_info": {
            "start": {"scored": 0, "allowed": 0},
            "end": {"scored": 6, "allowed": 4},
            "start_diff": 0,
            "end_diff": 2,
        },
        "team": {"team": {"name": "South Carolina"}, "year": {"value": 2024}},
        "opponent": {"team": {"name": "Coppin St."}, "year": {"value": 2024}},
        "lineup_id": {"value": "abc"},
        "players": [
            {"code": "p1", "id": {"name": "Hall, Bree"}, "ncaa_id": None},
            {"code": "p2", "id": {"name": "Edwards, Joyce"}, "ncaa_id": None},
            {"code": "p3", "id": {"name": "Dauda, Maryam"}, "ncaa_id": None},
            {"code": "p4", "id": {"name": "Fulwiley, MiLaysia"}, "ncaa_id": None},
            {"code": "p5", "id": {"name": "Feagin, Sania"}, "ncaa_id": None},
        ],
        "players_in": [],
        "players_out": [],
        "team_stats": {
            "num_events": 10,
            "num_possessions": 8,
            "pts": 6,
            "plus_minus": 2,
            "fg": {"attempts": {"total": 7}, "made": {"total": 3}, "ast": None},
            "fg_rim": {
                "attempts": {"total": 3},
                "made": {"total": 2},
                "ast": {"total": 1},
            },
            "orb": {"total": 1},
            "to": {"total": 2},
        },
        # opponent_stats ABSENT on purpose -- absent branch must yield Nones
        "player_count_error": None,
    }
    flat = _flatten_lineup_row(row)
    assert all(not isinstance(v, (dict, list)) for v in flat.values())
    assert flat["team"] == "South Carolina" and flat["opponent"] == "Coppin St."
    # sorted ("Last, First" -> last-name order)
    assert flat["player_1"] == "Dauda, Maryam" and flat["player_5"] == "Hall, Bree"
    assert flat["pts"] == 6 and flat["fga"] == 7 and flat["rim_ast"] == 1
    assert flat["opp_pts"] is None and flat["opp_fga"] is None
    assert flat["players_in"] is None  # empty list -> None, not ""

    # end-to-end through extract_family: flat frame, no Struct/List dtypes
    df = extract_family(
        {"lineups": [row]}, "lineups", season=2025, contest_id="5722355"
    )
    assert df.height == 1
    assert all(t.base_type() not in (pl.Struct, pl.List) for t in df.dtypes)
    assert df.get_column("contest_id").to_list() == ["5722355"]
    assert df.get_column("stint_num").to_list() == [1]
    assert df.get_column("lineup_key").item() is not None


def test_lineups_from_real_fixture_are_flat_and_keyed():
    """The real 44-stint fixture game: every column scalar, keys/stints stamped."""
    df = extract_family(_load_fixture(), "lineups", season=2025, contest_id="5722355")

    assert all(t.base_type() not in (pl.Struct, pl.List) for t in df.dtypes)
    assert df.get_column("lineup_key").null_count() == 0
    # stint_num is a per-team ordinal over start_min: 1..n within each team
    for (_team,), g in df.group_by("team"):
        assert sorted(g.get_column("stint_num").to_list()) == list(
            range(1, g.height + 1)
        )


def test_augment_pbp_flags_against_real_fixture():
    """Locks the event_description grammar on real WBB events (2007 in the tree)."""
    df = extract_family(_load_fixture(), "pbp", season=2025, contest_id="5722355")

    for col in ("is_fastbreak", "is_paint", "is_from_turnover", "is_second_chance"):
        assert df.schema[col] == pl.Boolean
        assert df.get_column(col).null_count() == 0  # fill_null(False)
        assert df.get_column(col).sum() > 0, f"{col}: never True on a real game"

    # "<shooter>, ... made - <name>, assist"
    assert df.get_column("assist_player").drop_nulls().len() > 0
    # "freethrow NofM" -> 1 <= ft_number <= ft_attempts
    ft = df.filter(pl.col("ft_number").is_not_null())
    assert ft.height > 0
    assert (ft.get_column("ft_number") >= 1).all()
    assert (ft.get_column("ft_number") <= ft.get_column("ft_attempts")).all()
    # foul_class only takes the four documented values
    assert set(df.get_column("foul_class").drop_nulls().unique().to_list()) <= {
        "personal",
        "offensive",
        "technical",
        "adminTechnical",
    }
    # "Team, turnover shotclock team;" -- team turnovers are a subset of turnovers
    tt = df.filter(pl.col("is_team_turnover") == True)  # noqa: E712
    assert tt.height > 0
    assert tt.get_column("turnover_type").null_count() == 0


def test_lineup_key_joins_the_pbp_derived_matchup_stints():
    """lineup_key is THE join key of the lineup index: the keys reshapers
    stamps on the BOX-derived lineups rows ("Last, First" names) must land on
    the keys derived.matchup_stints derives from the PBP on-court columns
    ("FIRST.LAST" names) -- the whole point of _key_name."""
    import json

    from ncaa_wbb_data_build.derived import matchup_stints

    finals = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(FIXTURE.parent.glob("*.json"))
    ]
    stints = matchup_stints(finals, 2025)
    lineups = pl.concat(
        [
            extract_family(f, "lineups", season=2025, contest_id=str(f["contest_id"]))
            for f in finals
        ],
        how="diagonal_relaxed",
    )

    known = set(lineups.get_column("lineup_key").drop_nulls().to_list())
    seen = set(stints.get_column("home_lineup_key").to_list()) | set(
        stints.get_column("away_lineup_key").to_list()
    )
    assert len(seen & known) / len(seen) > 0.8, "lineup_key join rate collapsed"
