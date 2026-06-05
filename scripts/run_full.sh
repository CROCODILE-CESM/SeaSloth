#!/usr/bin/env bash
# run_full.sh — Run all non-HPC benchmarks (full timing, not --quick).
# Use on Casper interactive nodes. HPC benchmarks requiring GLORYS/GEBCO
# are excluded here — use pbs_submit.sh for those.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="/glade/work/manishrv/conda-envs/CrocoDash/bin/python"

ESMF_MK="$(find "$REPO_ROOT/env" -name "esmf.mk" 2>/dev/null | head -1)"
if [ -n "$ESMF_MK" ]; then
    export ESMFMKFILE="$ESMF_MK"
fi

echo "=== CrocoScope: full fast+medium benchmarks ==="

"$PYTHON" -m asv run HEAD

echo ""
echo "Done. Run 'bash scripts/publish.sh' to build the dashboard."
