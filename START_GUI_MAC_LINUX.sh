#!/bin/bash
# Suno Backup — GUI launcher (macOS / Linux)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info >= (3,9))" 2>/dev/null)
        if [ "$VER" = "True" ]; then PYTHON="$cmd"; break; fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.9+ not found."
    exit 1
fi

"$PYTHON" setup_and_run.py --gui "$@"
