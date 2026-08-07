# ncaa-wbb-hoops-data

Python producer that reshapes [`ncaa-wbb-hoops-raw`](https://github.com/sportsdataverse/ncaa-wbb-hoops-raw)'s
parsed `stats.ncaa.org` women's basketball JSON into season-level tidy datasets.
The upstream source is `stats.ncaa.org` (via the bigballR/wbigballR port in
sdv-py) -- **not** ESPN; NCAA contest ids are strings, not ESPN ints. Sister
repo to the wehoop (WNBA) and hoopR (NBA/MBB) data producers -- same
build -> publish shape, different sport/league; a retarget of
[`ncaa-mbb-hoops-data`](https://github.com/sportsdataverse/ncaa-mbb-hoops-data).

## Datasets

Nine datasets, keyed in `config.REGISTRY`. Six are DIRECT extracts of a
top-level key in each game's parsed JSON; three are DERIVED from other
datasets rather than a parsed-JSON family.

| dataset | type | release tag | description |
|---|---|---|---|
| `pbp` | direct | `ncaa_wbb_pbp` | Play-by-play, one row per event. |
| `lineups` | direct | `ncaa_wbb_lineups` | On-court five-player units by stint. |
| `possessions` | direct | `ncaa_wbb_possessions` | Possession-level rollup. |
| `player_box` | direct | `ncaa_wbb_player_box` | Per-player box score, one row per player/game. |
| `team_box` | direct | `ncaa_wbb_team_box` | Per-team box score, one row per team/game. |
| `shots` | direct | `ncaa_wbb_shots` | Shot events with location. |
| `schedule` | derived | `ncaa_wbb_schedule` | One row per game (home/away/date/final score), built from that game's `pbp`. |
| `rosters` | derived | `ncaa_wbb_rosters` | Distinct `(team, player)` pairs per season, with a games-played count. Built from `player_box` because the parsed-JSON tree has no dedicated roster family -- sdv-py's roster parser needs separately-captured roster HTML this tree doesn't hold. |
| `team_ids` | derived | `ncaa_wbb_team_ids` | stats.ncaa.org team-id crosswalk for the season, from the bundled sdv-py `ncaa_wbb_team_ids` table. |

## The season ceiling: 2025

The bundled WBB team-id crosswalk
(`sportsdataverse/wbb/data/ncaa_teamids_wbb.csv`, read via
`sportsdataverse.wbb.wbb_ncaa_team_ids.ncaa_wbb_team_ids()`) covers seasons
**2009-10 through 2024-25 only** -- there is no 2025-26 row yet. Season is an
ending-year `Int64` throughout this package, so 2024-25 is season `2025`.

Building `team_ids` for season 2026 (2025-26) therefore returns **0 rows**,
silently -- not an error, not a warning that blocks the build. That's why
`tests/test_e2e.py` is pinned to season **2025**, not 2026: a season slip to
2026 would let an empty `team_ids` dataset sail through a "green" e2e
undetected. `test_derived.py` locks both sides of this: `team_ids(2025)` is
non-empty, `team_ids(2026)` is `height == 0`.

This is a **WBB-specific** constraint -- the MBB crosswalk this repo was
retargeted from already carries a 2025-26 row, so `ncaa-mbb-hoops-data`'s
season ceiling is one year ahead. Extending the WBB crosswalk to add a
2025-26 row is a separate sdv-py change, out of scope for this repo; once
that lands, the ceiling here lifts to match.

## Run order

1. **Build** -- reshapes the raw JSON and writes parquet in-repo under
   `wbb/{dataset}/parquet/{dataset}_{season}.parquet` (committed).
2. **Publish** -- uploads parquet + csv + rds as release assets to
   `sportsdataverse/sportsdataverse-data` (not committed; requires `gh` auth).

```bash
# Build all 9 datasets for a season
uv run python -m ncaa_wbb_data_build build --dataset all --season 2025

# Build one dataset
uv run python -m ncaa_wbb_data_build build --dataset shots --season 2025

# Build + publish (uploads release assets)
uv run python -m ncaa_wbb_data_build build --dataset all --season 2025 --publish
```

Or the launcher scripts, which set up logging and the raw-root env:

```bash
SEASON=2025 bash scripts/run_build.sh
SEASON=2025 DATASET=shots bash scripts/run_build.sh   # single dataset

SEASON=2025 bash scripts/run_publish.sh                # build + publish
```

`NCAA_WBB_RAW_ROOT` points at the sibling `ncaa-wbb-hoops-raw` checkout (the
launchers default it to `../ncaa-wbb-hoops-raw`); an HTTP fallback is used
when that checkout isn't available locally.

## Input contract

This repo consumes the output of the Phase-1 raw scraper,
[`ncaa-wbb-hoops-raw`](https://github.com/sportsdataverse/ncaa-wbb-hoops-raw):

- `wbb/json/{contest_id}.json` -- per-game parsed payload (the 7-key dict
  `contest_id`/`pbp`/`lineups`/`player_box`/`team_box`/`shots`/`possessions`).
- `wbb/schedule_master.parquet` -- the season contest-id index (`contest_id`,
  `season` as Utf8 ending-year, `captured`).

`contest_id` is a NCAA string id (not an ESPN int) and stays `Utf8`
everywhere in this package -- never cast to `Int64`.

**No real season data exists yet.** The Phase-1 live backfill against
`stats.ncaa.org` has not been run (it's a user-run job from a
residential IP -- see `ncaa-wbb-hoops-raw`'s README). This builder currently
has only the 4-game hermetic fixture bundled under
`tests/fixtures/raw_root/wbb/` (season 2025). Running `run_build.sh`
against a real `NCAA_WBB_RAW_ROOT` today will only produce whatever games
that checkout happens to have captured.

## Format policy

- **parquet**: committed in-repo under `wbb/{dataset}/parquet/`, always
  written on every build.
- **parquet + csv + rds**: published as release assets to
  `sportsdataverse/sportsdataverse-data`, tagged `ncaa_wbb_{dataset}` (e.g.
  `ncaa_wbb_pbp`). Uploaded one file at a time via
  `gh release upload <tag> <file> --repo sportsdataverse/sportsdataverse-data --clobber`,
  creating the release if it doesn't exist yet. csv/rds are staged under the
  gitignored `wbb/_release_build/` and are re-derivable from the committed
  parquet -- they are never committed.
- **No `ncaa_wbb_*` release exists yet** on `sportsdataverse/sportsdataverse-data`.
  `run_publish.sh` is retargeted and syntax-checked but has never been run for
  real against this repo's datasets.
- **rds** requires R with the `arrow` package (`Rscript` shells out to
  `arrow::read_parquet` -> `saveRDS`). Resolution order: `SDV_RSCRIPT` env,
  then `RSCRIPT` env, then `Rscript` on `PATH`, then a scan of
  `C:/Program Files/R/R-*/bin/Rscript.exe`. **R 4.5.3 has `arrow`; R 4.6.0 does
  not** (as of this writing) -- point `SDV_RSCRIPT` at an arrow-capable
  install if the default resolution picks the wrong one. RDS conversion
  failure (e.g. no R install has `arrow`) only logs a warning -- it never
  blocks the parquet+csv upload.

## Requirements / credentials

- [`uv`](https://docs.astral.sh/uv/) for everything -- never bare `python`/`pip`.
- The `sportsdataverse` dependency resolves to the local `../../sdv-py`
  sibling checkout (editable, `[tool.uv.sources]` in `pyproject.toml`): NCAA
  parsers aren't on PyPI yet. Swap to the PyPI pin in `pyproject.toml` once a
  release ships NCAA support.
- Publishing needs `gh` authenticated with a token: `GH_TOKEN`, `GITHUB_PAT`,
  or `SDV_GH_TOKEN` (checked in that order; `run_publish.sh` also falls back
  to `~/.Renviron`, then `~/Documents/.Renviron`).
- RDS conversion needs an R install with `arrow` on `PATH` (or `SDV_RSCRIPT`
  pointed at one) -- see the format-policy note above on the R 4.5.3 vs 4.6.0
  split.

## Tests

Hermetic, offline, no network: 4 real fixture games under
`tests/fixtures/raw_root/wbb/json/` plus a `schedule_master.parquet`
for season `2025`. `team_ids` reads the bundled sdv-py crosswalk, so it's
offline too.

```bash
uv run pytest -q
```

`tests/test_e2e.py` builds all 9 datasets from the fixtures into a temp
directory and asserts each parquet is written, non-empty, schema-stable
across the write/read round-trip, and holds the dtype-discipline contract
(`contest_id`/`id` as Utf8, `season` as Int64 == 2025). Season is pinned to
2025, not 2026 -- see "The season ceiling" above.

## sdv-py loader wiring (deferred)

Wiring these datasets into sdv-py's `wbb_loaders` is a follow-up task, done
*after* the first real publish. The loader introspects the live published
parquet's footer schema, so it can't be generated until a real `ncaa_wbb_*`
release exists on `sportsdataverse/sportsdataverse-data`.
