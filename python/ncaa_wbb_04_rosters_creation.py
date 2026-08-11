"""Stage 04 -- rosters.

Thin shim over the tested build package: the pipeline logic lives in
``ncaa_wbb_data_build.build``; this file exists so the stage sequence is readable from a
directory listing.

Stage numbers follow the ``REGISTRY`` order in ``ncaa_wbb_data_build/config.py``, which
reads the way you would rebuild a season from scratch: identity/reference
frames first, then the per-game event and box extracts, then the lineup-grain
frames that index into them. That is a READING order, not a dependency chain
-- no dataset is built from another dataset's output, so any one of them can
be built on its own. ``--dataset all`` builds every dataset in one CLI
invocation, following this same sequence.

Equivalent to::

    python -m ncaa_wbb_data_build build --dataset rosters --season <year>
"""

from __future__ import annotations

import sys

from ncaa_wbb_data_build.cli import main

DATASET = "rosters"

if __name__ == "__main__":
    # DATASET is appended, not prepended: argparse keeps the LAST occurrence of
    # an option, so a stray --dataset on the command line cannot make stage
    # 04 build something other than rosters.
    sys.exit(main([*sys.argv[1:], "--dataset", DATASET]))
