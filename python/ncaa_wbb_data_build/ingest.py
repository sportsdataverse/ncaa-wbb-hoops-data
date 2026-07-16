"""Read the ncaa-wbb-hoops-raw tree -- from a sibling checkout OR over HTTP.

The Python producer prefers the sibling checkout on disk (sdv-build-data
convention); when unavailable, ``raw_root`` may instead be the
``raw.githubusercontent.com`` base URL (``config.RAW_HTTP_BASE``). Parsed
game payloads -- the 7-key dict the raw repo's ``ncaa_parse.write_parsed``
produces (``contest_id``, ``pbp``, ``lineups``, ``player_box``, ``team_box``,
``shots``, ``possessions``) -- live at ``{raw_root}/wbb/json/{contest_id}.json``;
the season contest-id index at ``{raw_root}/wbb/schedule_master.parquet``.

NCAA contest ids are strings, not ESPN ints -- ``contest_id`` stays Utf8
everywhere, never cast to Int64.

HTTP mode details: per-game JSON is cached under ``$NCAA_WBB_CACHE``
(default ``.ncaa_wbb_raw_cache``, gitignored) so repeated dataset builds
don't re-fetch the same payloads; ``schedule_master.parquet`` is small and
fetched fresh every call.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import polars as pl

from ncaa_wbb_data_build.config import RAW_ROOT_ENV


def _resolve_root(explicit: str | Path | None) -> Path | str:
    """Resolve the ncaa-wbb-hoops-raw root (arg > env): a local Path or a base URL."""
    val = explicit or os.environ.get(RAW_ROOT_ENV)
    if not val:
        raise RuntimeError(
            f"set {RAW_ROOT_ENV} to the ncaa-wbb-hoops-raw checkout root or its "
            f"raw.githubusercontent base URL, or pass raw_root="
        )
    if isinstance(val, str) and val.startswith(("http://", "https://")):
        return val.rstrip("/")
    return Path(val)


def raw_root(explicit: str | Path | None = None) -> Path | str:
    """Resolve the ncaa-wbb-hoops-raw root (arg > env): a local Path or a base URL."""
    return _resolve_root(explicit)


def _http_get_bytes(url: str) -> bytes | None:
    """GET ``url`` -> bytes; ``None`` on any failure (R tryCatch parity)."""
    import requests

    try:
        resp = requests.get(url, timeout=60)
    except requests.RequestException:
        return None
    return resp.content if resp.status_code == 200 else None


def _cache_root() -> Path:
    return Path(os.environ.get("NCAA_WBB_CACHE", ".ncaa_wbb_raw_cache"))


def read_parsed(contest_id: str, *, raw_root: str | Path | None = None) -> dict | None:
    """Read one game's parsed JSON; ``None`` if absent/malformed (R tryCatch parity).

    Returns the parser's 7-key contract dict as-is -- never reshaped. HTTP
    mode caches each payload under ``$NCAA_WBB_CACHE``.
    """
    root = _resolve_root(raw_root)
    rel = f"wbb/json/{contest_id}.json"
    if isinstance(root, Path):
        f = root / rel
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None
    cached = _cache_root() / rel
    if cached.exists():
        try:
            return json.loads(cached.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None
    # `root` is the resolved HTTP base -- honor an explicit raw_root= URL
    # instead of silently falling back to the RAW_HTTP_BASE default.
    body = _http_get_bytes(f"{root}/json/{contest_id}.json")
    if body is None:
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    try:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(body)
    except OSError:
        pass  # cache is best-effort; the payload is already in hand
    return payload


def season_contest_ids(season: int, *, raw_root: str | Path | None = None) -> list[str]:
    """Sorted, de-duplicated contest ids for ``season`` from ``schedule_master.parquet``.

    ``season`` in the schedule is Utf8 (``str(ending_year)``, e.g. the
    2024-25 season is stored as ``"2025"``). Returns ``[]`` if the parquet
    is absent or the season matched nothing.
    """
    root = _resolve_root(raw_root)
    rel = "wbb/schedule_master.parquet"
    if isinstance(root, Path):
        f = root / rel
        if not f.exists():
            return []
        df = pl.read_parquet(f)
    else:
        # Same fix as read_parsed: use the resolved root, not the hardcoded
        # default, so an explicit raw_root= URL is honored.
        body = _http_get_bytes(f"{root}/schedule_master.parquet")
        if body is None:
            return []
        df = pl.read_parquet(io.BytesIO(body))
    df = df.filter(pl.col("season") == str(season))
    return sorted(df.get_column("contest_id").unique().to_list())
