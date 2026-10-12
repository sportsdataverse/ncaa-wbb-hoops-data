#!/usr/bin/env bash
# Droplet cron entry: in-season nightly build + publish of the CURRENT NCAA WBB season.
# ncaa-wbb-hoops-raw's 03:30 ET cron captures new games; nothing published them, so the
# ncaa_wbb_* tags sat at the last operator publish. This stays fully OFFLINE (reads the
# sibling raw checkout, never stats.ncaa.org): run_publish.sh builds every dataset and
# uploads it, stage 99 rebuilds the coverage index, then the wbb/ tree is committed.
# A season with no captured games writes nothing (build.py), so it no-ops pre-season.
#
#   bash scripts/cron_publish_current.sh [YYYY]     # END year, default from the date
#   watch: tail -f logs/cron_publish_current_$(date -u +%Y%m%d).log
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export PATH="/root/.local/bin:${PATH}"   # cron PATH lacks uv
M=$((10#$(date +%m))); SEASON=$(date +%Y); [ "$M" -ge 8 ] && SEASON=$((SEASON + 1))
SEASON="${1:-$SEASON}"
echo "=== cron_publish_current wbb ${SEASON} $(date -u +%FT%TZ)"
fail() { echo "::error ::$*"; echo "EXIT=1"; exit 1; }

# Hold the git_pull sweep's lock (it would autostash this run's outputs); git children get
# 9>&- so a daemonized gc / credential cache cannot keep the lock after this exits.
exec 9>/tmp/git_pull_sdv.lock
flock -w 3600 9 || fail "git_pull sweep held its lock for 1h"
branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != main ] || [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  git status --short --untracked-files=no | head -20
  fail "checkout is on '$branch' or has tracked changes; refusing to publish"
fi
git pull -q --ff-only 9>&- || fail "git pull --ff-only failed"

export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
rc=0
SEASON="$SEASON" bash scripts/run_publish.sh 9>&- || rc=1
NCAA_WBB_RAW_ROOT="${NCAA_WBB_RAW_ROOT:-$PWD/../ncaa-wbb-hoops-raw}" \
  uv run --quiet python python/ncaa_wbb_99_schedule_master_creation.py 9>&- \
  || echo "WARN: schedule master rebuild failed"

git add -- wbb
git diff --cached --quiet && { echo "wbb tree unchanged"; echo "EXIT=${rc}"; exit "$rc"; }
git -c user.name="Github Action" -c user.email="action@github.com" \
  commit -q -m "NCAA WBB Data Update (Start: ${SEASON} End: ${SEASON})" 9>&- || fail "commit failed"
for attempt in 1 2 3; do   # rebase --merge: parquet blobs hang the am backend
  git push -q origin HEAD 9>&- && { echo "pushed wbb ${SEASON}"; echo "EXIT=${rc}"; exit "$rc"; }
  git fetch -q origin main 9>&- && git rebase -q --merge origin/main 9>&- \
    || { git rebase --abort 2>/dev/null; fail "cannot rebase onto origin/main"; }
done
fail "push rejected 3 times"
