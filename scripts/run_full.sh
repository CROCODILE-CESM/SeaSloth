#!/usr/bin/env bash
# run_full.sh — Run all non-HPC benchmarks (full timing, not --quick).
# Use on Casper interactive nodes where xesmf + mom6_forge data is available.
# Slow benchmarks requiring GLORYS/GEBCO are excluded here — use pbs_submit.sh.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_CROCODASH="/glade/work/manishrv/conda-envs/CrocoDash/bin/python"
PYTHON_MOM6FORGE="/glade/work/manishrv/conda-envs/mom6_forge/bin/python"

echo "=== CrocoScope: full fast+medium benchmarks ==="

echo ""
echo "--- xesmf (CrocoDash env) ---"
"$PYTHON_CROCODASH" -m asv run \
    --python "$PYTHON_CROCODASH" \
    --bench "xesmf"

echo ""
echo "--- mom6_forge fast suites (mom6_forge env) ---"
"$PYTHON_MOM6FORGE" -m asv run \
    --python "$PYTHON_MOM6FORGE" \
    --bench "bench_grid_kdtree|bench_grid_metrics|bench_regrid_subsampling"

echo ""
echo "Done. Run 'bash scripts/publish.sh' to build the dashboard."
