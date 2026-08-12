"""Schedule master (D34): registry-derived in_* flags, manifest, coverage.

Offline and self-contained -- every frame is written into ``tmp_path`` in the
committed tree's own layout, so nothing here depends on the built ``wbb/``
data or on a raw checkout being present.

The load-bearing invariants:

* the ``in_*`` column set exactly mirrors the registry's game-level keys -- a
  dataset added to the registry gets its flag with no edit here, and a
  hand-listed flag with no registry entry cannot exist;
* a family with zero coverage reports ``False``, not an absent column (the
  WBB case: a league whose capture campaign never ran must read as honest
  zeros over a real denominator);
* ``contest_id`` stays Utf8 -- a numeric id raises rather than being cast.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from ncaa_wbb_data_build.config import REGISTRY
from ncaa_wbb_data_build.master import (
    GAME_LEVEL,
    add_game_detail,
    build_coverage,
    build_master,
    committed_contest_ids,
    denominator,
    flag_columns,
    games_in_data_repo,
    stamp_from_committed,
)

CIDS = ["3727922", "3727923", "3727924"]


def _index(cids: list[str] | None = None, season: int = 2024) -> pl.DataFrame:
    return pl.DataFrame(
        {"season": [season] * len(cids or CIDS), "contest_id": cids or CIDS},
        schema={"season": pl.Int64, "contest_id": pl.Utf8},
    )


def _write_dataset(base: Path, key: str, season: int, frame: pl.DataFrame) -> Path:
    spec = REGISTRY[key]
    d = base / "wbb" / spec.dataset / "parquet"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{spec.stem}_{season}.parquet"
    frame.write_parquet(path)
    return path


def _write_raw_master(root: Path, rows: dict[str, list]) -> None:
    (root / "wbb").mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(root / "wbb" / "wbb_schedule_master.parquet")


def test_flag_columns_exactly_mirror_the_registry():
    assert flag_columns() == tuple(
        f"in_{k}" for k, s in REGISTRY.items() if s.level == "game"
    )
    assert flag_columns()  # a registry with no game-level dataset is a bug
    assert "in_team_ids" not in flag_columns()  # season-grain: no flag


def test_denominator_is_the_raw_master_not_the_built_schedule(tmp_path: Path):
    """The denominator must include contests this repo built nothing from."""
    raw = tmp_path / "raw"
    _write_raw_master(raw, {"contest_id": CIDS, "season": ["2024"] * 3})
    # the committed schedule dataset knows about only one of them
    _write_dataset(
        tmp_path,
        "schedule",
        2024,
        pl.DataFrame({"contest_id": CIDS[:1], "season": [2024]}),
    )
    index = denominator(raw_root=raw)
    assert index.get_column("contest_id").to_list() == CIDS
    assert index.schema["contest_id"] == pl.Utf8
    assert index.schema["season"] == pl.Int64


def test_denominator_raises_without_a_raw_master(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="no schedule master"):
        denominator(raw_root=tmp_path)


def test_stamp_reads_the_committed_parquets(tmp_path: Path):
    spec = GAME_LEVEL[0]
    _write_dataset(
        tmp_path,
        spec.dataset,
        2024,
        pl.DataFrame({"contest_id": CIDS[:2], "season": [2024, 2024]}),
    )
    stamped = stamp_from_committed(_index(), tmp_path)
    assert stamped[f"in_{spec.dataset}"].to_list() == [True, True, False]
    # Datasets with nothing committed stay False, not absent.
    for other in GAME_LEVEL[1:]:
        assert stamped[f"in_{other.dataset}"].to_list() == [False, False, False]
        assert stamped.schema[f"in_{other.dataset}"] == pl.Boolean


def test_empty_league_reports_honest_zeros(tmp_path: Path):
    """No committed datasets at all -> a real denominator and every flag False."""
    raw = tmp_path / "raw"
    _write_raw_master(raw, {"contest_id": CIDS, "season": ["2024"] * 3})
    master = build_master(base=tmp_path, raw_root=raw)
    assert master.height == 3
    assert set(flag_columns()) <= set(master.columns)
    for flag in flag_columns():
        assert master[flag].sum() == 0
    assert games_in_data_repo(master).height == 0
    coverage = build_coverage(master)
    assert coverage.height == 1
    assert coverage.to_dicts()[0]["n_games"] == 3
    assert all(coverage.to_dicts()[0][f"pct_{f}"] == 0.0 for f in flag_columns())


def test_numeric_contest_id_raises_instead_of_casting(tmp_path: Path):
    spec = GAME_LEVEL[0]
    _write_dataset(
        tmp_path,
        spec.dataset,
        2024,
        pl.DataFrame({"contest_id": [3727922, 3727923], "season": [2024, 2024]}),
    )
    with pytest.raises(TypeError, match="contest_id is"):
        committed_contest_ids(spec, tmp_path)


def test_game_detail_left_joins_and_keeps_unbuilt_games(tmp_path: Path):
    _write_dataset(
        tmp_path,
        "schedule",
        2024,
        pl.DataFrame(
            {
                "contest_id": CIDS[:1],
                "season": [2024],
                "game_date": ["11/07/2023"],
                "home": ["A"],
                "away": ["B"],
                "home_score": [70],
                "away_score": [60],
            }
        ),
    )
    joined = add_game_detail(_index(), tmp_path)
    assert joined.height == 3  # left join: nothing dropped
    assert joined["home"].to_list() == ["A", None, None]


def test_game_detail_is_optional_when_nothing_is_built(tmp_path: Path):
    index = _index()
    assert add_game_detail(index, tmp_path).equals(index)


def test_master_is_column_ordered_and_key_sorted(tmp_path: Path):
    raw = tmp_path / "raw"
    _write_raw_master(
        raw,
        {"contest_id": [CIDS[2], CIDS[0]], "season": ["2025", "2024"]},
    )
    master = build_master(base=tmp_path, raw_root=raw)
    assert master.columns[:2] == ["season", "contest_id"]
    assert master.columns[2:] == sorted(master.columns[2:])
    assert master["season"].to_list() == [2024, 2025]


def test_manifest_keeps_only_games_with_a_flag(tmp_path: Path):
    raw = tmp_path / "raw"
    _write_raw_master(raw, {"contest_id": CIDS, "season": ["2024"] * 3})
    spec = GAME_LEVEL[0]
    _write_dataset(
        tmp_path,
        spec.dataset,
        2024,
        pl.DataFrame({"contest_id": CIDS[:1], "season": [2024]}),
    )
    master = build_master(base=tmp_path, raw_root=raw)
    manifest = games_in_data_repo(master)
    assert manifest["contest_id"].to_list() == CIDS[:1]
    assert manifest.columns == master.columns  # same schema, filtered rows


def test_coverage_orders_the_date_span_chronologically(tmp_path: Path):
    """min/max on the raw "MM/DD/YYYY" text would put January before November."""
    master = _index(CIDS).with_columns(
        pl.Series("game_date", ["11/07/2023", "01/20/2024", "12/01/2023"])
    )
    row = build_coverage(master).to_dicts()[0]
    assert str(row["first_date"]) == "2023-11-07"
    assert str(row["last_date"]) == "2024-01-20"


def test_coverage_rates(tmp_path: Path):
    flag = flag_columns()[0]
    master = _index().with_columns(pl.Series(flag, [True, True, False]))
    row = build_coverage(master).to_dicts()[0]
    assert row["n_games"] == 3
    assert row[f"pct_{flag}"] == pytest.approx(2 / 3)
