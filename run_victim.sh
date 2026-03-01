#!/usr/bin/env bash
# ============================================================
# LayerZero Botnet — Victim Launcher
# Automatically finds Python and runs victim.py.
# Usage: ./run_victim.sh [victim.py flags...]
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$SCRIPT_DIR/botnet"

# --- Find any working Python 3 ---
PYTHON=""
for candidate in python3 python /opt/anaconda3/bin/python3 /opt/homebrew/bin/python3 \
                 "$HOME/anaconda3/bin/python3" "$HOME/miniconda3/bin/python3" \
                 "$HOME/.pyenv/shims/python3"; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import sys; assert sys.version_info >= (3,8)" 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "  [!] Python 3.8+ not found."
    echo "  [!] Install Python from https://python.org or via your package manager."
    echo ""
    exit 1
fi

PYVER=$("$PYTHON" --version 2>&1)
echo "[+] Using Python: $PYTHON ($PYVER)"
echo "[+] Starting victim..."
echo ""
cd "$BOT_DIR" || exit 1
exec "$PYTHON" victim.py "$@"
