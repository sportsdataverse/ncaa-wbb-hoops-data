"""Tests for rds.py -- Rscript arrow::read_parquet -> saveRDS conversion.

Gated: only runs when the resolved ``Rscript`` has R's ``arrow`` package.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import polars as pl
import pytest

from ncaa_wbb_data_build.rds import _find_rscript, to_rds

_rscript = _find_rscript()


def _has_arrow(rscript: str | None) -> bool:
    if rscript is None:
        return False
    result = subprocess.run(
        [rscript, "-e", 'cat(requireNamespace("arrow", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "TRUE"


_has_rscript_with_arrow = _has_arrow(_rscript)

_needs_r = pytest.mark.skipif(not _has_rscript_with_arrow, reason="Rscript with arrow not available")


def test_to_rds_no_rscript_found_raises_runtime_error(tmp_path: Path, monkeypatch):
    """Not gated on real R: ``_find_rscript`` returning None must raise RuntimeError."""
    monkeypatch.setattr("ncaa_wbb_data_build.rds._find_rscript", lambda: None)
    parquet = tmp_path / "in.parquet"
    pl.DataFrame({"a": [1]}).write_parquet(parquet)

    with pytest.raises(RuntimeError, match="Rscript not found"):
        to_rds(parquet, tmp_path / "out.rds")


@_needs_r
def test_to_rds_honors_explicit_rscript_arg(tmp_path: Path):
    """Passing rscript= is used instead of _find_rscript()'s resolution."""
    df = pl.DataFrame({"a": [1, 2]})
    parquet = tmp_path / "in.parquet"
    df.write_parquet(parquet)

    out = to_rds(parquet, tmp_path / "out.rds", rscript=_rscript)

    assert out.exists()


@_needs_r
def test_to_rds_round_trips_through_r(tmp_path: Path):
    df = pl.DataFrame(
        {
            "game_id": [1, 2, 3],
            "team": ["South Carolina", "Notre Dame", "NC State"],
            "score": [92.0, 80.0, 104.0],
        }
    )
    parquet = tmp_path / "in.parquet"
    df.write_parquet(parquet)

    out = to_rds(parquet, tmp_path / "out.rds")

    assert out == tmp_path / "out.rds"
    assert out.exists()
    assert out.stat().st_size > 0

    result = subprocess.run(
        [
            _rscript,
            "-e",
            "x<-readRDS(commandArgs(TRUE)[1]); cat(nrow(x), ncol(x))",
            out.as_posix(),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    nrow, ncol = (int(x) for x in result.stdout.split())
    assert (nrow, ncol) == (df.height, df.width)
