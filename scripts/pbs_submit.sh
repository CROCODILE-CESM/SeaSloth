#!/usr/bin/env bash
#PBS -N seasloth_bench
#PBS -l select=1:ncpus=8:mem=64GB
#PBS -l walltime=04:00:00
#PBS -q casper
#PBS -A NCGD0011
#PBS -j oe
#PBS -o /glade/u/home/manishrv/documents/croc/dev/SeaSloth/pbs_bench.log
#
# pbs_submit.sh — PBS job for slow/HPC benchmarks on Casper.
# Runs suites that require GEBCO or GLORYS data.
# Submit with: qsub scripts/pbs_submit.sh
#
# Prerequisites: run `bash scripts/configure.sh` once to set up asv.conf.json.

set -euo pipefail
module load conda
conda activate CrocoDash

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== SeaSloth HPC benchmarks: $(date) ==="
echo "Node: $(hostname)"

# HEAD resolves against CrocoDash (asv.conf.json "repo" points there after configure.sh)
CROCO_HASH=$(python -c "
import CrocoDash, os, subprocess, pathlib
croco_dir = os.path.dirname(os.path.dirname(os.path.abspath(CrocoDash.__file__)))
print(subprocess.check_output(['git', '-C', croco_dir, 'rev-parse', 'HEAD']).decode().strip())
")
echo "CrocoDash commit: $CROCO_HASH"

python -m asv run --set-commit-hash HEAD

echo ""
echo "=== Committing results: $(date) ==="
git add results/
git commit -m "bench: CrocoDash ${CROCO_HASH:0:8} on $(hostname)" || echo "Nothing new to commit"

echo ""
echo "=== Done: $(date) ==="
echo "Push results and run 'bash scripts/publish.sh' from login node to rebuild dashboard."
echo "  git push && bash scripts/publish.sh"
