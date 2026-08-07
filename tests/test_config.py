"""Tests for the NCAA WBB dataset REGISTRY (config.py)."""

from ncaa_wbb_data_build.config import REGISTRY

DIRECT = {"pbp", "lineups", "possessions", "player_box", "team_box", "shots"}
DERIVED = {"matchup_stints", "team_rosters", "schedule", "rosters", "team_ids"}
EXPECTED = DIRECT | DERIVED


def test_registry_has_exactly_eleven_expected_datasets():
    assert len(REGISTRY) == 11
    assert set(REGISTRY) == EXPECTED


def test_all_tags_are_ncaa_wbb_and_never_espn_or_mbb():
    for spec in REGISTRY.values():
        assert spec.tag.startswith("ncaa_wbb_")
        assert "espn_" not in spec.tag
        assert "mbb" not in spec.tag


def test_direct_datasets_have_family_equal_to_dataset_key():
    for dataset in DIRECT:
        assert REGISTRY[dataset].family == dataset


def test_derived_datasets_have_no_family():
    for dataset in DERIVED:
        assert REGISTRY[dataset].family is None


def test_tag_and_stem_derive_from_dataset_key():
    for dataset, spec in REGISTRY.items():
        assert spec.tag == "ncaa_wbb_" + dataset
        assert spec.stem == dataset
