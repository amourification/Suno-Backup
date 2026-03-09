#!/bin/bash
# Suno Backup Tool — macOS / Linux launcher
# Double-click in Finder (macOS) or run: bash START_MAC_LINUX.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " ╔══════════════════════════════════════╗"
echo " ║       Suno Library Backup Tool       ║"
echo " ╚══════════════════════════════════════╝"
echo ""

# Find Python 3.9+
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info >= (3,9))" 2>/dev/null)
        if [ "$VER" = "True" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo " ERROR: Python 3.9+ not found."
    echo " Install via:"
    echo "   macOS:  brew install python  OR  https://python.org"
    echo "   Ubuntu: sudo apt install python3"
    echo ""
    read -p " Press Enter to exit..."
    exit 1
fi

echo " Using: $($PYTHON --version)"
echo ""
"$PYTHON" setup_and_run.py "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo " Process exited with code $EXIT_CODE"
    read -p " Press Enter to close..."
fi
