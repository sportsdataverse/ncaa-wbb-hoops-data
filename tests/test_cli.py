"""Tests for cli.py -- build subcommand, hermetic (real fixtures, no network, no gh)."""

from pathlib import Path

import polars as pl
import pytest

from ncaa_wbb_data_build.cli import main
from ncaa_wbb_data_build.config import REGISTRY

RAW_ROOT = str(Path(__file__).parent / "fixtures" / "raw_root")


def test_build_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["build", "--help"])
    assert exc.value.code == 0


def test_build_dataset_shots(tmp_path: Path):
    rc = main(
        [
            "build",
            "--dataset",
            "shots",
            "--season",
            "2025",
            "--base",
            str(tmp_path),
            "--raw-root",
            RAW_ROOT,
        ]
    )
    assert rc == 0
    pq = tmp_path / "wbb" / "shots" / "parquet" / "shots_2025.parquet"
    assert pq.exists()
    assert pl.read_parquet(pq).height > 0


def test_build_dataset_all(tmp_path: Path):
    rc = main(
        [
            "build",
            "--dataset",
            "all",
            "--season",
            "2025",
            "--base",
            str(tmp_path),
            "--raw-root",
            RAW_ROOT,
        ]
    )
    assert rc == 0
    for dataset in REGISTRY:
        pq = tmp_path / "wbb" / dataset / "parquet" / f"{dataset}_2025.parquet"
        assert pq.exists(), f"missing parquet for {dataset}"
