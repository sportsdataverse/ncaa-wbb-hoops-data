"""Stage 02 — within-team RAPM (Path A — apportions one team's performance).

Thin numbered entry over ``ops/build_rapm.py`` (gates run inside it,
publish-blocking; a failed season writes nothing). Appends a
``models/ledger.jsonl`` line per run. No fingerprint skip: the inputs are this
repo's living published trees — they change without a code change, and a skip
would be silent staleness.

Usage::

    python python/ncaa_wbb_model_02_rapm_within_team.py --help  # forwards args verbatim
    scripts/ncaa_wbb_models.sh 02
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
    sys.argv = ["build_rapm.py", *argv]
    rc = 0
    try:
        runpy.run_path(str(ROOT / "ops" / "build_rapm.py"), run_name="__main__")
    except SystemExit as exc:  # ops scripts exit via sys.exit(main())
        rc = int(exc.code or 0)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": "rapm_within_team",
        "estimand": "within-team",
        "argv": argv,
        "rc": rc,
        "gates": "run inside ops/build_rapm.py (publish-blocking)",
        "in_published_data": False,
    }
    ledger = ROOT / "models" / "ledger.jsonl"
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
