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
# Runs the medium and slow suites that require GEBCO or GLORYS data.
# Submit with: qsub scripts/pbs_submit.sh
#
# Adjust -A (project code) and walltime as needed.

set -euo pipefail

REPO_ROOT="/glade/u/home/manishrv/documents/croc/dev/CrocoScope"
cd "$REPO_ROOT"

PYTHON_CROCODASH="/glade/work/manishrv/conda-envs/CrocoDash/bin/python"
PYTHON_MOM6FORGE="/glade/work/manishrv/conda-envs/mom6_forge/bin/python"

echo "=== CrocoScope HPC benchmarks: $(date) ==="
echo "Node: $(hostname)"

echo ""
echo "--- mom6_forge topo + tidy (mom6_forge env) ---"
"$PYTHON_MOM6FORGE" -m asv run \
    --python "$PYTHON_MOM6FORGE" \
    --bench "bench_topo_regrid|bench_topo_tidy"

echo ""
echo "--- CrocoDash OBC pipeline (CrocoDash env) ---"
"$PYTHON_CROCODASH" -m asv run \
    --python "$PYTHON_CROCODASH" \
    --bench "crocodash"

echo ""
echo "=== Done: $(date) ==="
echo "Run 'bash scripts/publish.sh' from login node to rebuild dashboard."
