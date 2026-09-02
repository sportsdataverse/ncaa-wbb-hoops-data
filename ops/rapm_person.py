"""Re-key resolved possessions from per-season ``player_id`` to cross-season ``person_id``.

A multi-season RAPM design is only pooling if the same human is the same COLUMN
in every season. ``resolve_possessions`` hands back stats.ncaa.org
``player_id``s, which are per-season; ``build_person_keys`` (+ ``name_changes``)
bridges them to a ``person_id``. This module applies that bridge to the ten
on-floor slots and REFUSES to proceed if the bridge does not cover essentially
every slot -- a partial bridge silently merges or drops people, and the failure
would surface only as a wrong rating.

One implementation, shared by the producer and the evaluation harness, so the
identity step under the published estimator and the identity step under the
measurement cannot drift apart.
"""

from __future__ import annotations

import polars as pl

#: The bridge must cover essentially every on-floor slot. Observed on MBB and
#: WBB 2011-2026: 1.000. Below this the pooled design is quietly mis-identified.
PERSON_BRIDGE_FLOOR = 0.999

SLOT_IDS = [f"{side}_{i}_id" for side in ("home", "away") for i in range(1, 6)]


def to_person(
    resolved: pl.DataFrame, bridge: pl.DataFrame, season: int
) -> pl.DataFrame:
    """Replace each slot's ``player_id`` with its ``person_id``.

    Args:
        resolved: ``resolve_possessions`` output for ``season``.
        bridge: ``season`` (Int64) / ``player_id`` / ``person_id``, all Utf8
            except ``season``.
        season: The season ``resolved`` belongs to.

    Returns:
        ``contest_id`` (Int64), ``home``, ``away``, ``poss_team``, ``pts`` and
        the ten slots, now carrying ``person_id``.

    Raises:
        RuntimeError: bridge coverage below :data:`PERSON_BRIDGE_FLOOR`, or a
            ``contest_id`` that is not integer-like.
    """
    key = bridge.filter(pl.col("season") == season).select("player_id", "person_id")
    assert key.schema["player_id"] == pl.Utf8, "bridge player_id must be Utf8"
    out = resolved.select("contest_id", "home", "away", "poss_team", "pts", *SLOT_IDS)
    for slot in SLOT_IDS:
        assert out.schema[slot] == pl.Utf8, f"{slot} must be Utf8 to join the bridge"
        out = (
            out.join(
                key.rename({"player_id": slot, "person_id": f"_{slot}"}),
                on=slot,
                how="left",
            )
            .drop(slot)
            .rename({f"_{slot}": slot})
        )
    filled = pl.sum_horizontal([pl.col(c).is_not_null() for c in SLOT_IDS]).sum()
    before = resolved.select(filled).item()
    after = out.select(filled).item()
    cover = after / before if before else 0.0
    if cover < PERSON_BRIDGE_FLOOR:
        raise RuntimeError(
            f"season {season}: person bridge covers {cover:.4f} of on-floor slots "
            f"< {PERSON_BRIDGE_FLOOR} -- refusing to pool a mis-identified design"
        )
    out = out.select(
        pl.col("contest_id").cast(pl.Int64, strict=False),
        "home",
        "away",
        "poss_team",
        "pts",
        *SLOT_IDS,
    )
    if out.get_column("contest_id").null_count():
        raise RuntimeError(f"season {season}: contest_id is not integer-like")
    return out


def person_to_player(bridge: pl.DataFrame, season: int) -> pl.DataFrame:
    """``person_id`` -> ONE ``player_id`` for ``season`` (the lowest, deterministically).

    The bridge is many-to-one within a season for the handful of people who
    carry two ids (a mid-season name change): 1-16 per season on both leagues.
    A person-keyed fit rates them once, which is correct, so publishing needs a
    single representative id. ``person_id`` is published beside it, so no
    identity is lost.
    """
    return (
        bridge.filter(pl.col("season") == season)
        .select("person_id", "player_id")
        .sort("person_id", "player_id")
        .unique(subset=["person_id"], keep="first", maintain_order=True)
    )
