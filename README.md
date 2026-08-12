# ncaa-wbb-hoops-data

Python producer that reshapes [`ncaa-wbb-hoops-raw`](https://github.com/sportsdataverse/ncaa-wbb-hoops-raw)'s
parsed `stats.ncaa.org` men's basketball JSON into season-level tidy datasets.
The upstream source is `stats.ncaa.org` (via the bigballR port in sdv-py) --
**not** ESPN; NCAA contest ids are strings, not ESPN ints. Sister repo to the
wehoop (WNBA) and hoopR (NBA/WBB) data producers -- same build -> publish
shape, different sport/league.

## Datasets

Eleven datasets, keyed in `config.REGISTRY`. Six are DIRECT extracts of a
top-level key in each game's parsed JSON; the other five are DERIVED — built
from those same parsed payloads, from the raw roster files, or from the
crosswalk, rather than from one named family.

Listed in stage order. That order is `config.REGISTRY` insertion order, which
`--dataset all` iterates, so it is also the order a full build runs in:
identity/reference frames first, then per-game events and box, then the
lineup-grain frames. It is a **reading order, not a dependency chain** — no
dataset is built from another dataset's OUTPUT, so any one can be built alone
in any order (`--dataset shots` works on its own).

| NN | dataset | type | description |
| --- | --- | --- | --- |
| 01 | `team_ids` | derived | stats.ncaa.org team-id crosswalk for the season, from the bundled sdv-py `ncaa_wbb_team_ids` table. Reads no games at all. |
| 02 | `schedule` | derived | One row per game (home/away/date/final score). Built from each payload's `pbp` **family** — the parsed JSON has no schedule family. |
| 03 | `team_rosters` | derived | Per-team season rosters, read from the raw repo's captured roster JSON (not from a parsed-game family). |
| 04 | `rosters` | derived | Distinct `(team, player)` pairs per season with a games-played count. Built from each payload's `player_box` **family**, because the parsed tree has no roster family and sdv-py's roster parser needs roster HTML this tree doesn't hold. |
| 05 | `pbp` | direct | Play-by-play, one row per event. |
| 06 | `player_box` | direct | Per-player box score, one row per player/game. |
| 07 | `team_box` | direct | Per-team box score, one row per team/game. |
| 08 | `lineups` | direct | On-court five-man units by stint. |
| 09 | `matchup_stints` | derived | One row per constant-10-man floor segment, with score/possession deltas. `home_lineup_key`/`away_lineup_key` join to `lineups.lineup_key`. |
| 10 | `possessions` | direct | Possession-level rollup. |
| 11 | `shots` | direct | Shot events with location. |

Two of the reference frames read a per-game **family** rather than a dedicated
one: `schedule` from `pbp` and `rosters` from `player_box`. That is a content
lineage, not a build dependency — both re-derive from the raw payloads, so
they are still buildable before stages 05/06 ever run. They sit early because
they are dimension tables you join everything else to.

## Run order

1. **Build** -- reshapes the raw JSON and writes parquet in-repo under
   `wbb/{dataset}/parquet/ncaa_wbb_{dataset}_{season}.parquet` (committed).
2. **Publish** -- uploads parquet + csv.gz + rds as release assets to
   `sportsdataverse/sportsdataverse-data` (not committed; requires `gh` auth).

```bash
# Build all 11 datasets for a season
uv run python -m ncaa_wbb_data_build build --dataset all --season 2026

# Build one dataset
uv run python -m ncaa_wbb_data_build build --dataset shots --season 2026

# Build + publish (uploads release assets)
uv run python -m ncaa_wbb_data_build build --dataset all --season 2026 --publish
```

Or the launcher scripts, which set up logging and the raw-root env:

```bash
SEASON=2026 bash scripts/run_build.sh
SEASON=2026 DATASET=shots bash scripts/run_build.sh   # single dataset

SEASON=2026 bash scripts/run_publish.sh                # build + publish
```

`NCAA_WBB_RAW_ROOT` points at the sibling `ncaa-wbb-hoops-raw` checkout (the
launchers default it to `../ncaa-wbb-hoops-raw`); an HTTP fallback is used
when that checkout isn't available locally.

## Format policy

- **parquet**: committed in-repo under `wbb/{dataset}/parquet/` as
  `ncaa_wbb_{dataset}_{season}.parquet`, always written on every build.
  The `ncaa_wbb_` prefix matches the release tag, so a downloaded asset keeps
  its provenance in the filename instead of colliding with every other
  league's `pbp_2026.parquet`.
- **parquet + csv.gz + rds**: published as release assets to
  `sportsdataverse/sportsdataverse-data`, tagged `ncaa_wbb_{dataset}` (e.g.
  `ncaa_wbb_pbp`). Uploaded one file at a time via
  `gh release upload <tag> <file> --repo sportsdataverse/sportsdataverse-data --clobber`,
  creating the release if it doesn't exist yet. csv/rds are staged under the
  gitignored `wbb/_release_build/` and are re-derivable from the committed
  parquet -- they are never committed.
- **The release csv is GZIPPED (`.csv.gz`), deliberately.** One season of `pbp`
  is ~3.1M rows and writes a **2.03 GB** plain csv -- 99% of GitHub's 2 GiB
  per-asset hard limit, so a season slightly longer than 2025-26 would fail to
  upload outright. Gzip takes it to ~100 MB (21x). `espn_cfb_model_pbp` already
  ships `.csv.gz` on the same release repo. Read one with
  `pl.read_csv(gzip.open(path, "rb"))`, or `readr::read_csv()` in R (which
  decompresses transparently).
- **rds** requires R with the `arrow` package (`Rscript` shells out to
  `arrow::read_parquet` -> `saveRDS`). Resolution order: `SDV_RSCRIPT` env,
  then `RSCRIPT` env, then `Rscript` on `PATH`, then a scan of
  `C:/Program Files/R/R-*/bin/Rscript.exe`. RDS conversion failure (e.g. no R
  install has `arrow`) only logs a warning -- it never blocks the parquet+csv.gz
  upload.

## Requirements / credentials

- [`uv`](https://docs.astral.sh/uv/) for everything -- never bare `python`/`pip`.
- The `sportsdataverse` dependency resolves to the local `../../sdv-py`
  sibling checkout (editable): NCAA parsers aren't on PyPI yet. Swap to the
  PyPI pin in `pyproject.toml` once a release ships NCAA support.
- Publishing needs `gh` authenticated with a token: `GH_TOKEN`, `GITHUB_PAT`,
  or `SDV_GH_TOKEN` (checked in that order; `run_publish.sh` also falls back
  to `~/.Renviron`).
- RDS conversion needs an R install with `arrow` on `PATH` (or `SDV_RSCRIPT`
  pointed at one).

## Tests

Hermetic, offline, no network: 8 fixture games under
`tests/fixtures/raw_root/wbb/json/` plus an `mbb_schedule_master.parquet`
for season `2026`. `team_ids` reads the bundled sdv-py crosswalk, so it's
offline too.

```bash
uv run pytest -q
```

`tests/test_e2e.py` builds all 11 datasets from the fixtures into a temp
directory and asserts each parquet is written, non-empty, schema-stable
across the write/read round-trip, and holds the dtype-discipline contract
(`contest_id`/`id` as Utf8, `season` as Int64).

## sdv-py loader wiring (deferred)

Wiring these datasets into sdv-py's `mbb_loaders` is a follow-up task, done
*after* the first real publish. The loader introspects the live published
parquet's footer schema, so it can't be generated until a real `ncaa_wbb_*`
release exists on `sportsdataverse/sportsdataverse-data`.
