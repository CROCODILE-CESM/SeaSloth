#!/usr/bin/env bash
# configure.sh — Verify the CrocoDash conda environment is ready for benchmarking.
#
# asv.conf.json "repo" points to the public CrocoDash GitHub repo, so no local
# path configuration is needed. This script just confirms that CrocoDash and
# mom6_forge are importable in the active environment.
#
# Usage:
#   conda activate CrocoDash
#   bash scripts/configure.sh

set -euo pipefail

echo "Checking environment..."

python - <<'EOF'
import importlib, sys

ok = True
for pkg in ["CrocoDash", "mom6_forge", "asv"]:
    try:
        m = importlib.import_module(pkg)
        import os
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
    print("  python -m asv run --set-commit-hash HEAD")
EOF
