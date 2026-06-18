#!/usr/bin/env bash
# publish.sh — Build the ASV HTML dashboard from current results.
# Open .asv/html/index.html in a browser or Jupyter file browser to view.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

python -m asv publish
python scripts/generate_report.py

echo ""
echo "Dashboard: $REPO_ROOT/.asv/html/index.html"
echo "ASV timeline: $REPO_ROOT/.asv/html/summarylist.html"
echo ""
echo "To preview in a browser:"
echo "  python -m asv preview"
echo "  # or open either file directly in the Jupyter file browser"
