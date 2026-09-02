# Model registry

One row per published RAPM estimand (Track C step 1). Gate definitions live in
the fitting scripts' docstrings (`ops/build_rapm_league.py`); floors were
frozen from the 2026-08-24 full validation sweep (34 league-seasons,
non_di=drop, lambda=1000) and are **never lowered** — `--min-spearman` may
only RAISE them. `tests/test_model_registry.py` keeps this table in lockstep.

| model | artifact(s) | release tag | training data | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| League-wide RAPM (Path B — `estimand` = every D-I player on one scale) | per-season parquet, **52 assets**; additive columns `orapm_se` / `drapm_se` / `rapm_net_se` (ridge-posterior SEs, 2026-09-01); **estimator (2026-09-02)** = the **flat single-season ridge** — pooling is measured and better on point estimates but fails gate 5(b) here (see below), so this league is NOT in `POOLED_LEAGUES` | `ncaa_wbb_rapm` | this repo's published `possessions` + `team_rosters` + `name_changes` trees, 2011–2026 (2010 excluded by gate 1, not by a season list) | `ops/build_rapm_league.py` (stages 1–2) → `ops/publish_rapm_league.py` (stage 3) | publish-blocking, a failed season writes NOTHING: usable-possession ≥ **0.65** (obs 2011+ min 0.7609); intercept era band **[83, 98]** (obs 87.31–92.80) + hca **[1.0, 4.0]** — scale-bug catchers Spearman can't see; Torvik external: ≥ 250 joined teams AND Spearman(team_net, adjem) ≥ **0.89** (obs min 0.9039, the 2021 COVID season); **WBB 2011–2020 are `UNGATED_SEASONS`** (Torvik has no women's ratings pre-2021) — still under gates 1–2, marked `external_gate="ungated_no_oracle"` in the manifest; **SE gate (2026-09-01)**: σ̂² era band **[10000, 14000]** (obs 11,634–12,408), with the pooled band **[10000, 14000]** re-derived from the 14-season 2026-09-02 pooled sweep (obs 11,742.7 in 2013 – 12,400.3 in 2026) but unused here, Spearman(poss, rapm_net_se) ≤ **−0.80** (obs −0.950 to −0.872), top-decile median SE < bottom-decile, split-half (odd/even games) coverage ≥ **0.95** under the posterior SE (obs ≥ 0.9995) and in **[0.92, 0.98]** under the sampling SE for O/D/net (obs 0.9397–0.9563, nominal 0.954) | 2026-09-01 (SE columns; coefficients unchanged) | annual cron + dispatch (`.github/workflows/ncaa_wbb_models.yml`) via `python/ncaa_wbb_model_01_rapm_league.py` |
| Within-team RAPM (Path A — apportions one team's performance across its players) | per-season parquet, **55 assets** | `ncaa_wbb_rapm_within_team` | raw NCAA HTML bundles via the sdv-py hoop-explorer engine (`wbb_rapm.build_player_context` + ridge), ES lineup buckets rebuilt from the parse chain | `ops/build_rapm.py` → `ops/publish_rapm.py` | shape proven by the committed e2e lineup-aggregation test in sdv-py; **different estimand** from league-wide — `estimand` column stamped into every row; no Torvik gate (not comparable) | 2026-08-24 | manual by design via `python/ncaa_wbb_model_02_rapm_within_team.py` — needs the raw NCAA HTML bundle checkout, not runner-friendly |

Notes:
- The published `*_se` are POSTERIOR standard errors. Writing `M = (X'WX+λI)⁻¹`, the per-component
  SEs are `orapm_se[i] = sqrt(σ̂²·M[i,i])` and `drapm_se[i] = sqrt(σ̂²·M[P+i,P+i])`. **`rapm_net_se`
  is NOT `sqrt(orapm_se² + drapm_se²)`** — `rapm_net = orapm + drapm` (drapm is already signed
  so higher = better defense), so its variance carries the O/D covariance term:

      rapm_net_se[i] = sqrt(σ̂²·(M[i,i] + M[P+i,P+i] + 2·M[i,P+i]))

  Reproducing the net interval from the two marginal SEs alone gives the WRONG width (O and D
  for the same player are estimated from the same possessions and are correlated). These are a
  credible interval for the true impact under the ridge prior (a low-minute player sits at
  ~0 ± σ̂/√λ). The frequentist sandwich COVARIANCE `σ̂²(M − λM²)` — whose SEs are
  `sqrt(diag(·))`, with the same +2·cov(O,D) term for net — is computed by the engine only to
  calibrate them (split-half gate 5d); it is not published because it collapses to ~0 for a
  player the ridge pins at zero.
- **They are conservative by ≈2.5×** relative to how far the estimate actually moves between two
  halves of a season (split-half z-sd ≈ 0.38, not 1.0) — λ=1000 is prior-dominated. `±2·SE` is a
  cautious band for the true impact; it is NOT the repeatability of the number, so gate 5d's ~1.0
  posterior coverage is a one-sided guard (SEs that shrank), never a claim of nominal calibration.
- The two rows are deliberately different estimands and cross-check each
  other; never merge their tags.
- Oracle fixture: `ops/oracle/ncaa_wbb_torvik.parquet` (join on the
  stats.ncaa.org name). A NaN rho or an undersized/missing oracle season is a
  FAILURE, never a skip — except the explicit `UNGATED_SEASONS` allowlist.
- WBB is HALVES before season 2016 (the quarters model silently empties those
  seasons) — inherited by everything downstream of `possessions`.

## Evaluated, NOT adopted here: multi-year pooling and the SPM prior (2026-09-02)

Both levers measured better than the flat baseline on point estimates (PR #19: pooling
0.280 pts/game of out-of-sample margin error, the SPM prior 0.239, better in 10/10
seasons with CIs excluding zero). MBB turned pooling on; **WBB has not**, and neither
lever is adopted here. Two frozen publish gates say so:

1. **Pooling fails gate 5(b)** — Spearman(possessions, `rapm_net_se`) ≤ **−0.80**. A
   14-season `--all --survey` sweep of the pooled estimator measures
   **−0.7947 (2021)** and **−0.7953 (2024)**, with 2020 / 2025 / 2026 at −0.804 / −0.810
   / −0.806; the whole pooled range is −0.7947…−0.8507 against a flat −0.872…−0.950. At
   WBB's frozen `decay = 0.75` a player's SE is driven mostly by his three-season
   exposure while the published `off_poss` / `def_poss` are the season's, so the
   correlation the gate measures genuinely weakens. Lowering the ceiling would be the
   widening the rules forbid; re-tuning WBB's decay to MBB's 0.5 would be re-tuning a
   hyperparameter frozen on the development seasons in order to pass a gate. Re-pairing
   the gate against the *pooled* exposure is arguably the estimator-consistent test but
   cannot be told apart from changing the test until it passes, so it is recorded, not
   done. MBB is unaffected (pooled −0.8611…−0.9108).
2. **The SPM prior fails gate 5(d)** — the sampling-SE split-half calibration, band
   [0.92, 0.98]. `solve_rapm_league` treats the prior mean `b0` as a fixed constant, so
   the published SE describes `beta − b0` only while `b0` is itself estimated from the
   season's box scores; measured on MBB (`ops/experiments/rapm_se_calibration.py`) the
   coverage drops to 0.798–0.914 with z-sd 1.39–1.53 against a nominal 1.0, i.e. ~35%
   too-narrow intervals. Same conclusion for both leagues.

The pooled σ̂² band was still derived, so it is on record if WBB ever qualifies:
14-season sweep **11,742.7 (2013) … 12,400.3 (2026)** → **[10000, 14000]** by the
±12.5%-and-round-outward rule that reproduces the flat band exactly from its own
extremes. The band is NOT the blocker; gate 5(b) is.

This repo therefore publishes exactly what it published before — the flat single-season
ridge, through the pre-2026-09-02 code path — and `ops/build_rapm_league.py` carries the
pooled machinery, the leakage test and the recorded measurements.

## Operability (Track C steps 2–6)

- `models/manifest.yaml` — single home for the model/stage list (guarded by `tests/test_model_manifest.py`).
- One estimand = one numbered pipeline, flat in `python/` beside the data stages: `ncaa_wbb_model_01_rapm_league.py` / `ncaa_wbb_model_02_rapm_within_team.py`; run subsets with `scripts/ncaa_wbb_models.sh`.
- League-wide retrain is now WIRED: `.github/workflows/ncaa_wbb_models.yml` (dispatch + annual post-season cron). Within-team stays manual by design (raw HTML bundle dependency).
- Fingerprint skip: deliberately NOT used — inputs are living published trees; every run recomputes. Each run appends `models/ledger.jsonl`.
- Step 6: per-season parquet assets live on the release tags; nothing fitted is committed here.
