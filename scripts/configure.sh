#!/usr/bin/env bash
# configure.sh — Verify the CrocoDash conda environment is ready for benchmarking.
#
# This script just confirms that pytest-benchmark, CrocoDash, mom6_forge, and
# xesmf are importable in the active environment.
#
# Usage:
#   conda activate CrocoDash
#   bash scripts/configure.sh

set -euo pipefail

echo "Checking environment..."

python - <<'EOF'
import importlib, sys

ok = True
for pkg in ["pytest", "pytest_benchmark", "CrocoDash", "mom6_forge", "xesmf"]:
    try:
        m = importlib.import_module(pkg)
        src = getattr(m, "__file__", "?")
        print(f"  OK  {pkg:20s}  {src}")
    except ImportError as e:
        print(f"  MISSING  {pkg}: {e}", file=sys.stderr)
        ok = False

if not ok:
    print("\nSome packages are missing. Make sure the CrocoDash conda env is active:", file=sys.stderr)
    print("  conda activate CrocoDash", file=sys.stderr)
    sys.exit(1)
else:
    print("\nEnvironment looks good. Run benchmarks with:")
    print("  bash scripts/run_benchmarks.sh")
EOF
