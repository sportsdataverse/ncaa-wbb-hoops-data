"""Stage 01 — league-wide RAPM (Path B — every D-I player on one scale).

Thin numbered entry over ``ops/build_rapm_league.py`` (gates run inside it,
publish-blocking; a failed season writes nothing). Appends a
``models/ledger.jsonl`` line per run. No fingerprint skip: the inputs are this
repo's living published trees — they change without a code change, and a skip
would be silent staleness.

Usage::

    python python/ncaa_wbb_model_01_rapm_league.py --all  # or --season 2025
    scripts/ncaa_wbb_models.sh 01
"""
from __future__ import annotations

import json
import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    sys.argv = ["build_rapm_league.py", "--league", "wbb", *argv]
    rc = 0
    try:
        runpy.run_path(str(ROOT / "ops" / "build_rapm_league.py"), run_name="__main__")
    except SystemExit as exc:  # ops scripts exit via sys.exit(main())
        rc = int(exc.code or 0)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": "rapm_league",
        "estimand": "league-wide",
        "argv": argv,
        "rc": rc,
        "gates": "run inside ops/build_rapm_league.py (publish-blocking)",
        "in_published_data": False,
    }
    ledger = ROOT / "models" / "ledger.jsonl"
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
