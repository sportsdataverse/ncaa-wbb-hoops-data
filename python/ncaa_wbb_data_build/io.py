"""Dataset IO -- parquet writer (committed) + csv release staging + manifest.

Format policy: the tree commits **parquet only**, under
``wbb/{dataset}/parquet/{stem}_{season}.parquet``. Release assets (csv here;
``.rds`` in a later task) are staged under the gitignored
``wbb/_release_build/`` and only produced when ``release=True`` -- they are
never committed. A tiny per-dataset ``manifest.csv`` (committed) tracks one
row per ``(dataset, season)``, upserted on every write.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from ncaa_wbb_data_build._logging import get_logger, human_size
from ncaa_wbb_data_build.config import DatasetSpec

_LEAGUE = "wbb"

log = get_logger()

_MANIFEST_SCHEMA: dict[str, pl.PolarsDataType] = {
    "dataset": pl.Utf8,
    "season": pl.Int64,
    "row_count": pl.Int64,
    "generated_at_utc": pl.Utf8,
}


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def manifest_path(spec: DatasetSpec, base: Path) -> Path:
    return base / _LEAGUE / spec.dataset / "manifest.csv"


def _upsert_manifest(
    spec: DatasetSpec, season: int, row_count: int, base: Path
) -> Path:
    """Upsert one ``(dataset, season)`` row into the dataset's manifest, keep latest.

    Unlike an append log, this keeps exactly one row per season so idempotent
    rebuilds don't bloat the file: read existing (if present), drop any row
    for this ``(dataset, season)``, append the new row, sort by season.
    """
    f = manifest_path(spec, base)
    f.parent.mkdir(parents=True, exist_ok=True)
    row = pl.DataFrame(
        {
            "dataset": [spec.dataset],
            "season": [int(season)],
            "row_count": [int(row_count)],
            "generated_at_utc": [_utc_now_str()],
        },
        schema=_MANIFEST_SCHEMA,
    )
    if f.exists():
        existing = pl.read_csv(f, schema=_MANIFEST_SCHEMA)
        existing = existing.filter(
            ~((pl.col("dataset") == spec.dataset) & (pl.col("season") == int(season)))
        )
        row = pl.concat([existing, row], how="vertical")
    row = row.sort("season")
    row.write_csv(f)
    return f


def write_dataset(
    df: pl.DataFrame,
    spec: DatasetSpec,
    season: int,
    *,
    base: str | Path = ".",
    release: bool = False,
) -> list[Path]:
    """Write the committed parquet (always) + staged release csv (if requested).

    Always writes ``{base}/wbb/{dataset}/parquet/{stem}_{season}.parquet``.
    When ``release=True`` also writes a plain csv to the gitignored
    ``{base}/wbb/_release_build/{dataset}/{stem}_{season}.csv``. Upserts the
    committed ``{base}/wbb/{dataset}/manifest.csv`` row for every write.
    Returns the parquet path, plus the csv path when ``release=True``.
    """
    base = Path(base)
    pq_dir = base / _LEAGUE / spec.dataset / "parquet"
    pq_dir.mkdir(parents=True, exist_ok=True)
    pq = pq_dir / f"{spec.stem}_{season}.parquet"
    df.write_parquet(pq)
    out = [pq]

    if release:
        csv_dir = base / _LEAGUE / "_release_build" / spec.dataset
        csv_dir.mkdir(parents=True, exist_ok=True)
        csv = csv_dir / f"{spec.stem}_{season}.csv"
        df.write_csv(csv)
        out.append(csv)

    manifest = _upsert_manifest(spec, season, df.height, base)
    log.info(
        "wrote %s (%s), %d rows x %d cols%s; manifest %s upserted",
        pq,
        human_size(pq.stat().st_size),
        df.height,
        df.width,
        f" + {out[1].name} (release)" if release else "",
        manifest.name,
    )
    return out
