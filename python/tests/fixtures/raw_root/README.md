# Hermetic raw-root fixture (4 real NCAA WBB games)

Mirrors the `ncaa-wbb-hoops-raw` on-disk tree so `ingest.read_parsed` /
`ingest.season_contest_ids` and later build/e2e tests run fully offline.
Clone of the `ncaa-mbb-hoops-data` template's fixture, retargeted to WBB (see
that repo's `python/tests/fixtures/raw_root/README.md` for the shared
pattern).

- `wbb/json/{contest_id}.json` — the 7-key parsed dict
  (`{contest_id, pbp, lineups, player_box, team_box, shots, possessions}`)
  for 4 games, produced by the Phase-1 raw repo's
  `ncaa_parse.parse_bundle(bundle, league="wbb")` over the committed
  bigballR HTML fixtures at
  `sdv-py/tests/fixtures/ncaa/bigballr/html/{pbp,box,individual_stats}_{cid}.html`.
- `wbb/schedule_master.parquet` — `contest_id` (Utf8), `season` (Utf8,
  `"2025"`), `captured` (Utf8); one row per game.

## Games (all real season 2024-25)

| contest_id | game | why |
|---|---|---|
| 5722355 | South Carolina 92-60 Coppin St. (2024-11-14) | blowout |
| 5732292 | South Carolina 68-62 Michigan (2024-11-04) | close, neutral site |
| 5728709 | Notre Dame 80-70 Texas (2024-12-05) | 1 OT |
| 5733807 | NC State 104-95 Notre Dame (2025-02-23) | 2 OT |

## Why season "2025" — NOT the template's synthetic "2026"

The MBB template stamps a **synthetic** season `"2026"` on all its fixture
games (label only used as a filter key there, decoupled from the games'
real dates). Copying that here would be a real bug: the WBB team-id
crosswalk consumed by `derived.team_ids()` (a later task) has **no 2025-26
row** — `team_ids(2026)` resolves to **0 rows** for WBB, while `team_ids(2025)`
resolves 359. A synthetic "2026" fixture season would silently ship an EMPTY
`team_ids` dataset through a "green" e2e test.

`"2025"` is also **not synthetic** here — all 4 games are genuinely 2024-25
(ending year 2025), so the label matches both the crosswalk's coverage
ceiling and the games' real season.

## Quarter-model verification

`parse_bundle(..., league="wbb")` selects the 4-quarter period model
(`_WBB_PERIOD_MODEL = (4, 600, 300)`) instead of MBB's 2 halves
(`(2, 1200, 300)`). Observed on generation (see regenerate command below):

| contest_id | period-1 end `game_seconds` | max `period` | reading |
|---|---:|---:|---|
| 5722355 | 600 | 4 | regulation, quarters |
| 5732292 | 598 | 4 | regulation, quarters |
| 5728709 | 600 | 5 | 4 quarters + 1 OT |
| 5733807 | 583 | 6 | 4 quarters + 2 OT |

Period-1 ends near 600s (a WBB quarter), not ~1200s (an MBB half) — confirms
the parser used the quarter model, not halves. The raw repo's own
`test_ncaa_parse.py::test_wbb_quarter_period_model_changes_period_length`
proves this is a real per-league discriminator (same page under
`league="mbb"` ends period 1 near 1200s instead).

## Regenerate

Requires sdv-py **main**'s venv — PyPI `sportsdataverse` lacks the NCAA
parsers:

```
PYTHONPATH=<ncaa-wbb-hoops-raw>/python \
  <sdv-py>/.venv/Scripts/python.exe <path-to-generator-script>
```

The generator builds the same bundle shape as the raw repo's
`test_ncaa_parse.py::_fixture_bundle` (`contest_id`, `league="wbb"`,
`season="2024-25"`, `captured_at`, `urls={}`, `pages={play_by_play,
box_score, individual_stats}`), calls `parse_bundle(bundle, league="wbb")`
per game, writes each result to `wbb/json/{contest_id}.json`, and writes
`wbb/schedule_master.parquet` with `season="2025"` (Utf8, ending-year label,
NOT the bundle's `"2024-25"` string) for all 4 rows. The generator is a
one-off script, not part of this package — it is not committed here; see
the Task 2 report (`sdv-py/.superpowers/sdd/ncaa-wbb-data/task-2-report.md`)
for where it currently lives. The parsed contract is stable; column drift in
sdv-py's NCAA parsers is what would require regenerating these files.
