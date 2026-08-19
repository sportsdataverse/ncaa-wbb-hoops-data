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

Usage (from the worktree root):

    uv run python dev/ncaa_rapm/build_name_changes.py --league wbb
    uv run python dev/ncaa_rapm/build_name_changes.py --league mbb --season 2024

Output: dev/ncaa_rapm/out/ncaa_{league}_name_changes.parquet
    season, team, name_game_time, name_current, n_games

Only rows where the two CODED names differ are emitted -- comparing raw HTML
strings yields false positives from entity/whitespace noise (an early run
"found" KIERA.EDMONDS -> KIERA.EDMONDS).
"""

from __future__ import annotations

import argparse
import gzip
import html as _html
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import polars as pl

_RAW = {
    "wbb": Path("c:/Users/saiem/Documents/GitHub-Data/sdv-dev/wehoop-dev/ncaa-wbb-hoops-raw/wbb/raw"),
    "mbb": Path("c:/Users/saiem/Documents/GitHub-Data/sdv-dev/hoopR-dev/ncaa-mbb-hoops-raw/mbb/raw"),
}

_OPT = re.compile(r'<option value="(\d+)"[^>]*>\s*([^<]+?)\s*</option>')
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
        pages = json.loads(gzip.open(path, "rt", encoding="utf-8", errors="replace").read()).get("pages", {})
    except Exception:
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
    ap.add_argument("--league", choices=sorted(_RAW), required=True)
    ap.add_argument("--season", type=int, action="append")
    ap.add_argument("--limit", type=int, default=0, help="games per season (probe)")
    args = ap.parse_args(argv)

    root = _RAW[args.league]
    seasons = [str(s) for s in args.season] if args.season else sorted(d.name for d in root.iterdir() if d.is_dir())
    rows, scanned = [], 0
    for season in seasons:
        d = root / season
        files = sorted(d.glob("*.json.gz"))
        if args.limit:
            files = files[: args.limit]
        counts: Counter = Counter()
        for i, f in enumerate(files, 1):
            for team, old, new in scan_game(f):
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

    out_dir = Path(__file__).parent / "out"
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
