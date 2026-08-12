"""Dataset registry -- one row per released NCAA WBB dataset.

``REGISTRY`` maps dataset key -> ``DatasetSpec``. Six datasets are DIRECT
extracts of a top-level key in the parsed-JSON payload (``family`` set); the
other five are DERIVED (``family`` is None) -- built from the parsed payloads,
the raw roster files, or the crosswalk rather than extracted from one family.
No dataset is built from another dataset's OUTPUT; see the note above
``REGISTRY`` for what its order does and does not mean.
"""

from __future__ import annotations

from dataclasses import dataclass

_T = "ncaa_wbb_"

# Sibling hoopR-dev/ncaa-wbb-hoops-raw checkout root (Task 3 ingest reads this).
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
        level: grain -- ``"game"`` (one or more rows per contest, carries a
            ``contest_id``) or ``"season"``. Stage 99 derives the schedule
            master's ``in_*`` flag SET from the game-level entries, so this
            field is what makes that set registry-derived rather than
            hand-listed. A dataset added here gets its flag for free.
        csv_suffix: release csv extension.
    """

    dataset: str
    stem: str
    tag: str
    family: str | None
    level: str = "game"
    csv_suffix: str = ".csv"


# Insertion order IS the build order: ``cli.build`` does ``list(REGISTRY)`` for
# ``--dataset all``, and the numbered stage shims are gated against this
# sequence (tests/test_stage_inventory.py). Reordering here without renaming
# the shims (or vice versa) fails that gate by design.
#
# The order reads the way you would rebuild the season from scratch:
# identity/reference first (team_ids -> schedule -> rosters), then the per-game
# event and box extracts, then the lineup-grain frames that index into them.
#
# That is a READING order, not a dependency chain. No dataset is built from
# another dataset's output -- every one is a pure function of (raw tree,
# season): the DIRECT six extract a top-level family from each game's parsed
# JSON, and the DERIVED five are built from those same parsed payloads
# (``schedule``/``rosters``/``matchup_stints``), from the raw roster files
# (``team_rosters``), or from the crosswalk alone (``team_ids``, which reads no
# games at all). So any single dataset can be built on its own, in any order.
# ``matchup_stints`` is the one that looks like an exception and is not: its
# ``*_lineup_key`` columns join to ``lineups`` when you QUERY them, but both
# frames are derived independently from the raw payloads when you BUILD them.
REGISTRY: dict[str, DatasetSpec] = {
    # -- reference / identity (DERIVED: no parsed-JSON family) ---------------
    "team_ids": DatasetSpec(
        "team_ids", _T + "team_ids", _T + "team_ids", None, level="season"
    ),
    "schedule": DatasetSpec("schedule", _T + "schedule", _T + "schedule", None),
    "team_rosters": DatasetSpec(
        "team_rosters", _T + "team_rosters", _T + "team_rosters", None, level="season"
    ),
    "rosters": DatasetSpec(
        "rosters", _T + "rosters", _T + "rosters", None, level="season"
    ),
    # -- per-game events + box (DIRECT: family == dataset key) --------------
    "pbp": DatasetSpec("pbp", _T + "pbp", _T + "pbp", "pbp"),
    "player_box": DatasetSpec(
        "player_box", _T + "player_box", _T + "player_box", "player_box"
    ),
    "team_box": DatasetSpec("team_box", _T + "team_box", _T + "team_box", "team_box"),
    # -- lineup grain + the frames that index into the events ---------------
    "lineups": DatasetSpec("lineups", _T + "lineups", _T + "lineups", "lineups"),
    "matchup_stints": DatasetSpec(  # DERIVED
        "matchup_stints", _T + "matchup_stints", _T + "matchup_stints", None
    ),
    "possessions": DatasetSpec(
        "possessions", _T + "possessions", _T + "possessions", "possessions"
    ),
    "shots": DatasetSpec("shots", _T + "shots", _T + "shots", "shots"),
}
