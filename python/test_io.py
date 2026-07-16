"""Tests for io.py -- parquet writer (in-repo) + csv release staging + manifest."""

from pathlib import Path

import polars as pl

from ncaa_wbb_data_build.config import REGISTRY
from ncaa_wbb_data_build.io import write_dataset

SPEC = REGISTRY["pbp"]


def _frame(n: int) -> pl.DataFrame:
    return pl.DataFrame(
        {"game_id": list(range(n)), "value": [float(i) for i in range(n)]}
    )


def test_release_false_writes_only_parquet_no_csv_anywhere(tmp_path: Path):
    df = _frame(5)
    paths = write_dataset(df, SPEC, 2025, base=tmp_path)

    pq = tmp_path / "wbb" / "pbp" / "parquet" / "pbp_2025.parquet"
    assert paths == [pq]
    assert pq.exists()
    assert pl.read_parquet(pq).equals(df)

    release_dir = tmp_path / "wbb" / "_release_build"
    assert not release_dir.exists() or not any(release_dir.rglob("*.csv"))


def test_release_true_writes_parquet_and_staged_csv(tmp_path: Path):
    df = _frame(5)
    paths = write_dataset(df, SPEC, 2025, base=tmp_path, release=True)

    assert len(paths) == 2
    csv = tmp_path / "wbb" / "_release_build" / "pbp" / "pbp_2025.csv"
    assert csv in paths
    assert csv.exists()
    read_back = pl.read_csv(csv)
    assert read_back.height == df.height
    assert read_back.width == df.width


def test_manifest_upserts_by_dataset_and_season(tmp_path: Path):
    df = _frame(5)
    write_dataset(df, SPEC, 2025, base=tmp_path)

    mf = tmp_path / "wbb" / "pbp" / "manifest.csv"
    assert mf.exists()
    rows = pl.read_csv(mf)
    pbp_2025 = rows.filter((pl.col("dataset") == "pbp") & (pl.col("season") == 2025))
    assert pbp_2025.height == 1
    assert pbp_2025["row_count"][0] == 5

    # Re-write same (dataset, season) with a different height -> upsert, not append-dup.
    df2 = _frame(9)
    write_dataset(df2, SPEC, 2025, base=tmp_path)
    rows = pl.read_csv(mf)
    pbp_2025 = rows.filter((pl.col("dataset") == "pbp") & (pl.col("season") == 2025))
    assert pbp_2025.height == 1
    assert pbp_2025["row_count"][0] == 9

    # A second season adds a second row.
    write_dataset(_frame(3), SPEC, 2024, base=tmp_path)
    rows = pl.read_csv(mf)
    assert rows.height == 2
