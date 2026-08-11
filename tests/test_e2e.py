"""End-to-end offline build test -- all 11 datasets, one season, hermetic fixtures.

Builds every ``config.REGISTRY`` dataset from the 4 fixture games into a
single ``tmp_path`` base and asserts, per dataset: the parquet was written,
is non-empty, and the returned frame's schema round-trips through disk
unchanged. Also locks the dtype-discipline contract (``contest_id``/``id``
Utf8, ``season`` Int64 == 2025) and that a build upserts the manifest.

Season is pinned to **2025** because the committed hermetic fixtures under
``tests/fixtures/raw_root/wbb/`` are season-2025 games. This is no longer a
crosswalk-coverage guard: the bundled WBB team-id crosswalk now carries
2025-26, so ``team_ids(2026)`` resolves (see ``derived.team_ids`` +
``test_derived.py::test_team_ids_2026_season_is_populated``).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ncaa_wbb_data_build.build import build_season
from ncaa_wbb_data_build.config import REGISTRY

RAW_ROOT = Path(__file__).parent / "fixtures" / "raw_root"
SEASON = 2025

# The 6 DIRECT datasets + schedule all carry contest_id (Utf8, dtype discipline).
_HAS_CONTEST_ID = {
    "pbp",
    "lineups",
    "possessions",
    "player_box",
    "team_box",
    "shots",
    "schedule",
}
# The 6 DIRECT datasets carry a per-row season column pinned to the build season.
_DIRECT = {"pbp", "lineups", "possessions", "player_box", "team_box", "shots"}


def test_build_all_datasets(tmp_path: Path):
    for ds in REGISTRY:
        df = build_season(ds, SEASON, base=tmp_path, raw_root=str(RAW_ROOT))

        pq = tmp_path / "wbb" / ds / "parquet" / f"{REGISTRY[ds].stem}_{SEASON}.parquet"
        assert pq.exists(), f"{ds}: parquet not written"

        on_disk = pl.read_parquet(pq)
        assert on_disk.height > 0, f"{ds}: parquet is empty"
        assert df.schema == on_disk.schema, f"{ds}: returned schema != on-disk schema"

        if ds in _HAS_CONTEST_ID:
            assert df.schema["contest_id"] == pl.Utf8, f"{ds}: contest_id not Utf8"
        if ds == "team_ids":
            assert df.schema["id"] == pl.Utf8, "team_ids: id not Utf8"
        if ds in _DIRECT:
            assert (df.get_column("season") == SEASON).all(), (
                f"{ds}: season != {SEASON}"
            )

    manifest = tmp_path / "wbb" / "pbp" / "manifest.csv"
    assert manifest.exists(), "pbp manifest.csv not written"
    rows = pl.read_csv(manifest)
    assert ((rows["dataset"] == "pbp") & (rows["season"] == SEASON)).any(), (
        f"pbp manifest missing a (pbp, {SEASON}) row"
    )
