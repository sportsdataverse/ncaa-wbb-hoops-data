"""Dataset registry -- one row per released NCAA WBB dataset.

``REGISTRY`` maps dataset key -> ``DatasetSpec``. Six datasets are DIRECT
extracts of a top-level key in the parsed-JSON payload (``family`` set);
three are DERIVED from other datasets (``family`` is None).
"""

from __future__ import annotations

from dataclasses import dataclass

_T = "ncaa_wbb_"

# Sibling wehoop-dev/ncaa-wbb-hoops-raw checkout root (Task 3 ingest reads this).
RAW_ROOT_ENV = "NCAA_WBB_RAW_ROOT"

# HTTP fallback base when the sibling raw checkout isn't available locally
# (Task 3 ingest).
RAW_HTTP_BASE = (
    "https://raw.githubusercontent.com/sportsdataverse/ncaa-wbb-hoops-raw/main/wbb"
)


@dataclass(frozen=True)
class DatasetSpec:
    """How to build one released dataset.

    Attributes:
        dataset: directory name under ``wbb/`` and the manifest key.
        stem: output file stem (``{stem}_{season}.parquet`` / ``.csv``).
        tag: the ``sportsdataverse-data`` release tag (load-bearing).
        family: parsed-JSON top-level key this dataset is extracted from,
            for the 6 DIRECT datasets. None for the 3 DERIVED datasets,
            which are built from other datasets rather than extracted
            directly from a parsed-JSON family.
        csv_suffix: release csv extension.
    """

    dataset: str
    stem: str
    tag: str
    family: str | None
    csv_suffix: str = ".csv"


REGISTRY: dict[str, DatasetSpec] = {
    # DIRECT: family == dataset key (parsed-JSON key equals the dataset key).
    "pbp": DatasetSpec("pbp", "pbp", _T + "pbp", "pbp"),
    "lineups": DatasetSpec("lineups", "lineups", _T + "lineups", "lineups"),
    "possessions": DatasetSpec(
        "possessions", "possessions", _T + "possessions", "possessions"
    ),
    "player_box": DatasetSpec(
        "player_box", "player_box", _T + "player_box", "player_box"
    ),
    "team_box": DatasetSpec("team_box", "team_box", _T + "team_box", "team_box"),
    "shots": DatasetSpec("shots", "shots", _T + "shots", "shots"),
    # DERIVED: no parsed-JSON family, built from other datasets.
    "matchup_stints": DatasetSpec(
        "matchup_stints", "matchup_stints", _T + "matchup_stints", None
    ),
    "team_rosters": DatasetSpec(
        "team_rosters", "team_rosters", _T + "team_rosters", None
    ),
    "schedule": DatasetSpec("schedule", "schedule", _T + "schedule", None),
    "rosters": DatasetSpec("rosters", "rosters", _T + "rosters", None),
    "team_ids": DatasetSpec("team_ids", "team_ids", _T + "team_ids", None),
}
