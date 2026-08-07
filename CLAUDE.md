# CLAUDE.md — ncaa-wbb-hoops-data Development Guide

## Package Overview

This repo is the **reshape stage** for `stats.ncaa.org` women's college
basketball: it turns the parsed per-game JSON produced by
`ncaa-wbb-hoops-raw` into season-level tidy datasets (parquet/csv) and
publishes them as release assets on `sportsdataverse/sportsdataverse-data`.

Pipeline: `stats.ncaa.org -> ncaa-wbb-hoops-raw -> ncaa-wbb-hoops-data [HERE]
-> sportsdataverse-data`.

**The `-raw` / `-data` split is load-bearing: never mix them.** This repo is
**fully offline** — it reads a sibling `ncaa-wbb-hoops-raw` checkout (or
`NCAA_WBB_RAW_ROOT`) and never scrapes `stats.ncaa.org`. If you find yourself
wanting to fetch a page here, the work belongs in `-raw` instead.

`README.md` carries the nine-dataset table (six direct extracts of a parsed-JSON
key, three derived from other datasets), the format policy, and the run order.

**Note the input state:** the sibling `ncaa-wbb-hoops-raw` has no `wbb/raw/` or
`wbb/json/` tree yet — the pbp capture campaign still needs a run — and this
repo's own `wbb/` output tree is currently empty. Builds here will have nothing
to ingest until that lands.

## Layout

```
python/
  ncaa_wbb_data_build/          # the build package (installed by uv sync)
    cli.py  config.py  build.py  ingest.py  derived.py
    reshapers.py  io.py  publish.py  rds.py  _logging.py  __main__.py
  ncaa_wbb_NN_*_creation.py     # numbered stage shims
scripts/      # run_build.sh, run_publish.sh
tests/        # suite + fixtures/ at repo ROOT
wbb/          # the built dataset tree (currently empty)
```

The numbered `ncaa_wbb_NN_*_creation.py` shims are **dataset identity**, not
strict execution order. `tests/test_stage_inventory.py` gates the set.
`config.REGISTRY` is the dataset registry.

## The schedule-master name fallback (do not "clean up")

`ingest.py` resolves the season contest-id index by trying, in order:

```python
names = ("wbb_schedule_master.parquet", "schedule_master.parquet")
```

The prefixed `wbb/wbb_schedule_master.parquet` (D33/D36 master naming) is
**canonical**; the legacy unprefixed `wbb/schedule_master.parquet` is the
fallback. The fallback exists because the **writer** — `ncaa-wbb-hoops-raw` and
sdv-py's `scrape/ncaa/discover.py` — still emits the old name (the raw repo's
tree today holds exactly `wbb/schedule_master.parquet`). **When the writer
renames, the fallback drops.** Removing it before then breaks ingest against
every existing raw checkout.

## Season coverage — the README section is stale

`README.md` has a "The season ceiling: 2025" section claiming the bundled WBB
crosswalk (`sportsdataverse/wbb/data/ncaa_teamids_wbb.csv`, read via
`sportsdataverse.wbb.wbb_ncaa_team_ids.ncaa_wbb_team_ids()`) stops at
2024-25. **That is no longer true** — the crosswalk gained its 2025-26 rows,
and `tests/test_derived.py::test_team_ids_2026_season_is_populated` now locks
that season 2026 resolves like any other (the old `height == 0` assertion was
replaced). The sibling raw repo lifted its matching `MAX_SEASON` guard to 2026
in `f6153441` for the same reason.

Season is an ending-year `Int64` throughout the package, so 2024-25 is season
`2025`. When the crosswalk grows again, the raw repo's `MAX_SEASON` guard must
move with it — a stale guard doesn't fail loudly, it burns a capture campaign.

## Packaging

Root `pyproject.toml` + `uv.lock`. **There is no `requirements.txt`.**

- `sportsdataverse` is pinned to git `main` via `[tool.uv.sources]` — sdv-py's
  NCAA parsers (`ncaa_wbb_team_ids`, etc.) are not on PyPI yet. It is a **git
  source, not a `../../sdv-py` path**: a relative path pin makes the repo
  buildable only on a machine with this exact sibling layout, and fails on CI.
  For local sdv-py work, override with `uv pip install -e ../../sdv-py`.
- CI installs with `uv sync --frozen` — the lockfile is the contract.
- The build package installs from `python/` and exposes the
  `ncaa-wbb-data-build` console script.
- pytest: `testpaths = ["tests"]`.
- ruff: `select = ["E4","E7","E9","F","I"]`, `ignore = ["E712"]` (polars bool
  masks are written `pl.col("c") == True` on purpose), isort
  `known-first-party = ["ncaa_wbb_data_build"]`.

```sh
uv sync --frozen
uv run pytest -q
uv run ruff check python tests

SEASON=2025 bash scripts/run_build.sh                 # build (offline)
SEASON=2025 DATASET=shots bash scripts/run_build.sh
SEASON=2025 bash scripts/run_publish.sh               # build + upload via gh
```

`run_build.sh` defaults `NCAA_WBB_RAW_ROOT` to the sibling
`../ncaa-wbb-hoops-raw` checkout; an already-set value always wins.

## CI

- `.github/workflows/tests.yml` — sparse-checkout (`python`, `tests`,
  `pyproject.toml`, `uv.lock`; the built `wbb/` tree is never read by the
  tests, whose fixtures live in `tests/fixtures/`), then `uv sync --frozen`
  -> `ruff check python tests` -> `pytest -q`.
- `.github/workflows/orphan_scripts.yml` — the shared `sportsdataverse/.github`
  gate: every entry in `scripts/` must be referenced by a runbook, a workflow,
  or another script. Both `run_build.sh` and `run_publish.sh` are documented in
  `README.md` and above.

## Commit Convention

[Conventional Commits](https://www.conventionalcommits.org/):
`type(scope): description`. Common types: `feat`, `fix`, `chore`, `ci`, `docs`,
`refactor`, `test`, `build`. Use `type!:` or a `BREAKING CHANGE:` footer for
breaking changes.

**Never include AI agents or assistants (Claude, Copilot, Cursor, GPT, Gemini,
…) as co-authors.** Omit all `Co-Authored-By` trailers referencing AI tools,
whether the change was generated, refactored, or reviewed with AI assistance —
the human author is the sole attributable contributor. This is hook-enforced.

## Cross-Repo References

- Upstream scraper: `wehoop-dev/ncaa-wbb-hoops-raw`
- MBB twin: `hoopR-dev/ncaa-mbb-hoops-data`
- SDK internals: <https://github.com/sportsdataverse/sportsdataverse-py/blob/main/CLAUDE.md>
