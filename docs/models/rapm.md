# NCAA WBB RAPM — model documentation

Two deliberately different estimands, published on separate tags (never merge):

| estimand | tag | assets | stage |
|---|---|---|---|
| League-wide (Path B — every D-I player on one scale) | `ncaa_wbb_rapm` | 52 per-season parquet | `python/ncaa_wbb_model_01_rapm_league.py` |
| Within-team (Path A — apportions one team's performance) | `ncaa_wbb_rapm_within_team` | 55 per-season parquet | `python/ncaa_wbb_model_02_rapm_within_team.py` |

## Features / design

Ridge regression (`lambda = 1000`) over the possession-level on/off design
matrix built from this repo's published `possessions` + `team_rosters` +
`name_changes` trees (league-wide) or the raw-bundle lineup reconstruction via
the sdv-py hoop-explorer engine (within-team). Seasons 2011-2026; 2010 is
excluded by the usable-possession gate, not by a season list.

## Gates + observed results (frozen from the 2026-08-24 full validation sweep)

Publish-blocking — a failed season writes NOTHING; floors may only be RAISED
(`--min-spearman` refuses lower values):

| gate | floor | observed |
|---|---|---|
| usable-possession fraction | >= 0.65 | 2011+ min 0.7609 |
| intercept era band (scale-bug catcher) | [83, 98] | 87.31-92.80 |
| home-court advantage band | [1.0, 4.0] | in-band all seasons |
| Torvik external (league-wide only) | >= 250 joined teams AND Spearman(team_net, adjem) >= 0.89 | min 0.9039 (the 2021 COVID season) |

Within-team has NO Torvik gate (different estimand, not comparable); its shape
is proven by the committed sdv-py e2e lineup-aggregation test. Oracle fixture:
`ops/oracle/ncaa_wbb_torvik.parquet` — a NaN rho or missing oracle season is a
FAILURE, never a skip.

**WBB carve-out:** seasons 2011-2020 are `UNGATED_SEASONS` for the external gate only — Torvik has no women's ratings pre-2021. Internal gates (usable fraction, level bands) still apply; rows carry `external_gate="ungated_no_oracle"`.

## Operability

League-wide retrain: `.github/workflows/ncaa_wbb_models.yml` (dispatch +
annual post-season cron). Within-team stays manual by design (needs the raw
HTML bundle checkout). Each run appends `models/ledger.jsonl`. Single home for
the stage list: `models/manifest.yaml`.

## Figures

None committed yet — calibration / distribution figures are a recorded
follow-up for the next full build (this doc carries the numeric results in
the meantime).
