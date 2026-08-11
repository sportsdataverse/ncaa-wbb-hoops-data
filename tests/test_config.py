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
        assert spec.stem == "ncaa_wbb_" + dataset


def test_raw_sources_point_at_this_league_never_the_twin():
    """The raw root must name THIS repo's league on both path segments.

    Regression: a twin-port that rewrote only the ``ncaa_<lg>_`` tokens left
    ``RAW_HTTP_BASE`` ending in the OTHER league's tree
    (``.../ncaa-wbb-hoops-raw/main/mbb``), which would have fed MBB games to
    the WBB producer through the HTTP fallback. Nothing caught it: the tag
    check above only inspects tags, and the offline suite never exercises the
    fallback. Assert the whole string, not a prefix.
    """
    from ncaa_wbb_data_build import config

    league = "wbb"
    assert config.RAW_HTTP_BASE.endswith(f"/{league}"), (
        f"RAW_HTTP_BASE must end with the {league!r} tree, got {config.RAW_HTTP_BASE!r}"
    )
    assert f"ncaa-{league}-hoops-raw" in config.RAW_HTTP_BASE
    assert f"ncaa-{'mbb' if league == 'wbb' else 'wbb'}-hoops-raw" not in config.RAW_HTTP_BASE
    assert config.RAW_ROOT_ENV == f"NCAA_{league.upper()}_RAW_ROOT"
