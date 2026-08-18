#!/usr/bin/env bash
# Historical backfill: build + publish EVERY season of EVERY ncaa_wbb_* dataset.
#
# One-time (or re-runnable) driver behind the first full publish. Ordinary
# incremental work is `run_build.sh` / `run_publish.sh` for a single season --
# reach for this only when re-materialising the whole history.
#
#   bash scripts/run_historical_publish.sh                 # 2010..2026, all datasets
#   START=2015 END=2010 bash scripts/run_historical_publish.sh
#   DATASETS="pbp shots" bash scripts/run_historical_publish.sh
#   DRY_RUN=1 bash scripts/run_historical_publish.sh        # build + stage, no uploads
#
# Watch it live in another terminal:
#   tail -f logs/historical_publish_<timestamp>.log
#
# RESUMABLE, AND THE RESUME PROVES A PUBLISH. A (dataset, season) is skipped
# only when the RELEASE actually holds its parquet + csv assets -- never on the
# strength of a local file or a manifest row.
#
#   WHY THIS IS NOT THE MBB VERSION'S CHECK: `io.write_dataset` upserts the
#   manifest row BEFORE `publish_dataset` uploads anything (build.py: write at
#   line ~100, publish at ~106). So a unit whose upload failed -- a 403 from a
#   burned API quota, a network drop -- still leaves a current-looking parquet
#   AND a manifest row behind. The MBB driver's `[ -s "$pq" ] && manifest-has-row`
#   test then skips it on every subsequent run, forever, reporting it as
#   "skipped" rather than missing. Ask the release what it has instead.
#
# The published index costs ONE `gh` call per TAG (11), not one per unit (187):
# the 2026-08-12 MBB publish burned its GitHub API quota on per-unit polling and
# earned a 403 partway through the sweep.
#
# Knobs are env-only, so pace/scope can be retuned without editing this file.
set -uo pipefail          # NOT -e: one bad season must not kill the sweep

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

START="${START:-2026}"          # newest season (ending year)
END="${END:-2010}"              # oldest
DATASETS="${DATASETS:-}"        # empty = every dataset in config.REGISTRY order
FORCE="${FORCE:-0}"             # 1 = rebuild+reupload even when already published
DRY_RUN="${DRY_RUN:-0}"         # 1 = no gh uploads (still builds + stages)

export PYTHONUNBUFFERED=1       # real-time log lines, no 4KB buffering lag
export PYTHONIOENCODING=utf-8   # cp1252 chokes on unicode in piped output
export NCAA_WBB_RAW_ROOT="${NCAA_WBB_RAW_ROOT:-$REPO_ROOT/../ncaa-wbb-hoops-raw}"

# Use this repo's own venv -- never `uv run` in a long sweep (it can re-sync
# mid-run), and never a sibling repo's interpreter.
PY="${PY:-$REPO_ROOT/.venv/Scripts/python.exe}"
[ -x "$PY" ] || PY="$REPO_ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv interpreter at $REPO_ROOT/.venv -- run 'uv sync --frozen'" >&2; exit 1; }

# rds needs an R install that HAS arrow. PATH's Rscript often is not one:
# on this box PATH resolves to R-4.5.3 (no arrow) while 4.6.1 has it, and the
# only symptom is a warning + a silently missing .rds asset. Pick explicitly.
if [ -z "${SDV_RSCRIPT:-}" ]; then
  for r in "C:/Program Files/R/R-4.6.1/bin/Rscript.exe" \
           "C:/Program Files/R/R-4.6.0/bin/Rscript.exe" \
           "C:/Program Files/R/R-4.3.1/bin/Rscript.exe"; do
    [ -f "$r" ] || continue
    if "$r" -e 'quit(status = !requireNamespace("arrow", quietly = TRUE))' 2>/dev/null; then
      export SDV_RSCRIPT="$r"; break
    fi
  done
fi
[ -n "${SDV_RSCRIPT:-}" ] \
  && echo "rds: using ${SDV_RSCRIPT}" \
  || echo "rds: WARNING no R install with arrow found -- .rds assets will be SKIPPED"

if [ "$DRY_RUN" != "1" ]; then
  GH_TOKEN="${GH_TOKEN:-${GITHUB_PAT:-${SDV_GH_TOKEN:-}}}"
  if [ -z "$GH_TOKEN" ]; then
    for renviron in "$HOME/.Renviron" "$HOME/Documents/.Renviron"; do
      [ -f "$renviron" ] || continue
      line="$(grep -E '^(GITHUB_PAT|SDV_GH_TOKEN)=' "$renviron" | head -n1)" || true
      [ -n "$line" ] || continue
      val="${line#*=}"; val="${val%$'\r'}"
      val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
      GH_TOKEN="$val"; break
    done
  fi
  [ -z "$GH_TOKEN" ] && { echo "no gh token (GH_TOKEN/GITHUB_PAT/SDV_GH_TOKEN/.Renviron)" >&2; exit 1; }
  export GH_TOKEN
fi

mkdir -p logs
TS="$(date +%Y%m%d_%H%M%S)"
LOG="logs/historical_publish_${TS}.log"
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

[ -z "$DATASETS" ] && DATASETS="$("$PY" -c 'from ncaa_wbb_data_build.config import REGISTRY; print(" ".join(REGISTRY))')"
MODE_FLAG="--publish"; [ "$DRY_RUN" = "1" ] && MODE_FLAG="--dry-run"

say "historical publish: seasons ${START}..${END}, mode=${MODE_FLAG}, force=${FORCE}"
say "datasets: ${DATASETS}"
say "raw root: ${NCAA_WBB_RAW_ROOT}"

# --- resume index: what the RELEASES actually hold, one gh call per tag ------
INDEX="$(mktemp)"
trap 'rm -f "$INDEX"' EXIT
if [ "$FORCE" = "1" ] || [ "$DRY_RUN" = "1" ]; then
  : > "$INDEX"        # force/dry-run: treat everything as unpublished
  say "resume: disabled (force=${FORCE} dry_run=${DRY_RUN}) -- every unit will run"
else
  "$PY" -m ncaa_wbb_data_build check --porcelain > "$INDEX" 2>>"$LOG"
  idx_rc=$?
  # rc 2 = "gh could not answer" (GhUnavailable), distinct from rc 1 = "there
  # are gaps". Only rc 2 is fatal here: gaps are exactly what this sweep fills,
  # but an unreadable index must NOT degrade into "nothing is published" --
  # that would re-upload the entire history while reporting a clean run.
  if [ "$idx_rc" -eq 2 ]; then
    say "resume: gh could not report published state -- aborting (re-run when gh works)"
    exit 1
  fi
  say "resume: $(wc -l < "$INDEX" | tr -d ' ') unit(s) already published -- they will be skipped"
fi

ok=0; skip=0; fail=0; failed_list=""
sweep_start=$SECONDS

for (( season=START; season>=END; season-- )); do
  season_start=$SECONDS
  for ds in $DATASETS; do
    if grep -qx "${ds} ${season}" "$INDEX" 2>/dev/null; then
      skip=$((skip+1)); continue
    fi
    t0=$SECONDS
    if "$PY" -m ncaa_wbb_data_build build \
         --dataset "$ds" --season "$season" $MODE_FLAG >>"$LOG" 2>&1; then
      say "  OK   ${ds} ${season}  ($((SECONDS-t0))s)"
      ok=$((ok+1))
    else
      say "  FAIL ${ds} ${season}  ($((SECONDS-t0))s) -- see ${LOG}"
      fail=$((fail+1)); failed_list="${failed_list} ${ds}/${season}"
    fi
  done
  say "season ${season} done in $((SECONDS-season_start))s (ok=${ok} skip=${skip} fail=${fail})"
done

say "SWEEP COMPLETE in $((SECONDS-sweep_start))s -- ok=${ok} skipped=${skip} failed=${fail}"
[ -n "$failed_list" ] && say "failed:${failed_list}"

# Final audit: the sweep's own counters describe what it TRIED, so verify what
# the releases actually hold. Compares SETS, not counts.
if [ "$DRY_RUN" != "1" ]; then
  say "--- final audit (built vs published) ---"
  "$PY" -m ncaa_wbb_data_build check 2>&1 | tee -a "$LOG"
  audit=${PIPESTATUS[0]}
  [ "$audit" -ne 0 ] && say "AUDIT FOUND GAPS -- re-run this script to fill them"
  [ "$audit" -ne 0 ] && fail=$((fail+1))
fi

# Exit RED if anything failed, but only AFTER every other unit had its turn --
# one bad dataset-season must not hide the 180 that worked.
echo "EXIT=$([ "$fail" -eq 0 ] && echo 0 || echo 1)" | tee -a "$LOG"
exit "$([ "$fail" -eq 0 ] && echo 0 || echo 1)"
