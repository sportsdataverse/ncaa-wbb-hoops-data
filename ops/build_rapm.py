"""Path A: feed the real hoop-explorer RAPM engine from raw NCAA HTML.

The engine (`mbb_rapm.build_player_context` + the ridge solve) consumes
hoop-explorer's ES-derived lineup buckets -- 257 keys per bucket. Neither
published dataset carries them (`possessions` is 56 flat cols, `lineups` 77),
so the buckets have to come from the parse chain that produces them:

    get_box_lineup(individual_stats_html, TeamId(team))
      -> create_lineup_data(pbp_html, box_lineup)          -> list[LineupEvent]
      -> lineup_stats_buckets(events)                       -> list[LineupStatSet]
      -> lineup_to_team_report({"lineups": buckets})        -> on/off players
      -> build_player_context(players, buckets, ...)        -> RAPM context

Call sequence copied from `tests/mbb/test_mbb_ncaa_lineup_aggregation_e2e.py`,
the committed end-to-end proof, so the shape is right by construction rather
than inferred.

**This engine's RAPM is WITHIN-TEAM** -- it apportions one team's performance
across its own players from that team's lineup splits. That is a different
estimand from league-wide RAPM (which regresses every lineup in the league
jointly). Path B will do the league-wide form off the published `lineups`
frame; keeping both lets each be checked against the other.

Cost: ~0.51 s/game single-threaded, so ~47 min per season and ~13.4 h for one
league's 17 seasons. Per-game work is independent, so it parallelizes.

    uv run python ops/build_rapm.py --league wbb --season 2024 --team "Duke"
    uv run python ops/build_rapm.py --league wbb --season 2024 --workers 10
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import os
import re
from pathlib import Path

import polars as pl

from sportsdataverse.mbb import mbb_ncaa_lineup_aggregation as agg
from sportsdataverse.mbb.mbb_lineup_stats import lineup_to_team_report
from sportsdataverse.mbb.mbb_ncaa_boxscore_parser import get_box_lineup
from sportsdataverse.mbb.mbb_ncaa_game_pbp import parse_ncaa_bb_game_pbp
from sportsdataverse.mbb.mbb_ncaa_models import TeamId
from sportsdataverse.mbb.mbb_ncaa_pbp_parser import create_lineup_data
from sportsdataverse.mbb.mbb_rapm import (
    DEFAULT_RAPM_CONFIG,
    build_player_context,
    calc_lineup_outputs,
    calc_player_weights,
    calculate_rapm,
    slow_regression,
)
from sportsdataverse.scrape.ncaa.parse import wbb_period_model

_RAW = {
    "wbb": ("wehoop-dev/ncaa-wbb-hoops-raw", "wbb"),
    "mbb": ("hoopR-dev/ncaa-mbb-hoops-raw", "mbb"),
}
# Workspace root holding the sibling -raw / -data checkouts. Resolution order:
# --workspace-root, then $SDV_WORKSPACE_ROOT, then inferred from this file's
# location (<root>/<org-dir>/<repo>/ops/build_rapm.py). Never a hardcoded path.
_ROOT = Path(
    os.environ.get("SDV_WORKSPACE_ROOT") or Path(__file__).resolve().parents[3]
)

_DATA = {
    "wbb": ("wehoop-dev/ncaa-wbb-hoops-data", "wbb", "ncaa_wbb"),
    "mbb": ("hoopR-dev/ncaa-mbb-hoops-data", "mbb", "ncaa_mbb"),
}


def di_teams(league: str, season: int) -> "set[str]":
    """Division-I team set for the season, from the published `team_rosters`.

    Same definition the identity layer uses: a team with a roster is D-I. This
    is not cosmetic filtering -- rating everyone who appears on the floor
    silently wrecks the whole distribution. Measured on WBB 2024:

        scope       n      mean      sd    max|rating|
        ALL       5836    -1.849   5.072      33.3
        D-I only  4081    -0.028   2.188       9.2
        non-D-I   1755    -6.083   6.984      33.3

    D-I alone centres at ~0 with sd 2.19 -- the shape RAPM should have. The
    non-D-I teams are D2/D3 exhibition opponents: genuinely much worse AND
    enormously noisy, because each plays one or two tracked games. Including
    them moved the mean by 1.8 points and nearly tripled the spread.
    """
    repo, lg, stem = _DATA[league]
    f = _ROOT / repo / lg / "team_rosters" / "parquet" / f"{stem}_team_rosters_{season}.parquet"
    if not f.is_file():
        return set()
    return set(pl.read_parquet(f)["team"].unique().to_list())


def raw_season_dir(league: str, season: int) -> Path:
    repo, lg = _RAW[league]
    return _ROOT / repo / lg / "raw" / str(season)


def game_events(path: Path, league: str) -> "dict[str, list]":
    """Parse one bundle into ``{team: [LineupEvent, ...]}`` for both teams.

    A team whose box lineup or stint parse fails is skipped rather than
    aborting the game -- the other team's events are still usable, matching the
    per-family robustness contract of the raw parse stage.
    """
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            bundle = json.load(fh)
    except (OSError, json.JSONDecodeError, EOFError):
        return {}
    pages = bundle.get("pages") or {}
    pbp_html, box_html = pages.get("play_by_play"), pages.get("individual_stats")
    if not pbp_html or not box_html:
        return {}
    cid = str(bundle.get("contest_id") or path.stem)

    model = wbb_period_model(bundle.get("season")) if league == "wbb" else None
    kw = {"period_model": model} if model else {}
    try:
        pbp = parse_ncaa_bb_game_pbp(pbp_html, cid, **kw)
    except Exception:  # noqa: BLE001 -- one bad game must not kill a season
        return {}
    if not pbp.height:
        return {}

    out: "dict[str, list]" = {}
    for team in (pbp["home"][0], pbp["away"][0]):
        if not team:
            continue
        box_lineup = get_box_lineup(f"individual_stats_{cid}.html", box_html, TeamId(team), format_version=1)
        if isinstance(box_lineup, list):  # list[ParseError]
            continue
        res = create_lineup_data(f"pbp_{cid}.html", pbp_html, box_lineup, format_version=1)
        if isinstance(res, list):
            continue
        good, _bad = res
        if good:
            out.setdefault(team, []).extend(good)
    return out


def _worker(args):
    """Returns the per-team events, or None when the game FAILED to parse.

    Returning ``{}`` for a failure made it indistinguishable from a game that
    legitimately produced no events, so a run with silently broken games still
    reported complete coverage in its manifest.
    """
    path, league = args
    try:
        return {t: evs for t, evs in game_events(Path(path), league).items()}
    except Exception:  # noqa: BLE001
        return None


def league_baseline(all_buckets: "dict[str, list]") -> "tuple[float, float]":
    """Possession-weighted D1 mean of ``off_adj_ppp`` / ``def_adj_ppp``.

    `calc_lineup_outputs` documents its offsets as "the D1-average value for
    `field` (the regression's starting/baseline value on the RHS)". Passing 0.0
    makes every lineup's FULL efficiency (~100) the residual, which shifts every
    rating by roughly the league mean -- the first run centred at -2.39 instead
    of ~0. Deriving the baseline from the same buckets keeps it honest rather
    than assuming the 100.0 convention.
    """
    num_o = den_o = num_d = den_d = 0.0
    for buckets in all_buckets.values():
        for b in buckets:
            for key, poss_key, (num, den) in (
                ("off_adj_ppp", "off_poss", ("o", "o")),
                ("def_adj_ppp", "def_poss", ("d", "d")),
            ):
                v = (b.get(key) or {}).get("value")
                w = (b.get(poss_key) or {}).get("value")
                if v is None or not w:
                    continue
                if num == "o":
                    num_o += float(v) * float(w)
                    den_o += float(w)
                else:
                    num_d += float(v) * float(w)
                    den_d += float(w)
    return (num_o / den_o if den_o else 100.0, num_d / den_d if den_d else 100.0)


def team_rapm(
    team: str,
    events: list,
    ridge_lambda: float = 1.0,
    off_offset: float = 100.0,
    def_offset: float = 100.0,
) -> "list[dict]":
    """Run the engine for one team-season -> per-player RAPM rows."""
    buckets = agg.lineup_stats_buckets(events)
    if not buckets:
        return []
    report = lineup_to_team_report({"lineups": buckets, "error_code": None})
    ctx = build_player_context(
        report.get("players") or [],
        buckets,
        {},  # players_baseline -- no NCAA per-player baselines exist
        {},  # stats_averages
        100.0,
        "value",
        DEFAULT_RAPM_CONFIG,
    )
    if not ctx:
        return []
    codes = list(ctx.get("col_to_player") or [])
    if not codes:
        return []

    # X (off, def): one row per filtered lineup, one column per player, each
    # cell sqrt(lineup_poss / side_poss) -- the possession weighting is already
    # inside the design matrix, so the solve is an ordinary ridge.
    weights = calc_player_weights(ctx)
    # y: possession-weighted residual of each lineup vs the team baseline.
    outputs = calc_lineup_outputs("adj_ppp", off_offset, def_offset, ctx)

    ratings = []
    for side, X, y in zip(("off", "def"), weights, outputs):
        try:
            solver = slow_regression(X, ridge_lambda, ctx)
            ratings.append(calculate_rapm(solver, list(y)))
        except Exception as exc:  # noqa: BLE001 -- a singular team must not kill the season
            print(f"    {team}: {side} solve failed ({type(exc).__name__}) -- skipped", flush=True)
            ratings.append(None)

    off, dfn = ratings
    rows = []
    for i, code in enumerate(codes):
        rows.append(
            {
                "team": team,
                "player_code": code,
                "rapm_off": float(off[i]) if off is not None and i < len(off) else None,
                "rapm_def": float(dfn[i]) if dfn is not None and i < len(dfn) else None,
                "team_off_poss": float(
                    (ctx.get("team_info", {}).get("off_poss") or {}).get("value") or 0.0
                ),
                "num_players": int(ctx.get("num_players") or 0),
            }
        )
    for r in rows:
        if r["rapm_off"] is not None and r["rapm_def"] is not None:
            r["rapm_net"] = r["rapm_off"] - r["rapm_def"]
        else:
            r["rapm_net"] = None
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=sorted(_RAW), required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--team", default=None, help="Restrict to one team (proof run).")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--workspace-root",
        default=None,
        help="Root holding the sibling -raw/-data checkouts (or $SDV_WORKSPACE_ROOT).",
    )
    ap.add_argument(
        "--all-teams",
        dest="di_only",
        action="store_false",
        help="Rate every team on the floor, including non-D-I. Off by default: "
        "non-D-I teams shift the mean 1.8 pts and nearly triple the spread.",
    )
    ap.set_defaults(di_only=True)
    args = ap.parse_args(argv)
    if args.workspace_root:
        global _ROOT
        _ROOT = Path(args.workspace_root)

    d = raw_season_dir(args.league, args.season)
    if not d.is_dir():
        print(f"ERROR: no raw tree at {d}", file=sys.stderr)
        return 2
    files = sorted(d.glob("*.json.gz"))
    if args.limit:
        files = files[: args.limit]
    print(f"  {args.league} {args.season}: {len(files)} games, workers={args.workers}", flush=True)

    failed = 0
    by_team: "defaultdict[str, list]" = defaultdict(list)
    payload = [(str(f), args.league) for f in files]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for i, res in enumerate(ex.map(_worker, payload, chunksize=8), 1):
                if res is None:
                    failed += 1
                    continue
                for t, evs in res.items():
                    by_team[t].extend(evs)
                if i % 500 == 0:
                    print(f"    {i}/{len(files)} games, {len(by_team)} teams", flush=True)
    else:
        for i, p in enumerate(payload, 1):
            res = _worker(p)
            if res is None:
                failed += 1
                continue
            for t, evs in res.items():
                by_team[t].extend(evs)
            if i % 100 == 0:
                print(f"    {i}/{len(files)} games, {len(by_team)} teams", flush=True)

    # The BASELINE set and the OUTPUT set are different things. `--team` must
    # narrow only what gets WRITTEN: if it also narrowed the baseline, the
    # league offset would be computed from one team and that team's ratings
    # would not match its ratings in a full run.
    baseline_teams = sorted(by_team)
    if args.di_only:
        di = di_teams(args.league, args.season)
        if di:
            before = len(baseline_teams)
            baseline_teams = [t for t in baseline_teams if t in di]
            print(f"  D-I scope: {len(baseline_teams)}/{before} teams kept", flush=True)
        else:
            # Fail closed. Rating everyone silently wrecks the distribution
            # (see di_teams: ALL -> mean -1.85 / max|r| 33.3 vs D-I -0.03 / 9.2),
            # and a run that quietly did that is worse than no run.
            print(
                "ERROR: --di-only is set but no team_rosters were found, so D-I "
                "scope cannot be applied. Pass --all-teams to rate every team "
                "deliberately.",
                file=sys.stderr,
            )
            return 2

    if args.team and args.di_only and args.team not in baseline_teams:
        print(
            f"ERROR: --team {args.team!r} is not in the D-I scope for "
            f"{args.league} {args.season}. Rating an out-of-scope team against a "
            f"D-I baseline is not meaningful; pass --all-teams to do it anyway.",
            file=sys.stderr,
        )
        return 2
    teams = [args.team] if args.team else baseline_teams

    # One pass to bucket every BASELINE team, so the D1 baseline is measured on
    # the same data the ratings are fit to rather than assumed.
    buckets_by_team = {
        t: agg.lineup_stats_buckets(by_team[t]) for t in baseline_teams if by_team.get(t)
    }
    off_base, def_base = league_baseline(buckets_by_team)
    print(f"  D1 baseline adj_ppp: off={off_base:.2f} def={def_base:.2f}", flush=True)

    rows = []
    for t in teams:
        evs = by_team.get(t) or []
        if not evs:
            print(f"    {t}: no events", flush=True)
            continue
        r = team_rapm(t, evs, off_offset=off_base, def_offset=def_base)
        rows.extend(r)
        if args.team:
            print(f"    {t}: {len(evs)} events -> {len(r)} rated players", flush=True)

    df = pl.DataFrame(rows) if rows else pl.DataFrame()
    out = Path(args.out) if args.out else Path(__file__).parent / "out"
    out.mkdir(parents=True, exist_ok=True)
    # write_parquet overwrites silently, so a --team/--limit proof run would
    # otherwise replace a complete season. Partial runs get their own name.
    # The suffix marks PROVENANCE, so it is applied even with --out (which
    # chooses the directory, not the name). Otherwise `--team X --out <dir>`
    # writes the canonical season filename and a one-team frame can later be
    # published as if it were a complete season.
    suffix = ""
    if args.team:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", args.team).strip("-").lower()
        suffix += f"__team-{slug}"
    if args.limit:
        suffix += f"__limit-{args.limit}"
    f = out / f"ncaa_{args.league}_rapm_{args.season}{suffix}.parquet"
    if suffix:
        print(f"  PARTIAL run -> {f.name} (not the full-season output)", flush=True)
    # Remove any prior manifest BEFORE the parquet changes. An interruption
    # between the two writes must leave NO manifest (-> refused), never the
    # previous run's manifest sitting beside a new parquet.
    mf_path = f.with_suffix(".manifest.json")
    mf_path.unlink(missing_ok=True)
    df.write_parquet(f)

    # Completion manifest. The filename suffix proves a run was DECLARED
    # partial; it cannot prove a run that claimed to be full actually finished.
    # An interrupted or truncated full run writes the canonical name with fewer
    # teams and would otherwise be indistinguishable from a complete season.
    # The manifest records what the run actually covered, and the publisher
    # refuses to ship a season without one.
    manifest = {
        "league": args.league,
        "season": args.season,
        "partial": bool(args.team or args.limit),
        "team": args.team,
        "limit": args.limit or None,
        "di_only": bool(args.di_only),
        "games_available": len(sorted(d.glob("*.json.gz"))),
        "games_processed": len(files),
        "baseline_teams": len(baseline_teams),
        "teams_rated": len(teams),
        "games_failed": failed,
        "rows": int(df.height),
        "parquet": f.name,
        # Binds the manifest to THIS file. A row count alone cannot tell a
        # changed parquet from the one the run produced.
        "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
    }
    mf_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"  manifest -> {mf_path.name}", flush=True)
    print(f"  teams={len(teams)} rated_rows={df.height} -> {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
