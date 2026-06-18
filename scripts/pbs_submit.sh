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

REPO_ROOT="${PBS_O_WORKDIR:-/glade/u/home/manishrv/documents/croc/dev/SeaSloth}"
cd "$REPO_ROOT"

echo "=== SeaSloth HPC benchmarks: $(date) ==="
echo "Node: $(hostname)"

bash scripts/run_bench.sh

echo ""
echo "=== Done: $(date) ==="
echo "Commit results and rebuild dashboard from login node:"
echo "  git add results/ && git commit -m 'bench: <description>' && git push"
echo "  bash scripts/publish.sh"
