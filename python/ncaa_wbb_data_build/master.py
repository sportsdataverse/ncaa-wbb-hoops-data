"""Schedule master + the ``games_in_data_repo`` manifest (spec D34).

Two artifacts, one pass, derived from the same in-memory frame so they cannot
drift:

``wbb/ncaa_wbb_schedule_master.parquet``
    Every contest stats.ncaa.org lists -- the DENOMINATOR, including games
    this repo built nothing from.

``wbb/ncaa_wbb_games_in_data_repo.parquet``
    Only contests present in at least one committed dataset -- the NUMERATOR,
    and what consumers join against.

(A third, ``wbb/ncaa_wbb_schedule_coverage.parquet``, is a per-season roll-up
of the same frame: it is what makes a missing family legible at a glance.)

Where each half comes from:

- The denominator is the RAW repo's ``wbb/wbb_schedule_master.parquet`` (D33),
  read through :func:`ingest.schedule_master`. It is deliberately NOT the
  committed ``schedule`` dataset -- that one is derived from pbp, so it only
  ever contains games this repo already has, i.e. a numerator. Using it as the
  denominator would make coverage 100% by construction.
- Every ``in_*`` flag is stamped from the COMMITTED per-season parquet of that
  dataset (``wbb/{dataset}/parquet/{stem}_{season}.parquet``) -- the exact
  contents of what this repo publishes, not a proxy for it.

The flag SET is derived from the ``REGISTRY`` (``level == "game"``), never
hand-listed, so a dataset added to the registry gets its flag with no wiring
here. Every flag is materialized (``False``, not absent) so a family with zero
coverage -- a season with no ``shots``, or a whole league whose capture
campaign has not run -- is VISIBLE as zeros rather than silently missing.

NCAA contest ids are strings and stay ``Utf8`` end to end. A non-Utf8
``contest_id`` on either side raises instead of being cast: a float-origin id
stringifies as ``"3727922.0"`` and would silently match nothing.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ncaa_wbb_data_build import ingest
from ncaa_wbb_data_build.config import REGISTRY, DatasetSpec

_LEAGUE = "wbb"

#: Game-grain datasets -- the ones that get an ``in_*`` flag.
GAME_LEVEL: tuple[DatasetSpec, ...] = tuple(
    spec for spec in REGISTRY.values() if spec.level == "game"
)

#: The dataset whose committed frame supplies the master's game detail
#: (date / teams / score). One row per contest by construction.
_DETAIL_DATASET = "schedule"
_DETAIL_COLUMNS = ("game_date", "home", "away", "home_score", "away_score")


def flag_columns() -> tuple[str, ...]:
    """The ``in_*`` column set, derived from the registry."""
    return tuple(f"in_{spec.dataset}" for spec in GAME_LEVEL)


def _check_contest_id(df: pl.DataFrame, where: str) -> pl.DataFrame:
    """``contest_id`` must already be Utf8 -- never repair it with a cast."""
    dtype = df.schema.get("contest_id")
    if dtype is None:
        raise ValueError(f"{where}: no contest_id column")
    if dtype != pl.Utf8:
        raise TypeError(
            f"{where}: contest_id is {dtype}, expected Utf8. NCAA contest ids are "
            "strings; casting a numeric id here would join against nothing."
        )
    return df


def _ensure_flags(frame: pl.DataFrame) -> pl.DataFrame:
    """Every registry flag exists and is Boolean: absence must be representable."""
    missing = [pl.lit(False).alias(c) for c in flag_columns() if c not in frame.columns]
    out = frame.with_columns(missing) if missing else frame
    return out.with_columns([pl.col(c).cast(pl.Boolean) for c in flag_columns()])


def season_files(spec: DatasetSpec, base: str | Path) -> list[Path]:
    """Committed per-season parquets for one dataset, oldest season first."""
    d = Path(base) / _LEAGUE / spec.dataset / "parquet"
    return sorted(d.glob(f"{spec.stem}_*.parquet")) if d.is_dir() else []


def committed_contest_ids(spec: DatasetSpec, base: str | Path) -> set[str]:
    """Distinct contest ids across every committed season file of one dataset.

    A dataset whose per-season files carry no ``contest_id`` at all is a
    registry mislabel (``level="game"`` on a season-grain dataset), so it
    raises rather than reporting an empty -- and therefore invisible -- set.
    """
    ids: set[str] = set()
    for path in season_files(spec, base):
        frame = pl.read_parquet(path, columns=["contest_id"])
        _check_contest_id(frame, path.name)
        ids |= set(frame.get_column("contest_id").unique().to_list())
    return ids


def denominator(*, raw_root: str | Path | None = None) -> pl.DataFrame:
    """Every contest the raw schedule master knows about: ``(season, contest_id)``.

    Raises:
        FileNotFoundError: If the raw repo's schedule master is unreadable --
            without it there is no honest denominator, and an empty master
            would understate coverage rather than report it.
    """
    raw = ingest.schedule_master(raw_root=raw_root)
    if raw is None:
        raise FileNotFoundError(
            "no schedule master in the raw checkout; set NCAA_WBB_RAW_ROOT to the "
            "ncaa-wbb-hoops-raw root (or pass raw_root=)"
        )
    _check_contest_id(raw, "raw schedule master")
    return (
        raw.select(
            # season is a calendar year, not an id -- Int64 to match the
            # committed datasets, which all carry it as Int64.
            pl.col("season").cast(pl.Int64),
            pl.col("contest_id"),
        )
        .unique()
        .sort(["season", "contest_id"])
    )


def stamp_from_committed(index: pl.DataFrame, base: str | Path) -> pl.DataFrame:
    """Stamp one ``in_*`` per game-level dataset from its committed parquets."""
    out = _check_contest_id(index, "schedule index")
    for spec in GAME_LEVEL:
        ids = sorted(committed_contest_ids(spec, base))
        out = out.with_columns(
            pl.col("contest_id").is_in(ids).alias(f"in_{spec.dataset}")
        )
    return _ensure_flags(out)


def add_game_detail(index: pl.DataFrame, base: str | Path) -> pl.DataFrame:
    """Left-join date / teams / score from the committed ``schedule`` dataset.

    Left, not inner: a contest with nothing built keeps its row with null
    detail -- that is the whole point of a denominator. When the dataset has
    not been built at all (a league whose capture campaign has not run) the
    detail columns are simply absent, and the master is contest ids + flags.
    """
    spec = REGISTRY[_DETAIL_DATASET]
    paths = season_files(spec, base)
    if not paths:
        return index
    frames = [pl.read_parquet(p) for p in paths]
    detail = pl.concat(frames, how="diagonal_relaxed")
    _check_contest_id(detail, f"{_DETAIL_DATASET} dataset")
    keep = [c for c in _DETAIL_COLUMNS if c in detail.columns]
    detail = detail.select("season", "contest_id", *keep).unique(
        subset=["season", "contest_id"], keep="first"
    )
    if index.schema["season"] != detail.schema["season"]:
        raise TypeError(
            f"season dtype mismatch: index {index.schema['season']} vs "
            f"{_DETAIL_DATASET} {detail.schema['season']}"
        )
    return index.join(detail, on=["season", "contest_id"], how="left")


def build_master(
    *, base: str | Path = ".", raw_root: str | Path | None = None
) -> pl.DataFrame:
    """The D34 master: every contest, with a registry-derived flag per dataset."""
    index = denominator(raw_root=raw_root)
    master = add_game_detail(stamp_from_committed(index, base), base)
    lead = ["season", "contest_id"]
    return master.select(
        *lead, *sorted(c for c in master.columns if c not in lead)
    ).sort(lead)


def games_in_data_repo(master: pl.DataFrame) -> pl.DataFrame:
    """Only contests present in at least one committed dataset."""
    flags = [c for c in master.columns if c.startswith("in_")]
    if not flags:
        return master.head(0)
    return master.filter(pl.any_horizontal([pl.col(c) == True for c in flags]))


def build_coverage(master: pl.DataFrame) -> pl.DataFrame:
    """One row per season: game count, date span, and per-dataset build coverage."""
    flags = sorted(c for c in master.columns if c.startswith("in_"))
    if "season" not in master.columns:
        raise ValueError("master frame has no season column")
    aggs: list[pl.Expr] = [pl.len().alias("n_games")]
    if "game_date" in master.columns:
        # game_date is stats.ncaa.org's "MM/DD/YYYY" string; min/max on the
        # raw text would order 01/2024 before 11/2023, so parse first.
        # strict=False: an unparseable value becomes null, not an error.
        date = pl.col("game_date").str.to_date("%m/%d/%Y", strict=False)
        aggs += [date.min().alias("first_date"), date.max().alias("last_date")]
    aggs += [pl.col(f).mean().alias(f"pct_{f}") for f in flags]
    return master.group_by("season", maintain_order=True).agg(aggs).sort("season")
