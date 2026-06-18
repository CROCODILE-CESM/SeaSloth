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

set -euo pipefail
module load conda
conda activate CrocoDash
REPO_ROOT="/glade/u/home/manishrv/documents/croc/dev/SeaSloth"
cd "$REPO_ROOT"


echo "=== SeaSloth HPC benchmarks: $(date) ==="
echo "Node: $(hostname)"

# Discover CrocoDash source root from the active editable install
CROCO_DIR=$(python -c "import CrocoDash, os; print(os.path.dirname(os.path.dirname(os.path.abspath(CrocoDash.__file__))))")
CROCO_HASH=$(git -C "$CROCO_DIR" rev-parse HEAD)
echo "CrocoDash commit: $CROCO_HASH"

python -m asv run --set-commit-hash "$CROCO_HASH"

echo ""
echo "=== Committing results: $(date) ==="
git add results/
git commit -m "bench: CrocoDash ${CROCO_HASH:0:8} on $(hostname)" || echo "Nothing new to commit"

echo ""
echo "=== Done: $(date) ==="
echo "Push results and run 'bash scripts/publish.sh' from login node to rebuild dashboard."
echo "  git push && bash scripts/publish.sh"
