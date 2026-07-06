#!/bin/bash
#PBS -N data_health
#PBS -q casper
#PBS -l select=1:ncpus=2:mem=16GB
#PBS -l walltime=01:00:00
#PBS -A ncgd0011
#PBS -j oe
#PBS -o /glade/u/home/manishrv/documents/croc/dev/SeaSloth/pbs_data_health.log
#
# Daily data-access health check on Derecho/Casper.
#
# Run once to start the daily chain:
#   qsub scripts/pbs_data_health.sh
#
# Each run performs the full check (link checks + validate_function via
# CrocoDash), overwrites results/health.json (a snapshot, not a history),
# and self-resubmits for the same time tomorrow. Results are committed and
# pushed so that the next GitHub Actions CI run picks them up and rebuilds
# the health page.
#
# Prerequisites:
#   - SSH key configured for github.com (test: ssh -T git@github.com)
#   - Git remote uses SSH URL (git remote -v)

set -euo pipefail

REPO_ROOT="/glade/u/home/manishrv/documents/croc/dev/SeaSloth"
cd "$REPO_ROOT"

echo "=== Data access health check: $(date -u) ==="

conda run -n CrocoDash python scripts/check_data_access.py || FAILED=true

# Commit and push the overwritten snapshot
git config user.email "pbs-bot@ncar.ucar.edu"
git config user.name  "PBS Data Health Bot"
git pull --ff-only
git add results/health.json
git diff --cached --quiet \
    || git commit -m "ci: daily data-access health $(date -u +%Y-%m-%d)"
git push

echo "=== Done: $(date -u) ==="

# Resubmit for the same hour tomorrow
TOMORROW=$(date -u -d '+1 day' +%Y%m%d%H%M 2>/dev/null \
    || python3 -c "
from datetime import datetime, timedelta, timezone
t = datetime.now(timezone.utc) + timedelta(days=1)
print(t.strftime('%Y%m%d%H%M'))
")
qsub -a "$TOMORROW" "$REPO_ROOT/scripts/pbs_data_health.sh"
echo "Resubmitted for $TOMORROW UTC"

if [ "${FAILED:-false}" = "true" ]; then
    echo "WARNING: one or more health checks failed — see log above"
    exit 1
fi
