"""CLI -- ``ncaa_wbb_data_build build --dataset {ds|all} --season YYYY [--publish|--dry-run]``."""

from __future__ import annotations

import argparse

from ncaa_wbb_data_build._logging import get_logger
from ncaa_wbb_data_build.build import build_season
from ncaa_wbb_data_build.config import REGISTRY

log = get_logger()


def _build(args: argparse.Namespace) -> int:
    datasets = list(REGISTRY) if args.dataset == "all" else [args.dataset]
    for dataset in datasets:
        df = build_season(
            dataset,
            args.season,
            base=args.base,
            raw_root=args.raw_root,
            publish_release=args.publish,
            dry_run=args.dry_run,
        )
        log.info("%s %s: season complete -- %d rows", dataset, args.season, df.height)
    return 0


def _check(args: argparse.Namespace) -> int:
    """Compare each dataset's LOCALLY BUILT seasons against what the release holds.

    Compares the SETS, never the counts -- a count-only check passes while the
    seasons are wrong.

    Only ``built - live`` (built here, missing from the release) fails the
    check: that is the question a publish sweep needs answered. The reverse,
    ``live - built``, is REPORTED but not fatal, because a season published
    from another machine or built-then-pruned locally is legitimate and is not
    a publishing failure. Making it fatal would red the gate on a clean repo.

    A ``GhUnavailable`` is deliberately NOT swallowed into "nothing published":
    that is the distinction between "this tag has nothing" and "I could not
    look", and collapsing it would make a resume index empty and re-upload an
    entire history.
    """
    from pathlib import Path

    from ncaa_wbb_data_build.publish import (
        DEFAULT_REPO,
        GhUnavailable,
        published_seasons,
    )

    datasets = list(REGISTRY) if args.dataset == "all" else [args.dataset]
    base = Path(args.base)
    missing_total = 0
    for name in datasets:
        spec = REGISTRY[name]
        built = {
            int(p.stem.rsplit("_", 1)[1])
            for p in (base / "wbb" / spec.dataset / "parquet").glob(
                f"{spec.stem}_*.parquet"
            )
            if p.stem.rsplit("_", 1)[1].isdigit()
        }
        try:
            live = published_seasons(spec, repo=args.repo or DEFAULT_REPO)
        except GhUnavailable as exc:
            # Exit 2 (not 1): "I could not look" is a different outcome from
            # "there are gaps", and a caller gating a sweep must be able to
            # tell them apart before deciding to upload anything.
            log.error("cannot audit %s: %s", name, exc)
            return 2
        if args.porcelain:
            # "<dataset> <season>" per PUBLISHED unit -- the resume index a
            # sweep driver greps. One gh call per tag builds the whole index.
            for s in sorted(live):
                print(f"{name} {s}")
            continue
        missing = sorted(built - live)
        extra = sorted(live - built)
        missing_total += len(missing)
        status = "OK  " if not missing else "GAP "
        log.info(
            "%s %-15s built=%d published=%d%s%s",
            status,
            name,
            len(built),
            len(live),
            f" MISSING={missing}" if missing else "",
            f" PUBLISHED_ONLY={extra}" if extra else "",
        )
    if missing_total:
        log.error("%d built season(s) are NOT on their release", missing_total)
    return 1 if missing_total else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ncaa_wbb_data_build")
    sub = p.add_subparsers(dest="command", required=False)

    build_p = sub.add_parser("build", help="Build one or all datasets for a season.")
    build_p.add_argument("--dataset", required=True, choices=sorted(REGISTRY) + ["all"])
    build_p.add_argument("--season", type=int, required=True)
    build_p.add_argument("--base", default=".")
    build_p.add_argument("--raw-root", default=None)
    g = build_p.add_mutually_exclusive_group()
    g.add_argument("--publish", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    build_p.set_defaults(func=_build)

    check_p = sub.add_parser(
        "check",
        help="Audit built seasons against what each release actually holds.",
    )
    check_p.add_argument("--dataset", default="all", choices=sorted(REGISTRY) + ["all"])
    check_p.add_argument("--base", default=".")
    check_p.add_argument("--repo", default=None)
    check_p.add_argument(
        "--porcelain",
        action="store_true",
        help="Print '<dataset> <season>' per published unit (resume index).",
    )
    check_p.set_defaults(func=_check)

    args = p.parse_args(argv)
    if args.command is None:
        p.print_help()
        return 2
    return args.func(args)
