#!/usr/bin/env bash
# Launch the Movement Optimizer GUI.
# Usage: ./launch-movement-optimizer.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prefer python3, fall back to python
PYTHON="${PYTHON:-$(command -v python3 2>/dev/null || command -v python 2>/dev/null)}"

if [ -z "$PYTHON" ]; then
    echo "Error: Python not found. Install Python 3.10+ and try again." >&2
    exit 1
fi

echo "Starting Movement Optimizer..."
exec "$PYTHON" -m movement_optimizer "$@"
