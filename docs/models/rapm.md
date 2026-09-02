# NCAA WBB RAPM — league-wide and within-team


Two deliberately different RAPM estimands publish from this repository
on separate release tags (never merged): **league-wide**
(`ncaa_wbb_rapm`, Path B — every D-I player on one
points-per-100-possessions scale) and **within-team**
(`ncaa_wbb_rapm_within_team`, Path A — how one team’s performance
apportions across its own players; not comparable across teams by
construction). Every published row carries an `estimand` column so the
two can never be silently conflated. This document is the reproducible
writeup for the league-wide model, computed at render time from the
local sweep outputs (`ops/out_league/`), the committed evaluation card,
and the committed Torvik oracle fixture.

**Model.** Ridge regression (λ = 1000) over the possession-level on/off
design matrix: each row is a possession, each player an on/off column
(+1 offense, −1 defense), plus intercept and home-court terms. Offensive
and defensive components are estimated jointly; `rapm = orapm + drapm`
on the points-per-100 scale. The regularization strength was fixed by
the 2026-08 validation program — and the fitted value is *asserted* at
run time, because the λ no-op incident (a ridge that silently fit
unregularized) is exactly the class of bug that survives rank-based
checks.

**Uncertainty.** Every published row carries `orapm_se`, `drapm_se` and
`rapm_net_se` — the ridge **posterior** standard errors,
`sqrt(σ̂² · diag((XᵀWX + λI)⁻¹))`, with σ̂² the possession-weighted
residual variance on n − df_eff degrees of freedom (df_eff = trace of
the ridge hat matrix) and the net SE including the O/D posterior
covariance. Under the prior the penalty encodes (β ~ N(0, σ²/λ)) this is
a credible interval for the *true* impact: a low-minute player sits at ≈
0 ± σ̂/√λ (≈ ±3.6 per component) and the interval tightens as the data
separate a player from his lineups. The alternative, the frequentist
sandwich covariance σ̂²·M(XᵀWX)M (its SEs are `sqrt` of the diagonal), is
the *repeatability of the shrunk estimate*: it collapses toward 0 for a
player the ridge pins at zero, so it is not an interval for the truth —
but it is exactly what a refit can check, and the producer computes it
as the calibration instrument for the published SEs (see *Uncertainty*
below). The intercept is treated as fixed (its SE is ≈ 0.14 points per
100).

**Feature engineering lives in the possession construction, not the
regression**: substitution-window stint building, possession trimming
(the usable-possession gate measures how much of a season survives),
free-throw and end-of-period edge handling, and the `name_changes`
identity bridge that keeps a player one column across transfers and name
variants. The intercept and home-court estimates double as **scale-bug
catchers** — a wrong points-per-possession normalization moves them out
of band even when the player ordering (what a Spearman gate sees)
survives.

## Training data

<div id="bukjazhpjj" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#bukjazhpjj table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#bukjazhpjj thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#bukjazhpjj p { margin: 0; padding: 0; }
 #bukjazhpjj .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #bukjazhpjj .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #bukjazhpjj .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #bukjazhpjj .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #bukjazhpjj .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #bukjazhpjj .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #bukjazhpjj .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #bukjazhpjj .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #bukjazhpjj .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #bukjazhpjj .gt_column_spanner_outer:first-child { padding-left: 0; }
 #bukjazhpjj .gt_column_spanner_outer:last-child { padding-right: 0; }
 #bukjazhpjj .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #bukjazhpjj .gt_spanner_row { border-bottom-style: hidden; }
 #bukjazhpjj .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #bukjazhpjj .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #bukjazhpjj .gt_from_md> :first-child { margin-top: 0; }
 #bukjazhpjj .gt_from_md> :last-child { margin-bottom: 0; }
 #bukjazhpjj .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #bukjazhpjj .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #bukjazhpjj .gt_indent_1 { text-indent: 5px; }
 #bukjazhpjj .gt_indent_2 { text-indent: calc(5px * 2); }
 #bukjazhpjj .gt_indent_3 { text-indent: calc(5px * 3); }
 #bukjazhpjj .gt_indent_4 { text-indent: calc(5px * 4); }
 #bukjazhpjj .gt_indent_5 { text-indent: calc(5px * 5); }
 #bukjazhpjj .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #bukjazhpjj .gt_row_group_first td { border-top-width: 2px; }
 #bukjazhpjj .gt_row_group_first th { border-top-width: 2px; }
 #bukjazhpjj .gt_striped { color: #333333; background-color: #F4F4F4; }
 #bukjazhpjj .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #bukjazhpjj .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #bukjazhpjj .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #bukjazhpjj .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #bukjazhpjj .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #bukjazhpjj .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #bukjazhpjj .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #bukjazhpjj .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #bukjazhpjj .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #bukjazhpjj .gt_left { text-align: left; }
 #bukjazhpjj .gt_center { text-align: center; }
 #bukjazhpjj .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #bukjazhpjj .gt_font_normal { font-weight: normal; }
 #bukjazhpjj .gt_font_bold { font-weight: bold; }
 #bukjazhpjj .gt_font_italic { font-style: italic; }
 #bukjazhpjj .gt_super { font-size: 65%; }
 #bukjazhpjj .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #bukjazhpjj .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #bukjazhpjj .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #bukjazhpjj .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #bukjazhpjj .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #bukjazhpjj .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| League-wide RAPM corpus, by season |  |  |  |  |  |
|----|----|----|----|----|----|
| players + possessions from the local sweep outputs; usable% / intercept / HCA from the frozen evaluation card |  |  |  |  |  |
| season | players | player_poss | usable | mu | hca |
| 2011 | 4237 | 6,217,750 | 80.32 | 88.23 | 2.72 |
| 2012 | 4234 | 6,129,260 | 79.64 | 87.42 | 2.62 |
| 2013 | 4223 | 5,874,580 | 76.09 | 87.31 | 2.69 |
| 2014 | 4225 | 6,307,020 | 77.67 | 92.23 | 2.45 |
| 2015 | 4304 | 6,085,370 | 76.23 | 89.77 | 2.53 |
| 2016 | 4308 | 6,204,360 | 77.62 | 89.82 | 2.59 |
| 2017 | 4307 | 6,146,620 | 76.90 | 90.80 | 2.61 |
| 2018 | 4260 | 6,191,440 | 77.60 | 91.68 | 2.26 |
| 2019 | 4404 | 6,809,570 | 84.55 | 91.03 | 2.39 |
| 2020 | 4344 | 6,820,870 | 87.36 | 90.45 | 2.29 |
| 2021 | 4304 | 4,755,550 | 86.78 | 91.67 | 1.84 |
| 2022 | 4666 | 6,780,110 | 86.45 | 90.53 | 2.14 |
| 2023 | 4606 | 7,424,180 | 89.39 | 91.38 | 2.23 |
| 2024 | 4557 | 7,363,970 | 87.49 | 91.72 | 2.31 |
| 2025 | 4623 | 7,491,550 | 88.10 | 91.91 | 2.40 |
| 2026 | 4596 | 7,762,820 | 89.96 | 91.69 | 2.41 |

&#10;</div>

Inputs are this repository’s own published trees: `possessions` (the
stint-level frame the NCAA hoops engine compiles from raw stats.ncaa.org
bundles), `team_rosters`, and `name_changes`. Seasons 2011–2026; 2010
exists upstream but fails the usable-possession gate and is excluded by
the gate rather than a hand list.

## Exploratory data analysis

<img src="rapm_files/figure-commonmark/cell-4-output-1.png" width="420"
height="300"
alt="League-wide RAPM distribution, latest season — ridge shrinkage centers the mass at zero." />

<img src="rapm_files/figure-commonmark/cell-5-output-1.png" width="420"
height="300"
alt="Offensive vs defensive RAPM, latest season — the two components are estimated jointly." />

<img src="rapm_files/figure-commonmark/cell-6-output-1.png" width="420"
height="300"
alt="Shrinkage in action: |RAPM| vs possessions played — low-minute players are pulled to zero." />

## Attribution

There is no SHAP section here, and deliberately so: in an on/off design
the “features” are the players themselves, so the fitted coefficients
*are* the attributions — each player’s RAPM is exactly their estimated
marginal effect on a possession’s outcome, jointly with everyone else’s.
The O/D scatter above is the model’s native attribution decomposition,
and the shrinkage plot shows the prior doing the work SHAP would
otherwise reveal: low-minute players carry near-zero attributed effect
because the data cannot separate them from their lineups.

## Uncertainty

<img src="rapm_files/figure-commonmark/cell-7-output-1.png" width="420"
height="300"
alt="Posterior SE vs possessions, latest season — the SE falls with playing time, then flattens at a collinearity floor (a starter who never sits is confounded with his team’s total)." />

<div id="ozurzmgftk" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#ozurzmgftk table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#ozurzmgftk thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#ozurzmgftk p { margin: 0; padding: 0; }
 #ozurzmgftk .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #ozurzmgftk .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #ozurzmgftk .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #ozurzmgftk .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #ozurzmgftk .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ozurzmgftk .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ozurzmgftk .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ozurzmgftk .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #ozurzmgftk .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #ozurzmgftk .gt_column_spanner_outer:first-child { padding-left: 0; }
 #ozurzmgftk .gt_column_spanner_outer:last-child { padding-right: 0; }
 #ozurzmgftk .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #ozurzmgftk .gt_spanner_row { border-bottom-style: hidden; }
 #ozurzmgftk .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #ozurzmgftk .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #ozurzmgftk .gt_from_md> :first-child { margin-top: 0; }
 #ozurzmgftk .gt_from_md> :last-child { margin-bottom: 0; }
 #ozurzmgftk .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #ozurzmgftk .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #ozurzmgftk .gt_indent_1 { text-indent: 5px; }
 #ozurzmgftk .gt_indent_2 { text-indent: calc(5px * 2); }
 #ozurzmgftk .gt_indent_3 { text-indent: calc(5px * 3); }
 #ozurzmgftk .gt_indent_4 { text-indent: calc(5px * 4); }
 #ozurzmgftk .gt_indent_5 { text-indent: calc(5px * 5); }
 #ozurzmgftk .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #ozurzmgftk .gt_row_group_first td { border-top-width: 2px; }
 #ozurzmgftk .gt_row_group_first th { border-top-width: 2px; }
 #ozurzmgftk .gt_striped { color: #333333; background-color: #F4F4F4; }
 #ozurzmgftk .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ozurzmgftk .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ozurzmgftk .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #ozurzmgftk .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ozurzmgftk .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ozurzmgftk .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #ozurzmgftk .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #ozurzmgftk .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ozurzmgftk .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ozurzmgftk .gt_left { text-align: left; }
 #ozurzmgftk .gt_center { text-align: center; }
 #ozurzmgftk .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #ozurzmgftk .gt_font_normal { font-weight: normal; }
 #ozurzmgftk .gt_font_bold { font-weight: bold; }
 #ozurzmgftk .gt_font_italic { font-style: italic; }
 #ozurzmgftk .gt_super { font-size: 65%; }
 #ozurzmgftk .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ozurzmgftk .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #ozurzmgftk .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ozurzmgftk .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ozurzmgftk .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #ozurzmgftk .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Median posterior SE by possession decile — 2026 |  |  |  |  |
|----|----|----|----|----|
| decile 0 = fewest possessions; the prior SD σ̂/√λ is the ceiling, the collinearity floor the plateau |  |  |  |  |
| decile | n | poss_min | poss_max | median_rapm_net_se |
| 0 | 460 | 1 | 151 | 4.906 |
| 1 | 460 | 151 | 403 | 4.702 |
| 2 | 459 | 404 | 760 | 4.458 |
| 3 | 460 | 760 | 1,177 | 4.228 |
| 4 | 459 | 1,178 | 1,622 | 4.050 |
| 5 | 460 | 1,622 | 2,078 | 3.928 |
| 6 | 460 | 2,080 | 2,444 | 3.871 |
| 7 | 459 | 2,445 | 2,917 | 3.860 |
| 8 | 460 | 2,918 | 3,335 | 3.874 |
| 9 | 459 | 3,335 | 4,678 | 3.894 |

&#10;</div>

The published SE is validated on every season by a **split-half refit**:
the season’s games are split by the parity of `contest_id`
(deterministic and roster-neutral — the halves differ by sampling noise,
not by the development or transfer drift a date split would add), both
halves are refit, and each player rated in both is checked for \|β̂ₐ −
β̂ᵦ\| ≤ 2·sqrt(SEₐ² + SEᵦ²). Under the **sampling** SE this is the
textbook calibration test and the coverage sits at the 0.954 nominal in
every season — σ̂², the inverse and the O/D covariance are right.

Under the published **posterior** SE the same test returns ≈ 1.0
coverage with a standardised-difference SD of ≈ 0.38 rather than 1.0.
Read that plainly: **the published SE is conservative by ≈ 2.5×** (≈
2.3× for 1,000-plus-possession players) relative to how much the
estimate actually moves between two halves of a season. That is not a
defect — at λ = 1000 the fit is prior-dominated, and a credible interval
for the *true* impact is legitimately wider than the *repeatability* of
a shrunk estimate — but it means the posterior coverage number is a
one-sided guard against SEs that silently shrank, never evidence of
nominal calibration.

**What to do with it.** Use `rapm_net ± 2·rapm_net_se` as a deliberately
cautious band: if it excludes zero the player is separated from the
prior by the data, and overlapping bands (as in the leaders table below)
mean a tier, not a ranking. Do NOT read it as the season-to-season or
half-to-half wobble of the number — that spread is ≈ 2.5× tighter, and a
consumer propagating the published SE into a difference-of-two-players
test will be materially over-conservative.

<div id="cpgzzaieor" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#cpgzzaieor table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#cpgzzaieor thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#cpgzzaieor p { margin: 0; padding: 0; }
 #cpgzzaieor .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #cpgzzaieor .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #cpgzzaieor .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #cpgzzaieor .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #cpgzzaieor .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #cpgzzaieor .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cpgzzaieor .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #cpgzzaieor .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #cpgzzaieor .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #cpgzzaieor .gt_column_spanner_outer:first-child { padding-left: 0; }
 #cpgzzaieor .gt_column_spanner_outer:last-child { padding-right: 0; }
 #cpgzzaieor .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #cpgzzaieor .gt_spanner_row { border-bottom-style: hidden; }
 #cpgzzaieor .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #cpgzzaieor .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #cpgzzaieor .gt_from_md> :first-child { margin-top: 0; }
 #cpgzzaieor .gt_from_md> :last-child { margin-bottom: 0; }
 #cpgzzaieor .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #cpgzzaieor .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #cpgzzaieor .gt_indent_1 { text-indent: 5px; }
 #cpgzzaieor .gt_indent_2 { text-indent: calc(5px * 2); }
 #cpgzzaieor .gt_indent_3 { text-indent: calc(5px * 3); }
 #cpgzzaieor .gt_indent_4 { text-indent: calc(5px * 4); }
 #cpgzzaieor .gt_indent_5 { text-indent: calc(5px * 5); }
 #cpgzzaieor .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #cpgzzaieor .gt_row_group_first td { border-top-width: 2px; }
 #cpgzzaieor .gt_row_group_first th { border-top-width: 2px; }
 #cpgzzaieor .gt_striped { color: #333333; background-color: #F4F4F4; }
 #cpgzzaieor .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cpgzzaieor .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #cpgzzaieor .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #cpgzzaieor .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cpgzzaieor .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #cpgzzaieor .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #cpgzzaieor .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #cpgzzaieor .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cpgzzaieor .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #cpgzzaieor .gt_left { text-align: left; }
 #cpgzzaieor .gt_center { text-align: center; }
 #cpgzzaieor .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #cpgzzaieor .gt_font_normal { font-weight: normal; }
 #cpgzzaieor .gt_font_bold { font-weight: bold; }
 #cpgzzaieor .gt_font_italic { font-style: italic; }
 #cpgzzaieor .gt_super { font-size: 65%; }
 #cpgzzaieor .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cpgzzaieor .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #cpgzzaieor .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cpgzzaieor .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #cpgzzaieor .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #cpgzzaieor .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Standard-error gates by season — frozen from the 2026-09-01 sweep (evaluation card) |  |  |  |  |  |  |  |  |  |
|----|----|----|----|----|----|----|----|----|----|
| split-half = odd vs even games; coverage = share of players whose other-half estimate lies within 2·sqrt(SE_A² + SE_B²); z-sd = SD of the standardised difference (1.0 when calibrated) |  |  |  |  |  |  |  |  |  |
| season | σ̂² | ρ(poss, SE) | SE dec 0 | SE dec 9 | cov (posterior) | cov O (sampling) | cov D (sampling) | cov net (sampling) | z-sd (sampling) |
| 2011 | 11,751 | −0.912 | 4.79 | 3.83 | 1.000 | 0.948 | 0.952 | 0.946 | 1.044 |
| 2012 | 11,634 | −0.910 | 4.77 | 3.83 | 1.000 | 0.949 | 0.953 | 0.951 | 1.030 |
| 2013 | 11,740 | −0.922 | 4.80 | 3.85 | 1.000 | 0.944 | 0.947 | 0.943 | 1.038 |
| 2014 | 11,944 | −0.910 | 4.84 | 3.86 | 1.000 | 0.950 | 0.951 | 0.945 | 1.050 |
| 2015 | 11,896 | −0.921 | 4.83 | 3.86 | 1.000 | 0.950 | 0.949 | 0.955 | 1.012 |
| 2016 | 11,952 | −0.917 | 4.85 | 3.87 | 1.000 | 0.951 | 0.953 | 0.943 | 1.042 |
| 2017 | 12,120 | −0.910 | 4.87 | 3.93 | 1.000 | 0.944 | 0.951 | 0.952 | 1.017 |
| 2018 | 12,165 | −0.900 | 4.88 | 3.95 | 1.000 | 0.948 | 0.944 | 0.947 | 1.047 |
| 2019 | 12,245 | −0.891 | 4.90 | 3.92 | 1.000 | 0.950 | 0.952 | 0.949 | 1.035 |
| 2020 | 12,230 | −0.872 | 4.88 | 3.95 | 1.000 | 0.950 | 0.945 | 0.945 | 1.057 |
| 2021 | 12,391 | −0.950 | 4.94 | 4.04 | 1.000 | 0.950 | 0.948 | 0.947 | 1.032 |
| 2022 | 12,215 | −0.912 | 4.89 | 3.92 | 1.000 | 0.948 | 0.956 | 0.951 | 1.013 |
| 2023 | 12,278 | −0.889 | 4.89 | 3.90 | 1.000 | 0.950 | 0.952 | 0.946 | 1.024 |
| 2024 | 12,290 | −0.892 | 4.91 | 3.90 | 1.000 | 0.943 | 0.948 | 0.942 | 1.053 |
| 2025 | 12,408 | −0.891 | 4.92 | 3.92 | 1.000 | 0.944 | 0.952 | 0.942 | 1.042 |
| 2026 | 12,382 | −0.877 | 4.91 | 3.89 | 1.000 | 0.952 | 0.947 | 0.940 | 1.043 |

&#10;</div>

## Evaluation

Two layers, both real. First, the **frozen gates from the 2026-08-24
full validation sweep** (gates 1–4) and the **2026-09-01 standard-error
sweep** (gate 5) — publish-blocking (a failed season writes NOTHING;
floors may only be raised):

| gate | floor | observed (sweep) |
|----|----|----|
| usable-possession fraction | ≥ 0.65 | 2011+ min 0.7609 |
| intercept era band (scale-bug catcher) | \[83, 98\] | 87.31–92.80 |
| home-court advantage band | \[1.0, 4.0\] | in-band all seasons |
| σ̂² era band (SE scale-bug catcher) | \[10000, 14000\] | 11,634–12,408 |
| Spearman(possessions, rapm_net_se) | ≤ −0.80 | −0.950 to −0.872 |
| top-decile median SE \< bottom-decile median SE | strict | ratio 0.794–0.819 |
| split-half coverage, posterior SE (rapm_net) | ≥ 0.95 | ≥ 0.9995 |
| split-half coverage, sampling SE (O, D, net) | \[0.92, 0.98\] | 0.9397–0.9563 |
| Torvik external (league-wide only) | ≥ 250 joined teams AND Spearman(team_net, adjem) ≥ 0.89 | min 0.9039 (the 2021 COVID season) |

<div id="sijgyocvfe" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#sijgyocvfe table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#sijgyocvfe thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#sijgyocvfe p { margin: 0; padding: 0; }
 #sijgyocvfe .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #sijgyocvfe .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #sijgyocvfe .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #sijgyocvfe .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #sijgyocvfe .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #sijgyocvfe .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #sijgyocvfe .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #sijgyocvfe .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #sijgyocvfe .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #sijgyocvfe .gt_column_spanner_outer:first-child { padding-left: 0; }
 #sijgyocvfe .gt_column_spanner_outer:last-child { padding-right: 0; }
 #sijgyocvfe .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #sijgyocvfe .gt_spanner_row { border-bottom-style: hidden; }
 #sijgyocvfe .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #sijgyocvfe .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #sijgyocvfe .gt_from_md> :first-child { margin-top: 0; }
 #sijgyocvfe .gt_from_md> :last-child { margin-bottom: 0; }
 #sijgyocvfe .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #sijgyocvfe .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #sijgyocvfe .gt_indent_1 { text-indent: 5px; }
 #sijgyocvfe .gt_indent_2 { text-indent: calc(5px * 2); }
 #sijgyocvfe .gt_indent_3 { text-indent: calc(5px * 3); }
 #sijgyocvfe .gt_indent_4 { text-indent: calc(5px * 4); }
 #sijgyocvfe .gt_indent_5 { text-indent: calc(5px * 5); }
 #sijgyocvfe .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #sijgyocvfe .gt_row_group_first td { border-top-width: 2px; }
 #sijgyocvfe .gt_row_group_first th { border-top-width: 2px; }
 #sijgyocvfe .gt_striped { color: #333333; background-color: #F4F4F4; }
 #sijgyocvfe .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #sijgyocvfe .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #sijgyocvfe .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #sijgyocvfe .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #sijgyocvfe .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #sijgyocvfe .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #sijgyocvfe .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #sijgyocvfe .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #sijgyocvfe .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #sijgyocvfe .gt_left { text-align: left; }
 #sijgyocvfe .gt_center { text-align: center; }
 #sijgyocvfe .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #sijgyocvfe .gt_font_normal { font-weight: normal; }
 #sijgyocvfe .gt_font_bold { font-weight: bold; }
 #sijgyocvfe .gt_font_italic { font-style: italic; }
 #sijgyocvfe .gt_super { font-size: 65%; }
 #sijgyocvfe .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #sijgyocvfe .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #sijgyocvfe .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #sijgyocvfe .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #sijgyocvfe .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #sijgyocvfe .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Per-season gate results — frozen from the validation sweep (evaluation card) |  |  |  |  |  |  |
|----|----|----|----|----|----|----|
| rho = Spearman(team_net, Torvik AdjEM) on n joined teams; the possession-weighted stint aggregate the gate uses |  |  |  |  |  |  |
| season | usable | players | mu | hca | rho | n |
| 2011 | 80.32 | 4237 | 88.23 | 2.72 | <na> | <na> |
| 2012 | 79.64 | 4234 | 87.42 | 2.62 | <na> | <na> |
| 2013 | 76.09 | 4223 | 87.31 | 2.69 | <na> | <na> |
| 2014 | 77.67 | 4225 | 92.23 | 2.45 | <na> | <na> |
| 2015 | 76.23 | 4304 | 89.77 | 2.53 | <na> | <na> |
| 2016 | 77.62 | 4308 | 89.82 | 2.59 | <na> | <na> |
| 2017 | 76.90 | 4307 | 90.80 | 2.61 | <na> | <na> |
| 2018 | 77.60 | 4260 | 91.68 | 2.26 | <na> | <na> |
| 2019 | 84.55 | 4404 | 91.03 | 2.39 | <na> | <na> |
| 2020 | 87.36 | 4344 | 90.45 | 2.29 | <na> | <na> |
| 2021 | 86.78 | 4304 | 91.67 | 1.84 | 0.9039 | 326.0 |
| 2022 | 86.45 | 4666 | 90.53 | 2.14 | 0.9723 | 339.0 |
| 2023 | 89.39 | 4606 | 91.38 | 2.23 | 0.9841 | 347.0 |
| 2024 | 87.49 | 4557 | 91.72 | 2.31 | 0.9864 | 346.0 |
| 2025 | 88.10 | 4623 | 91.91 | 2.40 | 0.9800 | 349.0 |
| 2026 | 89.96 | 4596 | 91.69 | 2.41 | 0.9823 | 349.0 |

&#10;</div>

**WBB carve-out:** seasons 2011–2020 are `UNGATED_SEASONS` for the
external gate only — Torvik has no women’s ratings before 2021. Internal
gates (usable fraction, level bands) still apply, and published rows for
those seasons carry `external_gate="ungated_no_oracle"`.

Second, a **render-time external check** against the committed Torvik
oracle fixture. The gate’s own `team_net` is a possession-weighted stint
aggregate that needs the full stint frame; this document computes the
closest player-level proxy — each team’s possession-weighted mean of
player RAPM — and holds it against Torvik AdjEM. It is labeled a proxy
precisely because it is not the gate’s aggregate; its job is to show the
external agreement reproduces from the committed artifacts alone:

<div id="hzfksbkaqd" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#hzfksbkaqd table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#hzfksbkaqd thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#hzfksbkaqd p { margin: 0; padding: 0; }
 #hzfksbkaqd .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #hzfksbkaqd .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #hzfksbkaqd .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #hzfksbkaqd .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #hzfksbkaqd .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #hzfksbkaqd .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #hzfksbkaqd .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #hzfksbkaqd .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #hzfksbkaqd .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #hzfksbkaqd .gt_column_spanner_outer:first-child { padding-left: 0; }
 #hzfksbkaqd .gt_column_spanner_outer:last-child { padding-right: 0; }
 #hzfksbkaqd .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #hzfksbkaqd .gt_spanner_row { border-bottom-style: hidden; }
 #hzfksbkaqd .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #hzfksbkaqd .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #hzfksbkaqd .gt_from_md> :first-child { margin-top: 0; }
 #hzfksbkaqd .gt_from_md> :last-child { margin-bottom: 0; }
 #hzfksbkaqd .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #hzfksbkaqd .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #hzfksbkaqd .gt_indent_1 { text-indent: 5px; }
 #hzfksbkaqd .gt_indent_2 { text-indent: calc(5px * 2); }
 #hzfksbkaqd .gt_indent_3 { text-indent: calc(5px * 3); }
 #hzfksbkaqd .gt_indent_4 { text-indent: calc(5px * 4); }
 #hzfksbkaqd .gt_indent_5 { text-indent: calc(5px * 5); }
 #hzfksbkaqd .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #hzfksbkaqd .gt_row_group_first td { border-top-width: 2px; }
 #hzfksbkaqd .gt_row_group_first th { border-top-width: 2px; }
 #hzfksbkaqd .gt_striped { color: #333333; background-color: #F4F4F4; }
 #hzfksbkaqd .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #hzfksbkaqd .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #hzfksbkaqd .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #hzfksbkaqd .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #hzfksbkaqd .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #hzfksbkaqd .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #hzfksbkaqd .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #hzfksbkaqd .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #hzfksbkaqd .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #hzfksbkaqd .gt_left { text-align: left; }
 #hzfksbkaqd .gt_center { text-align: center; }
 #hzfksbkaqd .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #hzfksbkaqd .gt_font_normal { font-weight: normal; }
 #hzfksbkaqd .gt_font_bold { font-weight: bold; }
 #hzfksbkaqd .gt_font_italic { font-style: italic; }
 #hzfksbkaqd .gt_super { font-size: 65%; }
 #hzfksbkaqd .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #hzfksbkaqd .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #hzfksbkaqd .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #hzfksbkaqd .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #hzfksbkaqd .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #hzfksbkaqd .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Render-time external check — possession-weighted player-RAPM proxy vs Torvik AdjEM |  |  |
|----|----|----|
| proxy aggregate (not the gate's stint-weighted team_net); computed from committed artifacts on every render |  |  |
| season | joined_teams | proxy_spearman |
| 2021 | 326 | 0.9039 |
| 2022 | 339 | 0.9723 |
| 2023 | 347 | 0.9841 |
| 2024 | 346 | 0.9864 |
| 2025 | 349 | 0.9800 |
| 2026 | 349 | 0.9823 |

&#10;</div>

<img src="rapm_files/figure-commonmark/cell-12-output-1.png" width="420"
height="300"
alt="Team proxy aggregate vs Torvik AdjEM, latest season." />

## Results

<div id="tktaeichco" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#tktaeichco table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#tktaeichco thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#tktaeichco p { margin: 0; padding: 0; }
 #tktaeichco .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #tktaeichco .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #tktaeichco .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #tktaeichco .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #tktaeichco .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #tktaeichco .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tktaeichco .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #tktaeichco .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #tktaeichco .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #tktaeichco .gt_column_spanner_outer:first-child { padding-left: 0; }
 #tktaeichco .gt_column_spanner_outer:last-child { padding-right: 0; }
 #tktaeichco .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #tktaeichco .gt_spanner_row { border-bottom-style: hidden; }
 #tktaeichco .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #tktaeichco .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #tktaeichco .gt_from_md> :first-child { margin-top: 0; }
 #tktaeichco .gt_from_md> :last-child { margin-bottom: 0; }
 #tktaeichco .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #tktaeichco .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #tktaeichco .gt_indent_1 { text-indent: 5px; }
 #tktaeichco .gt_indent_2 { text-indent: calc(5px * 2); }
 #tktaeichco .gt_indent_3 { text-indent: calc(5px * 3); }
 #tktaeichco .gt_indent_4 { text-indent: calc(5px * 4); }
 #tktaeichco .gt_indent_5 { text-indent: calc(5px * 5); }
 #tktaeichco .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #tktaeichco .gt_row_group_first td { border-top-width: 2px; }
 #tktaeichco .gt_row_group_first th { border-top-width: 2px; }
 #tktaeichco .gt_striped { color: #333333; background-color: #F4F4F4; }
 #tktaeichco .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tktaeichco .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #tktaeichco .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #tktaeichco .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tktaeichco .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #tktaeichco .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #tktaeichco .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #tktaeichco .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tktaeichco .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #tktaeichco .gt_left { text-align: left; }
 #tktaeichco .gt_center { text-align: center; }
 #tktaeichco .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #tktaeichco .gt_font_normal { font-weight: normal; }
 #tktaeichco .gt_font_bold { font-weight: bold; }
 #tktaeichco .gt_font_italic { font-style: italic; }
 #tktaeichco .gt_super { font-size: 65%; }
 #tktaeichco .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tktaeichco .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #tktaeichco .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tktaeichco .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #tktaeichco .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #tktaeichco .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Top 15 league-wide RAPM — 2026 (min 800 possessions) |  |  |  |  |  |  |  |  |
|----|----|----|----|----|----|----|----|----|
| points per 100 possessions; SE = posterior standard error, interval = RAPM ± 2·SE; no public headshot CDN exists for stats.ncaa.org player ids |  |  |  |  |  |  |  |  |
| Player | Team | Poss | O-RAPM | D-RAPM | RAPM | SE | 95% lo | 95% hi |
| SARAH.STRONG | UConn | 3,908 | 11.23 | 8.44 | 19.67 | 3.89 | 11.89 | 27.45 |
| MADISON.BOOKER | Texas | 4,648 | 8.53 | 9.21 | 17.74 | 3.84 | 10.06 | 25.43 |
| AZZI.FUDD | UConn | 4,166 | 8.04 | 8.95 | 16.99 | 3.91 | 9.16 | 24.82 |
| JOYCE.EDWARDS | South Carolina | 4,515 | 8.33 | 7.52 | 15.85 | 3.81 | 8.24 | 23.46 |
| GABRIELA.JAQUEZ | UCLA | 4,009 | 8.72 | 6.03 | 14.75 | 3.76 | 7.24 | 22.27 |
| HANNAH.HIDALGO | Notre Dame | 4,621 | 6.84 | 7.68 | 14.52 | 4.14 | 6.25 | 22.80 |
| MADINA.OKOT | South Carolina | 3,356 | 8.93 | 4.96 | 13.89 | 3.70 | 6.49 | 21.28 |
| JORDAN.LEE | Texas | 4,510 | 8.86 | 4.61 | 13.48 | 3.81 | 5.86 | 21.09 |
| MILAYSIA.FULWILEY | LSU | 3,123 | 6.47 | 6.95 | 13.42 | 3.64 | 6.14 | 20.69 |
| ASHLYNN.SHADE | UConn | 3,881 | 4.69 | 8.40 | 13.09 | 3.71 | 5.67 | 20.52 |
| AUBREY.GALVAN | Vanderbilt | 4,332 | 9.87 | 3.12 | 12.99 | 3.98 | 5.03 | 20.95 |
| GIANNA.KNEEPKENS | UCLA | 3,713 | 8.22 | 4.68 | 12.90 | 3.74 | 5.41 | 20.39 |
| CHARLISSE.LEGERWALKER | UCLA | 3,731 | 7.70 | 5.02 | 12.72 | 3.72 | 5.28 | 20.15 |
| RAEGAN.BEERS | Oklahoma | 3,342 | 7.15 | 5.55 | 12.70 | 3.81 | 5.07 | 20.33 |
| TESSA.JOHNSON | South Carolina | 3,899 | 8.46 | 4.23 | 12.70 | 3.75 | 5.20 | 20.19 |

&#10;</div>

RAPM is a retrodictive on/off estimate: low-minute players shrink
heavily toward zero, multicollinearity between players who always share
the floor is resolved only by the prior, and the external Torvik gate
validates TEAM-level aggregation, not individual ordering — which is why
the results table applies a possession floor before ranking anyone. The
intervals make the point directly: the top-15 bands overlap almost
entirely, so the table is a tier, not a ranking.

## Provenance & reproducibility

- **Trained on:** this repository’s published `possessions` +
  `team_rosters` + `name_changes` trees, seasons 2011–2026 (2010
  excluded by the usable-possession gate).
- **Model:** ridge (λ = 1000, asserted at run time) via the league-blind
  sdv-py `mbb_ncaa_rapm_league` engine (WBB passes its own frames; there
  is no twin); league-wide stage
  `python/ncaa_wbb_model_01_rapm_league.py`, within-team stage
  `python/ncaa_wbb_model_02_rapm_within_team.py` (manual by design —
  needs the raw HTML bundle checkout).
- **Standard errors:** posterior `sqrt(σ̂²·diag((XᵀWX+λI)⁻¹))` from one
  dense Cholesky inverse of the (2P+1)-square penalised Gram matrix
  (≈10k, seconds); the sampling SE `sqrt(diag(σ̂²(M − λM²)))` —
  `σ̂²(M − λM²)` is the sampling COVARIANCE matrix — comes from the same
  inverse and drives the split-half calibration gate (gate 5). Engine:
  sdv-py `mbb_ncaa_rapm_league.solve_rapm_league` /
  `split_half_se_check`.
- **Gates:** frozen in the table above; oracle fixture
  `ops/oracle/ncaa_wbb_torvik.parquet` (a NaN rho or missing oracle
  season is a FAILURE, never a skip). Runs append `models/ledger.jsonl`;
  publish is a separate deliberate step (`ops/publish_rapm_league.py`).
- **Retrain:** `scripts/ncaa_wbb_models.sh 01` /
  `.github/workflows/ncaa_wbb_models.yml` (dispatch + annual post-season
  cron). Single home: `models/manifest.yaml`.
- **Rebuild this document:** `scripts/render_model_docs.sh` (Quarto →
  GFM; `uv sync --group docs`); reads only committed/local artifacts —
  fully offline.

## Avenues for improvement & open issues

- **Luck adjustment** — 3P% luck-adjusting the target is still open (the
  other half of this item, informative priors instead of a flat ridge,
  is answered by the SPM-prior result below).
- **Resolved (2026-09-01, PR \#17):** exact standard errors — the ridge
  posterior SEs are published as `orapm_se` / `drapm_se` /
  `rapm_net_se`, validated by a split-half calibration gate (sampling-SE
  coverage at the 0.954 nominal in every season) and shown as ±2·SE
  intervals above. Finding worth keeping: at λ = 1000 the posterior SE
  is ≈2.3× the estimate’s repeatability even for 4,000-possession
  players — the prior, not the data, sets most of the interval.
- **Within-team CI** — Path A still requires the raw HTML bundle
  checkout; a store-backed runner would let it join the wired retrain.
- **Resolved (2026-09-02, PR \#19):** multi-year RAPM is built and
  **measured**, and the premise this item was written on turned out to
  be wrong. A decayed-weight stacked design (seasons *t−2…t* in one fit,
  columns keyed by the cross-season `person_id`, season *s* weighted
  `decay^(t−s)` with `decay = 0.75`, each season offset to *t*’s scoring
  level) beats the single-season baseline on out-of-sample game-margin
  MAE by **0.280 points per game** over 12,398 held-out games, better in
  10/10 seasons, pooled game-cluster bootstrap 95% CI excluding zero.
  Next-season Spearman for returning players rises 0.4497 → 0.4657.
  **But the gain is NOT concentrated in the low-possession tail.** The
  absolute Spearman gain is flat across playing time — +0.015 in the
  \<100-possession bin and +0.014 in the 1500+ bin — so there is no
  possession threshold above which it stops helping. It is a uniform
  variance reduction, not a tail stabiliser. The *relative* gain is
  largest in the tail only because the baseline is near zero there
  (0.0963 → 0.1252 for \<200 possessions vs 0.5228 → 0.5374 for 1000+);
  those are different claims and should not be conflated. **Not wired
  into this producer yet, on purpose:** pooling changes what `σ̂²`
  measures (weighted residual variance under decay weights — 7,733 vs
  the single-season 13,212, measured on the MBB twin, against this
  league’s publish-blocking gate band of \[10000, 14000\]), so the
  estimator flip needs its own WBB sweep to re-derive that band, plus a
  season-*t* filter on the published frame, and it republishes 52 live
  assets.
- **SPM-prior RAPM (2026-09-02, PR \#19) — measured, engine support
  shipped, not yet the producer default.** Shrinking toward a box-score
  plus/minus estimate instead of toward zero
  (`solve_rapm_league(prior_mean=…)`, a re-centring that leaves λ and
  every `*_se` column untouched) is worth **0.239 points per game** of
  margin error out-of-sample and lifts next-season Spearman 0.4497 →
  0.4731; combined with multi-year it is **0.442** and 0.4852. It has a
  real threshold at roughly **100 possessions**: +0.03…+0.06 Spearman in
  every bin above it, and -0.005 below it — under ~100 possessions a
  player’s box *rates* are themselves noise, so the prior is a
  confident-looking centre made of noise. Exposure shrink
  `poss/(poss+k)` with `k = 0` was chosen on held-out development
  seasons. Full pre-registered design, all three criteria, and the
  leakage boundaries: `ops/experiments/rapm_stabilization.py`
  (re-runnable) and the ClaudeCowork ledger
  `2026-09-01-writeup-improvements/reports/rapm-stabilization.md`.
