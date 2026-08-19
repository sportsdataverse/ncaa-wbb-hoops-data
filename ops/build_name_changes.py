"""Build the NCAA game-time -> current player name crosswalk.

stats.ncaa.org re-renders roster and box pages with a player's CURRENT name,
while the play-by-play preserves the name as it was at game time. A player who
changes their name therefore NEVER matches between `possessions` and
`team_rosters` -- no string heuristic can bridge e.g.
`KATELYNN.LIMARDO -> KATELYNN.MARTIN`, and one that could would also produce
wrong matches.

The `box_score` page carries both, bound by a shared numeric player id:

    shot JS   addShot(..., '... player_768547579 team_201', ...)
              "1st 06:33 : made by Miah Monahan(Eastern Ill.) 9-7"   <- game-time
    dropdown  <option value="768547579">Miah Meyer</option>          <- current

The id is per-game (sequential within a page), which is fine: we only need it
to link the two renderings inside one page.

Canonical home is the `-data` repo, at `ops/build_name_changes.py`:

    python ops/build_name_changes.py --league wbb
    python ops/build_name_changes.py --league mbb --season 2024

Output (default): <repo>/<league>/name_changes/parquet/ncaa_{league}_name_changes.parquet
    season, team, name_game_time, name_current, n_games

`n_games` counts GAMES, not shot attempts -- mappings are deduped per file.

The raw tree resolves as --raw-root, then $NCAA_{WBB,MBB}_RAW_ROOT, then the
sibling layout; --out overrides the destination. A file that cannot be parsed
is logged and counted, and a non-empty failure ledger fails the RUN (exit 1),
so an incomplete crosswalk can never look like a clean one.

Only rows where the two CODED names differ are emitted -- comparing raw HTML
strings yields false positives from entity/whitespace noise (an early run
"found" KIERA.EDMONDS -> KIERA.EDMONDS).
"""

from __future__ import annotations

import argparse
import gzip
import html as _html
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import polars as pl

# League -> (sibling raw-repo dir, tree under it). Kept RELATIVE: absolute
# workstation paths make the script unrunnable on any other checkout.
_LEAGUE_REL = {
    "wbb": ("ncaa-wbb-hoops-raw", "wbb/raw"),
    "mbb": ("ncaa-mbb-hoops-raw", "mbb/raw"),
}

#: Env override naming the directory that CONTAINS the sibling `-raw` checkout.
_ROOT_ENV = {"wbb": "NCAA_WBB_RAW_ROOT", "mbb": "NCAA_MBB_RAW_ROOT"}


def raw_dir(league: str, raw_root: "str | None" = None) -> Path:
    """Resolve the raw tree: --raw-root, then $NCAA_{LG}_RAW_ROOT, then sibling.

    An explicit root may name EITHER the season tree (``…/<lg>/raw``) or the
    directory holding the sibling ``-raw`` checkout; ``<base>/<tree>`` is
    preferred when it exists, otherwise ``<base>`` is taken to BE the tree. The
    caller sees which was chosen either way, because a resolved path with no
    season dirs under it fails in ``main`` naming the path.
    """
    repo, tree = _LEAGUE_REL[league]
    for base in (raw_root, os.environ.get(_ROOT_ENV[league])):
        if base:
            b = Path(base)
            return b / tree if (b / tree).is_dir() else b
    # Canonical home is <data-repo>/ops/, so parents[2] is the directory that
    # holds the sibling -raw checkouts. From anywhere else, pass --raw-root.
    return Path(__file__).resolve().parents[2] / repo / tree

_OPT = re.compile(r'<option value="(\d+)"[^>]*>\s*([^<]+?)\s*</option>')
#: Files that could not be parsed. A non-empty ledger fails the run.
_FAILURES: "list[tuple[str, str]]" = []

_SHOT = re.compile(r"addShot\([^)]*?:\s*(?:made|missed) by ([^(]+)\(([^)]+)\)[^)]*?player_(\d+)")


def code(name: str) -> str:
    """`Miah Monahan` -> `MIAH.MONAHAN`, diacritics folded, entities decoded."""
    s = _html.unescape(name)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return ".".join(p for p in re.split(r"\s+", s.strip().upper()) if p)


def scan_game(path: Path) -> "list[tuple[str, str, str]]":
    """-> [(team, game_time_code, current_code)] for genuine changes only."""
    try:
        # Context manager: this runs over ~194k files, so one leaked descriptor
        # per game exhausts the OS limit long before the scan finishes.
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            pages = json.load(fh).get("pages", {})
    except (OSError, json.JSONDecodeError, EOFError) as exc:
        # Narrow, logged, AND COUNTED. A bare `except Exception` made corruption
        # indistinguishable from "this game had no name changes"; returning []
        # quietly is just as bad, because the run then writes a
        # successful-looking parquet over an incomplete scan. One bad file must
        # not abort a 194k-file sweep, so the failure is recorded and the RUN
        # exits non-zero at the end -- the driver-failure-ledger pattern.
        _FAILURES.append((str(path), f"{type(exc).__name__}: {exc}"))
        print(f"  WARN unreadable {path.name}: {type(exc).__name__}: {exc}", flush=True)
        return []
    box = pages.get("box_score") or ""
    if not box:
        return []
    opts = dict(_OPT.findall(box))
    if not opts:
        return []
    out = []
    for raw_name, team, pid in _SHOT.findall(box):
        cur = opts.get(pid)
        if not cur:
            continue
        a, b = code(raw_name), code(cur)
        if a and b and a != b:
            out.append((team.strip(), a, b))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=sorted(_LEAGUE_REL), required=True)
    ap.add_argument("--season", type=int, action="append")
    ap.add_argument("--limit", type=int, default=0, help="games per season (probe)")
    ap.add_argument("--out", default=None, help="Output dir (default: the dataset location).")
    ap.add_argument(
        "--raw-root",
        default=None,
        help="EITHER the season tree itself (…/<lg>/raw, holding 2010/, 2011/ …) "
        "OR the directory containing the sibling -raw checkout; whichever is "
        "given, the season dirs must end up directly beneath the resolved path. "
        "Falls back to $NCAA_{WBB,MBB}_RAW_ROOT, then the sibling layout.",
    )
    args = ap.parse_args(argv)

    root = raw_dir(args.league, args.raw_root)
    if not root.is_dir():
        print(f"ERROR: raw tree not found: {root}", file=sys.stderr)
        print(f"  pass --raw-root or set ${_ROOT_ENV[args.league]}", file=sys.stderr)
        return 2
    available = {d.name for d in root.iterdir() if d.is_dir()}
    if args.season:
        seasons = [str(s) for s in args.season]
        missing = [s for s in seasons if s not in available]
        if missing:
            # Silently scanning nothing would emit an empty parquet that looks
            # like "no name changes this season".
            print(
                f"ERROR: no raw tree for season(s) {', '.join(missing)} under {root}",
                file=sys.stderr,
            )
            print(f"  available: {', '.join(sorted(available))}", file=sys.stderr)
            return 2
    else:
        seasons = sorted(available)
    rows, scanned = [], 0
    for season in seasons:
        d = root / season
        files = sorted(d.glob("*.json.gz"))
        if args.limit:
            files = files[: args.limit]
        counts: Counter = Counter()
        for i, f in enumerate(files, 1):
            # dedupe per FILE: scan_game yields one record per matching shot
            # attempt, so counting them directly inflates n_games for anyone
            # who took more than one shot in a game.
            for team, old, new in set(scan_game(f)):
                counts[(team, old, new)] += 1
            if i % 500 == 0:
                print(
                    f"  {args.league} {season}: {i}/{len(files)} games, {len(counts)} changes",
                    flush=True,
                )
        scanned += len(files)
        for (team, old, new), n in counts.items():
            rows.append(
                {
                    "season": season,
                    "team": team,
                    "name_game_time": old,
                    "name_current": new,
                    "n_games": n,
                }
            )
        print(
            f"  {args.league} {season}: {len(files)} games -> {len(counts)} changes",
            flush=True,
        )

    # Canonical dataset location in the -data repo: <repo>/<league>/name_changes/parquet
    out_dir = (
        Path(args.out)
        if args.out
        else Path(__file__).resolve().parents[1] / args.league / "name_changes" / "parquet"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"ncaa_{args.league}_name_changes.parquet"
    df = (
        pl.DataFrame(
            rows,
            schema={
                "season": pl.Utf8,
                "team": pl.Utf8,
                "name_game_time": pl.Utf8,
                "name_current": pl.Utf8,
                "n_games": pl.Int64,
            },
        )
        if rows
        else pl.DataFrame(
            schema={
                "season": pl.Utf8,
                "team": pl.Utf8,
                "name_game_time": pl.Utf8,
                "name_current": pl.Utf8,
                "n_games": pl.Int64,
            }
        )
    )
    df.write_parquet(out)
    print(f"scanned={scanned} games -> {df.height} name-changes -> {out}")
    if _FAILURES:
        print(file=sys.stderr)
        print(f"FAILED to parse {len(_FAILURES)} file(s) -- crosswalk is INCOMPLETE:", file=sys.stderr)
        for path_, why in _FAILURES[:20]:
            print(f"  {path_}: {why}", file=sys.stderr)
        if len(_FAILURES) > 20:
            print(f"  ... and {len(_FAILURES) - 20} more", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
