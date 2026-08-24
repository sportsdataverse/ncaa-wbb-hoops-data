# Torvik team-rating oracle (league-RAPM external gate)

`ncaa_wbb_torvik.parquet` — Bart Torvik women's T-Rank adjusted efficiencies,
**2021–2026 only** (2,085 team-seasons; Torvik's women's coverage starts
2021), crosswalked to stats.ncaa.org team names.

- Source: `https://barttorvik.com/ncaaw/<year>_team_results.csv` (the static
  CSV; `trank.php?csv=1` returns HTTP-200 HTML and must not be used).
- Captured 2026-08-18 by sdv-py `dev/ncaa_rapm/build_oracle.py` (greedy
  claim-consuming name matcher, ≈97% of D-I matched; unmatched tail is
  paren-disambiguated one-offs, deliberately not fuzzy-matched). Regenerate
  there and re-copy.
- Columns: `season` (**Utf8**), `team` (stats.ncaa.org name — the join key),
  `torvik_team`, `adjoe`, `adjde`, `barthag`, `adjem` (= adjoe − adjde).
  No null or imputed-zero efficiency rows (verified 2026-08-24).

Consumed by `ops/build_rapm_league.py` gate 3: per-season
Spearman(team_net, adjem) ≥ 0.89 on ≥ 250 joined teams (floors frozen from
the observed 2026-08-24 sweep — min 0.9039 in the 2021 COVID season, all
other seasons ≥ 0.9723; never lowered). Seasons 2011–2020 publish via the
explicit `UNGATED_SEASONS` allowlist (no oracle exists), internal gates only.
