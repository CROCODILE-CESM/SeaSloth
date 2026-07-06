#!/usr/bin/env bash
# run_benchmarks.sh — Run the perf-benchmark suite and write results/latest.json.
#
# Usage:
#   conda activate CrocoDash
#   bash scripts/run_benchmarks.sh              # everything
#   bash scripts/run_benchmarks.sh -k xesmf      # just one suite
#
# Extra arguments are passed straight through to pytest.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p results
pytest benchmarks/ --benchmark-json=results/latest.json -v "$@"
