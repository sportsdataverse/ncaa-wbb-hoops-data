"""Per-season build driver -- ties ingest -> reshapers/derived -> concat -> io together.

Two paths, keyed off ``config.REGISTRY[dataset].family``:

- DIRECT (6 datasets): read each game's parsed JSON, extract the family,
  concat across the season. One bad game is logged + skipped, never aborts
  the season (R tryCatch parity).
- DERIVED (schedule, rosters, team_ids): built from all season finals (or,
  for team_ids, from no finals at all) by ``derived.py``.

Either way the result is written via ``io.write_dataset`` and, if requested,
published lazily (see the local ``publish`` import below -- deferred so that
importing ``publish`` -- which shells out to ``gh`` -- isn't a hard
requirement just to ``import ncaa_wbb_data_build.build``).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import polars as pl
from tqdm import tqdm

from ncaa_wbb_data_build import derived, ingest, io, reshapers
from ncaa_wbb_data_build._logging import get_logger
from ncaa_wbb_data_build.config import REGISTRY

log = get_logger()

# Non-TTY runs (CI) get a heartbeat line every N games instead of a tqdm bar.
_PROGRESS_EVERY = 250


def build_season(
    dataset: str,
    season: int,
    *,
    base: str | Path,
    raw_root: str | Path | None = None,
    publish_release: bool = False,
    dry_run: bool = False,
) -> pl.DataFrame:
    """Build one dataset/season from the raw checkout: reshape/derive, write, (opt) publish.

    Args:
        dataset: Key into ``config.REGISTRY`` (e.g. ``"pbp"``, ``"schedule"``).
        season: Season ending year (e.g. 2025 for 2024-25).
        base: Output root directory for ``io.write_dataset``.
        raw_root: Sibling ``ncaa-wbb-hoops-raw`` checkout root (arg > env).
        publish_release: If True, upload the written files via ``publish.publish_dataset``.
        dry_run: If True, run the publish step in dry-run mode (no ``gh`` calls).

    Returns:
        pl.DataFrame: The built season frame, or an empty frame if nothing qualified.
    """
    spec = REGISTRY[dataset]
    root = ingest.raw_root(raw_root)
    started = time.monotonic()

    if spec.family is not None:
        out = _build_direct(dataset, spec.family, season, root)
    elif dataset == "team_ids":
        out = derived.team_ids(season)
    elif dataset in ("schedule", "rosters"):
        contest_ids = ingest.season_contest_ids(season, raw_root=root)
        if not contest_ids:
            log.warning(
                "%s %s: no contest_ids in schedule_master; nothing built",
                dataset,
                season,
            )
            return pl.DataFrame()
        finals = [f for cid in contest_ids if (f := ingest.read_parsed(cid, raw_root=root)) is not None]
        out = derived.schedule(finals, season) if dataset == "schedule" else derived.rosters(finals, season)
    else:
        raise ValueError(f"{dataset}: no DIRECT family and no DERIVED builder registered")

    if out.height == 0:
        # _build_direct already warns (empty contest_ids or 0 games extracted)
        # before returning an empty frame -- don't warn twice for that path.
        if spec.family is None:
            log.warning("%s %s: 0 rows built; nothing written", dataset, season)
        return out

    io.write_dataset(out, spec, season, base=base, release=publish_release or dry_run)
    if publish_release or dry_run:
        from ncaa_wbb_data_build import (
            publish,
        )  # lazy: avoid a hard `gh` dependency for plain imports

        publish.publish_dataset(spec, season, base=base, dry_run=dry_run)

    log.info(
        "%s %s: done -- %d rows in %.1fs",
        dataset,
        season,
        out.height,
        time.monotonic() - started,
    )
    return out


def _build_direct(dataset: str, family: str, season: int, root: str | Path) -> pl.DataFrame:
    """DIRECT-path loop: per-game read + extract + concat, one bad game skipped."""
    contest_ids = ingest.season_contest_ids(season, raw_root=root)
    if not contest_ids:
        log.warning("%s %s: no contest_ids in schedule_master; nothing built", dataset, season)
        return pl.DataFrame()

    log.info("%s %s: per-game build starting -- %d games", dataset, season, len(contest_ids))
    frames: list[pl.DataFrame] = []
    missing = 0
    failed = 0
    for n, cid in enumerate(tqdm(contest_ids, desc=f"{dataset} {season}", disable=None), start=1):
        final = ingest.read_parsed(cid, raw_root=root)
        if final is None:
            missing += 1
            continue
        try:
            frame = reshapers.extract_family(final, family, season=season, contest_id=cid)
        except Exception as e:  # one bad game must not abort the season
            log.warning("%s %s: extract failed for game %s: %s", dataset, season, cid, e)
            failed += 1
            continue
        if frame.height:
            frames.append(frame)
        if not sys.stderr.isatty() and n % _PROGRESS_EVERY == 0:
            log.info("%s %s: %d/%d games processed", dataset, season, n, len(contest_ids))

    if missing:
        log.warning(
            "%s %s: %d/%d games had no readable payload",
            dataset,
            season,
            missing,
            len(contest_ids),
        )
    if failed:
        log.warning(
            "%s %s: %d/%d games failed to extract",
            dataset,
            season,
            failed,
            len(contest_ids),
        )
    if not frames:
        log.warning("%s %s: 0 games extracted; nothing written", dataset, season)
        return pl.DataFrame()

    out = pl.concat(frames, how="diagonal_relaxed")
    if "contest_id" in out.columns:
        out = out.sort("contest_id", maintain_order=True)
    return out
