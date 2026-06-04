#!/usr/bin/env bash
# run_fast.sh — Run fast CI/local benchmarks (xesmf suite).
# Safe to run on login nodes and in CI — no HPC data required.
# Uses CrocoDash env (has xesmf installed).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="/glade/work/manishrv/conda-envs/CrocoDash/bin/python"

echo "=== CrocoScope: fast benchmarks ==="
echo "Python: $PYTHON"
echo "Suites: xesmf"
echo ""

"$PYTHON" -m asv run \
    --python "$PYTHON" \
    --bench "xesmf" \
    --quick

echo ""
echo "Done. Run 'bash scripts/publish.sh' to build the dashboard."
