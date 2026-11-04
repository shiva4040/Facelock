#!/usr/bin/env bash
# ===================================================================
# FaceLock Linux Launcher
# ===================================================================
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -f ".env/bin/python" ]; then
    exec ".env/bin/python" main.py "$@"
elif command -v python3 >/dev/null 2>&1; then
    exec python3 main.py "$@"
else
    echo "[ERROR] Python 3 was not found. Please run ./install.sh first."
    exit 1
fi

