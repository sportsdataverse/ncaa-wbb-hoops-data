"""Direct family extractor -- NCAA's parsed families are already tidy.

Unlike WNBA (which reshapes raw ESPN JSON through per-family helpers), the
NCAA parser already emits tidy per-family row lists. The only job here is to
build a frame from those rows and pin ``contest_id``/``season`` onto it.
"""

from __future__ import annotations

import polars as pl


def extract_family(
    final: dict, family: str, *, season: int, contest_id: str
) -> pl.DataFrame:
    """Build the family's frame from one game's parsed JSON, tagged with contest_id/season.

    ``contest_id`` always overwrites any value already present in the rows,
    pinning it to Utf8 (dtype discipline: contest_id is Utf8 everywhere).
    An empty family still returns the two literal columns so
    ``pl.concat(..., how="diagonal_relaxed")`` across games works even when
    some games have an empty family.
    """
    rows = final.get(family) or []
    if not rows:
        # pl.DataFrame([]) is 0x0 -- with_columns would broadcast the
        # literals to 1 row instead of 0. Build the empty frame with an
        # explicit 0-row schema so it stays concat-safe.
        return pl.DataFrame(schema={"contest_id": pl.Utf8, "season": pl.Int64})
    frame = pl.DataFrame(rows)
    return frame.with_columns(
        pl.lit(contest_id, dtype=pl.Utf8).alias("contest_id"),
        pl.lit(season, dtype=pl.Int64).alias("season"),
    )
