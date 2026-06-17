#!/usr/bin/env bash
# publish.sh — Build the ASV HTML dashboard from current results.
# Open .asv/html/index.html in a browser or Jupyter file browser to view.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="/glade/work/manishrv/conda-envs/CrocoDash/bin/python"

"$PYTHON" -m asv publish
"$PYTHON" scripts/generate_report.py

echo ""
echo "Benchmark report: $REPO_ROOT/.asv/html/report.html"
echo "ASV dashboard:    $REPO_ROOT/.asv/html/index.html"
echo ""
echo "To preview in a browser:"
echo "  $PYTHON -m asv preview"
echo "  # or open either file directly in the Jupyter file browser"
