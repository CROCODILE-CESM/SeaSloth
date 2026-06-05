#!/usr/bin/env bash
# run_fast.sh — Run fast CI/local benchmarks (xesmf suite).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="/glade/work/manishrv/conda-envs/CrocoDash/bin/python"

# ASV's conda env doesn't source activation scripts, so ESMFMKFILE is never set
# in benchmark subprocesses. Find it inside the managed env and export it here.
ESMF_MK="$(find "$REPO_ROOT/env" -name "esmf.mk" 2>/dev/null | head -1)"
if [ -n "$ESMF_MK" ]; then
    export ESMFMKFILE="$ESMF_MK"
else
    echo "NOTE: env/ not built yet — first run will take ~5 min to create the conda env."
fi

echo "=== CrocoScope: fast benchmarks ==="
echo "Suites: xesmf"
echo ""

"$PYTHON" -m asv run --bench "xesmf" --quick HEAD

echo ""
echo "Done. Run 'bash scripts/publish.sh' to build the dashboard."
