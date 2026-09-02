"""Turn ``rapm_stabilization.py``'s JSON into the report tables and the verdict.

The decision rule is the pre-registered one and is applied here, in code, so the
verdict cannot drift from the numbers::

    uv run python ops/experiments/summarize_rapm_stabilization.py <results.json> [...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

VARIANTS = ("baseline", "multi_year", "spm_prior", "multi_year_spm")
FLOOR = {"mbb": 0.93, "wbb": 0.89}


def load(paths: "list[str]") -> list:
    out = []
    for p in paths:
        out.extend(json.loads(Path(p).read_text(encoding="utf-8")))
    return out


def dev_table(recs: list) -> str:
    """Hyperparameter grid: mean C3 MAE over the development seasons."""
    grid: dict = {}
    for r in recs:
        k = (r["decay"], r["shrink_k"])
        for name, v in r["variants"].items():
            grid.setdefault(k, {}).setdefault(name, []).append(v["c3_mae"])
    lines = [
        "| decay | shrink k | " + " | ".join(VARIANTS) + " |",
        "|---|---|" + "---|" * len(VARIANTS),
    ]
    for k in sorted(grid):
        row = [f"{sum(grid[k][n]) / len(grid[k][n]):.4f}" for n in VARIANTS]
        lines.append(f"| {k[0]} | {k[1]:.0f} | " + " | ".join(row) + " |")
    return "\n".join(lines)


def eval_tables(recs: list, league: str) -> "tuple[str, dict]":
    seasons = sorted(r["season"] for r in recs)
    lines = [
        "| season | "
        + " | ".join(f"{n} C3" for n in VARIANTS)
        + " | torvik base/my/spm/both |",
        "|---|" + "---|" * (len(VARIANTS) + 1),
    ]
    wins = {n: 0 for n in VARIANTS}
    pooled: dict = {n: [] for n in VARIANTS}
    torvik_ok = True
    for r in sorted(recs, key=lambda x: x["season"]):
        v = r["variants"]
        for n in VARIANTS:
            pooled[n].append(
                (r["season"], v[n]["c3_mae"], v[n]["c3_diff_mean"], r["n_test_games"])
            )
            if n != "baseline" and v[n]["c3_mae"] < v["baseline"]["c3_mae"]:
                wins[n] += 1
            if v[n]["torvik"] < FLOOR[league]:
                torvik_ok = False
        lines.append(
            f"| {r['season']} | "
            + " | ".join(f"{v[n]['c3_mae']:.4f}" for n in VARIANTS)
            + " | "
            + "/".join(f"{v[n]['torvik']:.3f}" for n in VARIANTS)
            + " |"
        )
    # game-count-weighted pooled MAE (each held-out game counts once)
    summary = {"seasons": seasons, "wins": wins, "torvik_ok": torvik_ok, "pooled": {}}
    for n in VARIANTS:
        num = sum(mae * g for _s, mae, _d, g in pooled[n])
        den = sum(g for *_x, g in pooled[n])
        dnum = sum(d * g for _s, _m, d, g in pooled[n])
        summary["pooled"][n] = {"mae": num / den, "diff": dnum / den, "games": den}
    return "\n".join(lines), summary


def c2_table(recs: list) -> str:
    bins = ("overall", "bin_0", "bin_200", "bin_500", "bin_1000")
    agg: dict = {n: {b: [] for b in bins} for n in VARIANTS}
    for r in recs:
        for n, v in r["variants"].items():
            if "c2" not in v:
                continue
            for b in bins:
                x = v["c2"].get(b)
                if x is not None and x == x:  # not NaN
                    agg[n][b].append(x)
    head = "| variant | overall | <200 poss | 200-500 | 500-1000 | 1000+ |"
    lines = [head, "|---|---|---|---|---|---|"]
    for n in VARIANTS:
        cells = [
            f"{sum(agg[n][b]) / len(agg[n][b]):.4f}" if agg[n][b] else "n/a"
            for b in bins
        ]
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def c1_table(recs: list) -> str:
    bins = ("r", "bin_0", "bin_200", "bin_500", "bin_1000")
    agg: dict = {n: {b: [] for b in bins} for n in VARIANTS}
    for r in recs:
        for n, v in r.get("c1", {}).items():
            for b in bins:
                x = v.get(b)
                if x is not None and x == x:
                    agg[n][b].append(x)
    lines = [
        "| variant | overall | <200 poss | 200-500 | 500-1000 | 1000+ |",
        "|---|---|---|---|---|---|",
    ]
    for n in VARIANTS:
        cells = [
            f"{sum(agg[n][b]) / len(agg[n][b]):.4f}" if agg[n][b] else "n/a"
            for b in bins
        ]
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def verdict(recs: list, summary: dict) -> str:
    """The pre-registered decision rule, applied in code so it cannot drift."""
    n_seasons = len(summary["seasons"])
    need_wins = 8 if n_seasons >= 10 else n_seasons
    out = []
    base_c2 = _mean_c2(recs, "baseline")
    for n in VARIANTS[1:]:
        lo, hi = _pooled_ci(recs, n)
        per_season = sum(1 for r in recs if r["variants"][n]["c3_diff_ci"][1] < 0)
        c2 = _mean_c2(recs, n)
        checks = {
            "C3 pooled diff < 0": summary["pooled"][n]["diff"] < 0,
            f"C3 pooled 95% cluster-bootstrap CI [{lo:+.4f}, {hi:+.4f}] excludes 0": hi < 0,
            f"(supplementary) per-season CI below 0 in {per_season}/{len(recs)} seasons": True,
            f"C3 better in >= {need_wins}/{n_seasons} seasons": summary["wins"][n]
            >= need_wins,
            "C2 overall not lower": c2["overall"] >= base_c2["overall"],
            "torvik floor held": summary["torvik_ok"],
        }
        if n in ("multi_year", "multi_year_spm"):
            checks["C2 <200 bin higher (lever-1 mechanism)"] = (
                c2["bin_0"] > base_c2["bin_0"]
            )
        ok = all(checks.values())
        out.append(f"**{n}: {'WIN' if ok else 'NOT A WIN'}**")
        out += [f"  - {'PASS' if v else 'FAIL'} — {k}" for k, v in checks.items()]
    return "\n".join(out)


def _pooled_ci(recs: list, name: str) -> "tuple[float, float]":
    """The PRE-REGISTERED criterion: one cluster bootstrap over every held-out GAME
    of every evaluation season pooled (2,000 draws, games resampled, never rows)."""
    import numpy as np

    diff = np.concatenate([np.asarray(r["variants"][name]["c3_diff_games"], dtype=float) for r in recs])
    rng = np.random.default_rng(20260902)
    n = len(diff)
    means = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(2000)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _mean_c2(recs: list, name: str) -> dict:
    keys = ("overall", "bin_0", "bin_200", "bin_500", "bin_1000")
    vals = {k: [] for k in keys}
    for r in recs:
        c2 = r["variants"][name].get("c2")
        if not c2:
            continue
        for k in keys:
            x = c2.get(k)
            if x is not None and x == x:
                vals[k].append(x)
    return {k: (sum(v) / len(v) if v else float("nan")) for k, v in vals.items()}


def main(argv: "list[str] | None" = None) -> int:
    argv = argv or sys.argv[1:]
    league = "wbb" if any("wbb" in a for a in argv) else "mbb"
    recs = load(argv)
    if len({(r["decay"], r["shrink_k"]) for r in recs}) > 1:
        print("## Development grid (mean C3 MAE over dev seasons)\n")
        print(dev_table(recs))
        return 0
    tbl, summary = eval_tables(recs, league)
    print(f"## C3 -- out-of-sample game-margin MAE ({league})\n")
    print(tbl)
    print("\n**Pooled over all held-out games**\n")
    print("| variant | MAE | mean paired diff vs baseline | seasons better |")
    print("|---|---|---|---|")
    for n in VARIANTS:
        p = summary["pooled"][n]
        w = (
            "-"
            if n == "baseline"
            else f"{summary['wins'][n]}/{len(summary['seasons'])}"
        )
        print(f"| {n} | {p['mae']:.4f} | {p['diff']:+.4f} | {w} |")
    print(f"\n({summary['pooled']['baseline']['games']} held-out games)\n")
    print("## C2 -- next-season Spearman vs the baseline t+1 fit (mean over seasons)\n")
    print(c2_table(recs))
    print(
        "\n## C1 -- split-half reliability (DIAGNOSTIC; inflated for prior-carrying variants)\n"
    )
    print(c1_table(recs))
    print("\n## Verdict (pre-registered rule, applied in code)\n")
    print(verdict(recs, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
