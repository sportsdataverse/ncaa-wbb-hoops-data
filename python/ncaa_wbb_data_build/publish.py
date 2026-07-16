"""Release publishing -- per-file ``gh release upload --clobber`` (create-if-missing).

Port of the R ``sportsdataverse_save`` upload. Multi-asset globs silently drop
large files, so upload one file at a time -- and uploads never delete-then-
upload, they overwrite in place via ``--clobber``. ``runner``/``exists_check``
are injectable for hermetic tests.

Assets are parquet (in-repo, always present) + csv + rds (release staging,
gitignored, written by ``io.write_dataset(release=True)`` / ``rds.to_rds``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from ncaa_wbb_data_build._logging import get_logger, human_size
from ncaa_wbb_data_build.config import DatasetSpec

_LEAGUE = "wbb"

DEFAULT_REPO = "sportsdataverse/sportsdataverse-data"

log = get_logger()


# Bound each `gh` shell-out so a network stall / hung invocation can't block the
# whole publish run indefinitely (a failed upload is safe to re-run -- every
# upload is idempotent via --clobber).
_GH_TIMEOUT = 180


def _gh(args: list[str]) -> None:
    subprocess.run(["gh", *args], check=True, timeout=_GH_TIMEOUT)


def _gh_release_exists(tag: str, repo: str) -> bool:
    return (
        subprocess.run(
            ["gh", "release", "view", tag, "--repo", repo],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_GH_TIMEOUT,
        ).returncode
        == 0
    )


def _dataset_files(spec: DatasetSpec, season: int, base: Path) -> list[Path]:
    release_dir = base / _LEAGUE / "_release_build" / spec.dataset
    cands = [
        base / _LEAGUE / spec.dataset / "parquet" / f"{spec.stem}_{season}.parquet",
        release_dir / f"{spec.stem}_{season}.csv",
        release_dir / f"{spec.stem}_{season}.rds",
    ]
    return [f for f in cands if f.exists()]


def publish_dataset(
    spec: DatasetSpec,
    season: int,
    *,
    base: str | Path,
    repo: str = DEFAULT_REPO,
    dry_run: bool = False,
    runner: Callable[[list[str]], None] | None = None,
    exists_check: Callable[[str, str], bool] | None = None,
    make_rds: bool = True,
) -> dict:
    """Upload a dataset/season's parquet + csv + rds to the release, creating it if missing.

    Args:
        spec: Dataset spec (``dataset``/``stem``/``tag``) from ``config.REGISTRY``.
        season: Season year; must match the files already written by ``io.write_dataset``.
        base: Root directory containing ``wbb/{dataset}/parquet`` + ``wbb/_release_build/{dataset}``.
        repo: ``owner/repo`` slug for the release target.
        dry_run: If True, skip all ``gh`` calls and log the would-be uploads.
        runner: Injectable ``gh`` arg-list executor; defaults to a real subprocess call.
        exists_check: Injectable ``(tag, repo) -> bool`` release-existence check.
        make_rds: If True, stage the rds asset from the parquet (via ``rds.to_rds``)
            when missing. RDS failure (e.g. no Rscript/arrow) only logs a warning --
            it never blocks the parquet+csv upload.

    Returns:
        dict: ``{"tag": ..., "files": [...], "uploaded": <count>}``.

    Example:
        Quick start::

            from ncaa_wbb_data_build.config import REGISTRY
            from ncaa_wbb_data_build import publish
            publish.publish_dataset(REGISTRY["team_box"], 2025, base="build")
    """
    run = runner or _gh
    exists = exists_check or _gh_release_exists
    base = Path(base)

    if make_rds:
        parquet = (
            base / _LEAGUE / spec.dataset / "parquet" / f"{spec.stem}_{season}.parquet"
        )
        rds_path = (
            base
            / _LEAGUE
            / "_release_build"
            / spec.dataset
            / f"{spec.stem}_{season}.rds"
        )
        # Regenerate the rds when it's missing OR stale (parquet rebuilt since):
        # a prior run's rds must never be uploaded against a freshly written parquet.
        if parquet.exists() and (
            not rds_path.exists() or rds_path.stat().st_mtime < parquet.stat().st_mtime
        ):
            from ncaa_wbb_data_build import rds

            try:
                rds.to_rds(parquet, rds_path)
            except Exception as e:  # noqa: BLE001 -- R may be absent in CI
                log.warning(
                    "%s %s: rds conversion failed, skipping rds asset: %s",
                    spec.dataset,
                    season,
                    e,
                )

    files = _dataset_files(spec, season, base)
    if not files:
        log.warning("%s %s: no files to publish under %s", spec.dataset, season, base)

    if not dry_run and not exists(spec.tag, repo):
        log.info("release %s missing on %s -- creating it", spec.tag, repo)
        run(
            [
                "release",
                "create",
                spec.tag,
                "--repo",
                repo,
                "--title",
                spec.tag,
                "--notes",
                f"{spec.tag} (NCAA WBB dataset, Python-built).",
            ]
        )

    count = 0
    for f in files:
        if dry_run:
            size = human_size(f.stat().st_size)
            log.info("[dry-run] upload %s (%s) -> %s:%s", f, size, repo, spec.tag)
            continue
        size = human_size(f.stat().st_size)
        log.info("uploading %s (%s) -> %s:%s", f.name, size, repo, spec.tag)
        run(["release", "upload", spec.tag, str(f), "--repo", repo, "--clobber"])
        count += 1
        log.info("uploaded %s -> %s (asset %d/%d)", f.name, spec.tag, count, len(files))

    return {"tag": spec.tag, "files": [str(f) for f in files], "uploaded": count}
