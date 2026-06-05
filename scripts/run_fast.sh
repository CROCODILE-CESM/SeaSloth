#!/usr/bin/env bash
# run_fast.sh — Run fast CI/local benchmarks (mom6_forge grid/kdtree suites).
# xesmf benchmarks are slow (ESMF weight generation); run them via run_full.sh.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="/glade/work/manishrv/conda-envs/CrocoDash/bin/python"

ESMF_MK="$(find "$REPO_ROOT/env" -name "esmf.mk" 2>/dev/null | head -1)"
if [ -n "$ESMF_MK" ]; then
    export ESMFMKFILE="$ESMF_MK"
else
    echo "NOTE: env/ not built yet — first run will take ~5 min to create the conda env."
fi

echo "=== CrocoScope: fast benchmarks ==="
echo "Suites: mom6_forge.bench_grid_kdtree, mom6_forge.bench_grid_metrics, mom6_forge.bench_topo_tidy, mom6_forge.bench_regrid_subsampling"
echo ""

"$PYTHON" -m asv run --bench "bench_grid_kdtree|bench_grid_metrics|bench_topo_tidy|bench_regrid_subsampling" --quick HEAD

echo ""
echo "Done. Run 'bash scripts/publish.sh' to build the dashboard."
