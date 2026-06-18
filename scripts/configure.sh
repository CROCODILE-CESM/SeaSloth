#!/usr/bin/env bash
# configure.sh — One-time setup: writes the CrocoDash repo path into asv.conf.json.
#
# Run once after cloning (with the CrocoDash conda env active), or any time
# you change which CrocoDash install you want to track.
#
# Usage:
#   conda activate CrocoDash
#   bash scripts/configure.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Discover CrocoDash source root from the active editable install
CROCO_DIR=$(python -c "
import CrocoDash, os
print(os.path.dirname(os.path.dirname(os.path.abspath(CrocoDash.__file__))))
")

if [ -z "$CROCO_DIR" ]; then
    echo "ERROR: Could not find CrocoDash. Is the CrocoDash conda env active?"
    exit 1
fi

echo "Discovered CrocoDash at: $CROCO_DIR"

python - <<EOF
import json, pathlib
conf_path = pathlib.Path("$REPO_ROOT/asv.conf.json")
conf = json.loads(conf_path.read_text())
conf["repo"] = "$CROCO_DIR"
conf_path.write_text(json.dumps(conf, indent=4) + "\n")
print(f"Updated asv.conf.json: repo = {conf['repo']!r}")
EOF
