#!/usr/bin/env bash
# Build one or all NCAA WBB datasets for a season AND publish (upload) the
# release assets to sportsdataverse/sportsdataverse-data via `gh`.
#
# Usage:
#   SEASON=2025 bash scripts/run_publish.sh
#   SEASON=2025 DATASET=shots bash scripts/run_publish.sh
#
# Watch a running publish live in another terminal:
#   tail -f scripts/../logs/run_publish_<timestamp>.log
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export NCAA_WBB_RAW_ROOT="${NCAA_WBB_RAW_ROOT:-$REPO_ROOT/../ncaa-wbb-hoops-raw}"
[ -n "${NCAA_WBB_CACHE:-}" ] && export NCAA_WBB_CACHE

# Resolve a gh token without ever echoing its value: env first, then
# ~/.Renviron / ~/Documents/.Renviron (read by R at startup, not by bash --
# so we grep them here). Checked in that order: this box uses BOTH files
# (~/.Renviron and ~/Documents/.Renviron), so both are scanned.
GH_TOKEN="${GH_TOKEN:-${GITHUB_PAT:-${SDV_GH_TOKEN:-}}}"
if [ -z "$GH_TOKEN" ]; then
  for renviron in "$HOME/.Renviron" "$HOME/Documents/.Renviron"; do
    [ -f "$renviron" ] || continue
    line="$(grep -E '^(GITHUB_PAT|SDV_GH_TOKEN)=' "$renviron" | head -n1)"
    [ -n "$line" ] || continue
    val="${line#*=}"
    val="${val%$'\r'}"      # strip trailing CR (Windows-edited .Renviron)
    val="${val%\"}"; val="${val#\"}"
    val="${val%\'}"; val="${val#\'}"
    GH_TOKEN="$val"
    break
  done
fi
if [ -z "$GH_TOKEN" ]; then
  echo "run_publish.sh: no gh token found (checked GH_TOKEN, GITHUB_PAT, SDV_GH_TOKEN, ~/.Renviron, ~/Documents/.Renviron)" >&2
  exit 1
fi
export GH_TOKEN

mkdir -p logs
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOGFILE="logs/run_publish_${TIMESTAMP}.log"

# RDS asset staging needs an R install with the `arrow` package (R 4.5.3
# has it; R 4.6.0 does not, as of this writing). Point SDV_RSCRIPT at an
# arrow-capable Rscript.exe if the default resolution order (SDV_RSCRIPT ->
# RSCRIPT -> Rscript on PATH -> C:/Program Files/R/R-*/bin/Rscript.exe scan)
# picks the wrong install. RDS failure only warns -- it never blocks the
# parquet+csv upload.
[ -n "${SDV_RSCRIPT:-}" ] && export SDV_RSCRIPT

uv run python -m ncaa_wbb_data_build build \
  --dataset "${DATASET:-all}" \
  --season "${SEASON:?set SEASON}" \
  --publish \
  2>&1 | tee "$LOGFILE"
