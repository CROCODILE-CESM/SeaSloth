#!/usr/bin/env bash
#PBS -N crocoscope_bench
#PBS -l select=1:ncpus=8:mem=64GB
#PBS -l walltime=04:00:00
#PBS -q casper
#PBS -A NCGD0011    # <-- change to your project allocation code
#PBS -j oe
#PBS -o /glade/u/home/manishrv/documents/croc/dev/CrocoScope/pbs_bench.log
#
# pbs_submit.sh — PBS job for slow/HPC benchmarks on Casper.
# Runs suites that require GEBCO or GLORYS data.
# Submit with: qsub scripts/pbs_submit.sh

set -euo pipefail

REPO_ROOT="/glade/u/home/manishrv/documents/croc/dev/CrocoScope"
cd "$REPO_ROOT"

PYTHON="/glade/work/manishrv/conda-envs/CrocoDash/bin/python"

ESMF_MK="$(find "$REPO_ROOT/env" -name "esmf.mk" 2>/dev/null | head -1)"
if [ -n "$ESMF_MK" ]; then
    export ESMFMKFILE="$ESMF_MK"
fi

echo "=== CrocoScope HPC benchmarks: $(date) ==="
echo "Node: $(hostname)"

"$PYTHON" -m asv run HEAD

echo ""
echo "=== Done: $(date) ==="
echo "Run 'bash scripts/publish.sh' from login node to rebuild dashboard."
