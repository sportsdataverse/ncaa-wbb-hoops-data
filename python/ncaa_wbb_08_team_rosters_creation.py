"""Stage 08 -- team_rosters.

Thin shim over the tested build package: the pipeline logic lives in
``ncaa_wbb_data_build.build``; this file exists so the stage sequence is readable from a
directory listing.

Stage numbers follow the ``REGISTRY`` order in ``ncaa_wbb_data_build/config.py``, which is
the intended build order -- the DERIVED datasets (built from other datasets,
not extracted directly from parsed-JSON) sort after the DIRECT per-game
extracts they can depend on. The number is a stable dataset identity, NOT an
execution schedule: ``--dataset all`` builds every dataset in one CLI
invocation and remains the sequence truth.

Equivalent to::

    python -m ncaa_wbb_data_build build --dataset team_rosters --season <year>
"""

from __future__ import annotations

import sys

from ncaa_wbb_data_build.cli import main

DATASET = "team_rosters"

if __name__ == "__main__":
    # DATASET is appended, not prepended: argparse keeps the LAST occurrence of
    # an option, so a stray --dataset on the command line cannot make stage
    # 08 build something other than team_rosters.
    sys.exit(main([*sys.argv[1:], "--dataset", DATASET]))
