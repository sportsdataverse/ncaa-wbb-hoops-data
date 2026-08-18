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
from ncaa_wbb_data_build.io import CSV_SUFFIX  # single source of the csv extension

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
    """True when ``tag`` exists. Ambiguous failures are NOT reported as absent.

    ``gh release view`` returns 0 when the release exists and 1 when it does
    not. Any OTHER code means gh could not answer the question -- it failed to
    launch, lost the network, hit an auth error. Reading that as "absent" makes
    the caller try to CREATE a release that already exists, which fails and
    takes the whole unit down with it.

    That is exactly what happened on 2026-08-18 at 02:53:17: a transient
    Windows STATUS_DLL_INIT_FAILED (0xC0000142 = exit 3221225794) hit Rscript
    and gh in the same second, this check read it as "tag missing", and
    ``team_ids 2022`` died on a redundant ``release create``.

    So: 0 -> True, 1 -> False, anything else -> retry once, then assume the
    release EXISTS. Assuming existence is the safe default -- if it really is
    missing, the upload that follows fails loudly and the unit is retried,
    whereas assuming absence corrupts a good run.
    """
    for attempt in (1, 2):
        rc = subprocess.run(
            ["gh", "release", "view", tag, "--repo", repo],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_GH_TIMEOUT,
        ).returncode
        if rc in (0, 1):
            return rc == 0
        log.warning(
            "gh release view %s: ambiguous exit %d (attempt %d/2)", tag, rc, attempt
        )
    log.warning(
        "gh could not resolve whether %s exists -- assuming it does, so a real "
        "upload error surfaces instead of a bogus 'release create'",
        tag,
    )
    return True


def published_assets(tag: str, repo: str = DEFAULT_REPO) -> set[str]:
    """Asset names currently attached to ``tag``; empty set when the tag is absent.

    ONE ``gh`` call per TAG, not per (dataset, season). A sweep therefore costs
    11 calls instead of 187: the 2026-08-12 MBB publish burned its GitHub API
    quota on per-unit polling and earned a 403 partway through the sweep.
    """
    proc = subprocess.run(
        # fmt: off
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            repo,
            "--json",
            "assets",
            "--jq",
            ".assets[].name",
        ],
        # fmt: on
        capture_output=True,
        text=True,
        timeout=_GH_TIMEOUT,
    )
    if proc.returncode != 0:  # tag not created yet -> nothing published
        return set()
    return {ln.strip() for ln in proc.stdout.splitlines() if ln.strip()}


def published_seasons(
    spec: DatasetSpec,
    *,
    repo: str = DEFAULT_REPO,
    assets: set[str] | None = None,
) -> set[int]:
    """Seasons of ``spec`` whose REQUIRED assets are actually on the release.

    Required = parquet AND csv; ``.rds`` is best-effort (``publish_dataset``
    already degrades to a warning when no R install has arrow), so demanding it
    would make every season look unpublished on a machine without R.

    This exists because **a manifest row proves a BUILD, not a PUBLISH.**
    ``io.write_dataset`` upserts the manifest before ``publish_dataset`` runs,
    so a season whose upload failed still leaves a manifest row behind -- and a
    resume check keyed on the manifest skips it forever, silently. Ask the
    release what it actually has.
    """
    names = published_assets(spec.tag, repo) if assets is None else assets
    out: set[int] = set()
    prefix, suffix = f"{spec.stem}_", ".parquet"
    for n in names:
        if not (n.startswith(prefix) and n.endswith(suffix)):
            continue
        season = n[len(prefix) : -len(suffix)]
        if season.isdigit() and f"{prefix}{season}{CSV_SUFFIX}" in names:
            out.add(int(season))
    return out


def _dataset_files(spec: DatasetSpec, season: int, base: Path) -> list[Path]:
    release_dir = base / _LEAGUE / "_release_build" / spec.dataset
    cands = [
        base / _LEAGUE / spec.dataset / "parquet" / f"{spec.stem}_{season}.parquet",
        release_dir / f"{spec.stem}_{season}{CSV_SUFFIX}",
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
            publish.publish_dataset(REGISTRY["team_box"], 2026, base="build")
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
