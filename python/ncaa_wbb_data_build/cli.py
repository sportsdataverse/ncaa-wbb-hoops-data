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

    args = p.parse_args(argv)
    if args.command is None:
        p.print_help()
        return 2
    return args.func(args)
