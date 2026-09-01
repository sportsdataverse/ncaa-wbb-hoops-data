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

<div id="scuedkvgik" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#scuedkvgik table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#scuedkvgik thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#scuedkvgik p { margin: 0; padding: 0; }
 #scuedkvgik .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #scuedkvgik .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #scuedkvgik .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #scuedkvgik .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #scuedkvgik .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #scuedkvgik .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #scuedkvgik .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #scuedkvgik .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #scuedkvgik .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #scuedkvgik .gt_column_spanner_outer:first-child { padding-left: 0; }
 #scuedkvgik .gt_column_spanner_outer:last-child { padding-right: 0; }
 #scuedkvgik .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #scuedkvgik .gt_spanner_row { border-bottom-style: hidden; }
 #scuedkvgik .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #scuedkvgik .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #scuedkvgik .gt_from_md> :first-child { margin-top: 0; }
 #scuedkvgik .gt_from_md> :last-child { margin-bottom: 0; }
 #scuedkvgik .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #scuedkvgik .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #scuedkvgik .gt_indent_1 { text-indent: 5px; }
 #scuedkvgik .gt_indent_2 { text-indent: calc(5px * 2); }
 #scuedkvgik .gt_indent_3 { text-indent: calc(5px * 3); }
 #scuedkvgik .gt_indent_4 { text-indent: calc(5px * 4); }
 #scuedkvgik .gt_indent_5 { text-indent: calc(5px * 5); }
 #scuedkvgik .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #scuedkvgik .gt_row_group_first td { border-top-width: 2px; }
 #scuedkvgik .gt_row_group_first th { border-top-width: 2px; }
 #scuedkvgik .gt_striped { color: #333333; background-color: #F4F4F4; }
 #scuedkvgik .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #scuedkvgik .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #scuedkvgik .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #scuedkvgik .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #scuedkvgik .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #scuedkvgik .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #scuedkvgik .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #scuedkvgik .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #scuedkvgik .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #scuedkvgik .gt_left { text-align: left; }
 #scuedkvgik .gt_center { text-align: center; }
 #scuedkvgik .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #scuedkvgik .gt_font_normal { font-weight: normal; }
 #scuedkvgik .gt_font_bold { font-weight: bold; }
 #scuedkvgik .gt_font_italic { font-style: italic; }
 #scuedkvgik .gt_super { font-size: 65%; }
 #scuedkvgik .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #scuedkvgik .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #scuedkvgik .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #scuedkvgik .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #scuedkvgik .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #scuedkvgik .gt_asterisk { font-size: 100%; vertical-align: 0; }
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

## Evaluation

Two layers, both real. First, the **frozen gates from the 2026-08-24
full validation sweep** — publish-blocking (a failed season writes
NOTHING; floors may only be raised):

| gate | floor | observed (sweep) |
|----|----|----|
| usable-possession fraction | ≥ 0.65 | 2011+ min 0.7609 |
| intercept era band (scale-bug catcher) | \[83, 98\] | 87.31–92.80 |
| home-court advantage band | \[1.0, 4.0\] | in-band all seasons |
| Torvik external (league-wide only) | ≥ 250 joined teams AND Spearman(team_net, adjem) ≥ 0.89 | min 0.9039 (the 2021 COVID season) |

<div id="alttkjjxpa" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#alttkjjxpa table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#alttkjjxpa thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#alttkjjxpa p { margin: 0; padding: 0; }
 #alttkjjxpa .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #alttkjjxpa .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #alttkjjxpa .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #alttkjjxpa .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #alttkjjxpa .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #alttkjjxpa .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #alttkjjxpa .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #alttkjjxpa .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #alttkjjxpa .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #alttkjjxpa .gt_column_spanner_outer:first-child { padding-left: 0; }
 #alttkjjxpa .gt_column_spanner_outer:last-child { padding-right: 0; }
 #alttkjjxpa .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #alttkjjxpa .gt_spanner_row { border-bottom-style: hidden; }
 #alttkjjxpa .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #alttkjjxpa .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #alttkjjxpa .gt_from_md> :first-child { margin-top: 0; }
 #alttkjjxpa .gt_from_md> :last-child { margin-bottom: 0; }
 #alttkjjxpa .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #alttkjjxpa .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #alttkjjxpa .gt_indent_1 { text-indent: 5px; }
 #alttkjjxpa .gt_indent_2 { text-indent: calc(5px * 2); }
 #alttkjjxpa .gt_indent_3 { text-indent: calc(5px * 3); }
 #alttkjjxpa .gt_indent_4 { text-indent: calc(5px * 4); }
 #alttkjjxpa .gt_indent_5 { text-indent: calc(5px * 5); }
 #alttkjjxpa .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #alttkjjxpa .gt_row_group_first td { border-top-width: 2px; }
 #alttkjjxpa .gt_row_group_first th { border-top-width: 2px; }
 #alttkjjxpa .gt_striped { color: #333333; background-color: #F4F4F4; }
 #alttkjjxpa .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #alttkjjxpa .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #alttkjjxpa .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #alttkjjxpa .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #alttkjjxpa .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #alttkjjxpa .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #alttkjjxpa .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #alttkjjxpa .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #alttkjjxpa .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #alttkjjxpa .gt_left { text-align: left; }
 #alttkjjxpa .gt_center { text-align: center; }
 #alttkjjxpa .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #alttkjjxpa .gt_font_normal { font-weight: normal; }
 #alttkjjxpa .gt_font_bold { font-weight: bold; }
 #alttkjjxpa .gt_font_italic { font-style: italic; }
 #alttkjjxpa .gt_super { font-size: 65%; }
 #alttkjjxpa .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #alttkjjxpa .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #alttkjjxpa .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #alttkjjxpa .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #alttkjjxpa .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #alttkjjxpa .gt_asterisk { font-size: 100%; vertical-align: 0; }
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

<div id="yaxouijqpg" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#yaxouijqpg table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#yaxouijqpg thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#yaxouijqpg p { margin: 0; padding: 0; }
 #yaxouijqpg .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #yaxouijqpg .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #yaxouijqpg .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #yaxouijqpg .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #yaxouijqpg .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #yaxouijqpg .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #yaxouijqpg .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #yaxouijqpg .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #yaxouijqpg .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #yaxouijqpg .gt_column_spanner_outer:first-child { padding-left: 0; }
 #yaxouijqpg .gt_column_spanner_outer:last-child { padding-right: 0; }
 #yaxouijqpg .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #yaxouijqpg .gt_spanner_row { border-bottom-style: hidden; }
 #yaxouijqpg .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #yaxouijqpg .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #yaxouijqpg .gt_from_md> :first-child { margin-top: 0; }
 #yaxouijqpg .gt_from_md> :last-child { margin-bottom: 0; }
 #yaxouijqpg .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #yaxouijqpg .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #yaxouijqpg .gt_indent_1 { text-indent: 5px; }
 #yaxouijqpg .gt_indent_2 { text-indent: calc(5px * 2); }
 #yaxouijqpg .gt_indent_3 { text-indent: calc(5px * 3); }
 #yaxouijqpg .gt_indent_4 { text-indent: calc(5px * 4); }
 #yaxouijqpg .gt_indent_5 { text-indent: calc(5px * 5); }
 #yaxouijqpg .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #yaxouijqpg .gt_row_group_first td { border-top-width: 2px; }
 #yaxouijqpg .gt_row_group_first th { border-top-width: 2px; }
 #yaxouijqpg .gt_striped { color: #333333; background-color: #F4F4F4; }
 #yaxouijqpg .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #yaxouijqpg .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #yaxouijqpg .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #yaxouijqpg .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #yaxouijqpg .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #yaxouijqpg .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #yaxouijqpg .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #yaxouijqpg .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #yaxouijqpg .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #yaxouijqpg .gt_left { text-align: left; }
 #yaxouijqpg .gt_center { text-align: center; }
 #yaxouijqpg .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #yaxouijqpg .gt_font_normal { font-weight: normal; }
 #yaxouijqpg .gt_font_bold { font-weight: bold; }
 #yaxouijqpg .gt_font_italic { font-style: italic; }
 #yaxouijqpg .gt_super { font-size: 65%; }
 #yaxouijqpg .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #yaxouijqpg .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #yaxouijqpg .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #yaxouijqpg .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #yaxouijqpg .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #yaxouijqpg .gt_asterisk { font-size: 100%; vertical-align: 0; }
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

<img src="rapm_files/figure-commonmark/cell-9-output-1.png" width="420"
height="300"
alt="Team proxy aggregate vs Torvik AdjEM, latest season." />

## Results

<div id="euuxjnafpt" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#euuxjnafpt table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#euuxjnafpt thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#euuxjnafpt p { margin: 0; padding: 0; }
 #euuxjnafpt .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #euuxjnafpt .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #euuxjnafpt .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #euuxjnafpt .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #euuxjnafpt .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #euuxjnafpt .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #euuxjnafpt .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #euuxjnafpt .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #euuxjnafpt .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #euuxjnafpt .gt_column_spanner_outer:first-child { padding-left: 0; }
 #euuxjnafpt .gt_column_spanner_outer:last-child { padding-right: 0; }
 #euuxjnafpt .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #euuxjnafpt .gt_spanner_row { border-bottom-style: hidden; }
 #euuxjnafpt .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #euuxjnafpt .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #euuxjnafpt .gt_from_md> :first-child { margin-top: 0; }
 #euuxjnafpt .gt_from_md> :last-child { margin-bottom: 0; }
 #euuxjnafpt .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #euuxjnafpt .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #euuxjnafpt .gt_indent_1 { text-indent: 5px; }
 #euuxjnafpt .gt_indent_2 { text-indent: calc(5px * 2); }
 #euuxjnafpt .gt_indent_3 { text-indent: calc(5px * 3); }
 #euuxjnafpt .gt_indent_4 { text-indent: calc(5px * 4); }
 #euuxjnafpt .gt_indent_5 { text-indent: calc(5px * 5); }
 #euuxjnafpt .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #euuxjnafpt .gt_row_group_first td { border-top-width: 2px; }
 #euuxjnafpt .gt_row_group_first th { border-top-width: 2px; }
 #euuxjnafpt .gt_striped { color: #333333; background-color: #F4F4F4; }
 #euuxjnafpt .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #euuxjnafpt .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #euuxjnafpt .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #euuxjnafpt .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #euuxjnafpt .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #euuxjnafpt .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #euuxjnafpt .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #euuxjnafpt .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #euuxjnafpt .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #euuxjnafpt .gt_left { text-align: left; }
 #euuxjnafpt .gt_center { text-align: center; }
 #euuxjnafpt .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #euuxjnafpt .gt_font_normal { font-weight: normal; }
 #euuxjnafpt .gt_font_bold { font-weight: bold; }
 #euuxjnafpt .gt_font_italic { font-style: italic; }
 #euuxjnafpt .gt_super { font-size: 65%; }
 #euuxjnafpt .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #euuxjnafpt .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #euuxjnafpt .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #euuxjnafpt .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #euuxjnafpt .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #euuxjnafpt .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Top 15 league-wide RAPM — 2026 (min 800 possessions) |  |  |  |  |  |
|----|----|----|----|----|----|
| points per 100 possessions; no public headshot CDN exists for stats.ncaa.org player ids |  |  |  |  |  |
| Player | Team | Poss | O-RAPM | D-RAPM | RAPM |
| SARAH.STRONG | UConn | 3,908 | 11.23 | 8.44 | 19.67 |
| MADISON.BOOKER | Texas | 4,648 | 8.53 | 9.21 | 17.74 |
| AZZI.FUDD | UConn | 4,166 | 8.04 | 8.95 | 16.99 |
| JOYCE.EDWARDS | South Carolina | 4,515 | 8.33 | 7.52 | 15.85 |
| GABRIELA.JAQUEZ | UCLA | 4,009 | 8.72 | 6.03 | 14.75 |
| HANNAH.HIDALGO | Notre Dame | 4,621 | 6.84 | 7.68 | 14.52 |
| MADINA.OKOT | South Carolina | 3,356 | 8.93 | 4.96 | 13.89 |
| JORDAN.LEE | Texas | 4,510 | 8.86 | 4.61 | 13.48 |
| MILAYSIA.FULWILEY | LSU | 3,123 | 6.47 | 6.95 | 13.42 |
| ASHLYNN.SHADE | UConn | 3,881 | 4.69 | 8.40 | 13.09 |
| AUBREY.GALVAN | Vanderbilt | 4,332 | 9.87 | 3.12 | 12.99 |
| GIANNA.KNEEPKENS | UCLA | 3,713 | 8.22 | 4.68 | 12.90 |
| CHARLISSE.LEGERWALKER | UCLA | 3,731 | 7.70 | 5.02 | 12.72 |
| RAEGAN.BEERS | Oklahoma | 3,342 | 7.15 | 5.55 | 12.70 |
| TESSA.JOHNSON | South Carolina | 3,899 | 8.46 | 4.23 | 12.70 |

&#10;</div>

RAPM is a retrodictive on/off estimate: low-minute players shrink
heavily toward zero, multicollinearity between players who always share
the floor is resolved only by the prior, and the external Torvik gate
validates TEAM-level aggregation, not individual ordering — which is why
the results table applies a possession floor before ranking anyone.

## Provenance & reproducibility

- **Trained on:** this repository’s published `possessions` +
  `team_rosters` + `name_changes` trees, seasons 2011–2026 (2010
  excluded by the usable-possession gate).
- **Model:** ridge (λ = 1000, asserted at run time) via the sdv-py
  `wbb_ncaa_rapm_league` engine; league-wide stage
  `python/ncaa_wbb_model_01_rapm_league.py`, within-team stage
  `python/ncaa_wbb_model_02_rapm_within_team.py` (manual by design —
  needs the raw HTML bundle checkout).
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

- **Luck adjustment and archetype priors** — the two known gaps versus
  the strongest public APM systems (catalogued in the APM research
  corpus): 3P% luck-adjusting the target, and informative priors by
  player archetype instead of a flat ridge.
- **Exact standard errors** — the ridge posterior gives per-player SEs
  almost for free; publishing them would turn point estimates into
  honest intervals.
- **Within-team CI** — Path A still requires the raw HTML bundle
  checkout; a store-backed runner would let it join the wired retrain.
- **Known issue:** multi-year RAPM (stabilizing low-minute players
  across seasons) is unbuilt; single-season estimates stay noisy below
  ~200 possessions.
