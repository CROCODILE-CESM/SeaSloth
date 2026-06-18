#!/usr/bin/env bash
# run_bench.sh — Run benchmarks tagged to the CrocoDash commit in the active env.
#
# Usage:
#   conda activate CrocoDash
#   bash scripts/run_bench.sh [extra asv args...]
#
# Examples:
#   bash scripts/run_bench.sh --quick
#   bash scripts/run_bench.sh --bench "CrocoDashImports" --quick
#   bash scripts/run_bench.sh --bench "XESMFWeightsGenerate"

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Discover CrocoDash commit from the active editable install
CROCO_HASH=$(python -c "
import CrocoDash, os, subprocess
croco_dir = os.path.dirname(os.path.dirname(os.path.abspath(CrocoDash.__file__)))
print(subprocess.check_output(['git', '-C', croco_dir, 'rev-parse', 'HEAD']).decode().strip())
")

echo "CrocoDash: $CROCO_HASH"
echo "Running: asv run --set-commit-hash $CROCO_HASH $*"
echo ""

python -m asv run --set-commit-hash "$CROCO_HASH" "$@"
