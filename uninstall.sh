#!/usr/bin/env bash
# ===================================================================
#               FaceLock Linux App Uninstaller
# ===================================================================
set -e

echo "==================================================================="
echo "               FaceLock Linux App Uninstaller"
echo "==================================================================="
echo ""

read -p "Are you sure you want to uninstall FaceLock? [y/N]: " -r response
if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

echo ""
echo "[1/4] Terminating running FaceLock instances..."
pkill -f "main.py" >/dev/null 2>&1 || true

echo ""
echo "[2/4] Removing desktop launcher and icons..."
rm -f "$HOME/.local/bin/facelock"
rm -f "$HOME/.local/share/applications/facelock.desktop"
rm -f "$HOME/Desktop/facelock.desktop"
rm -f "$HOME/.config/autostart/facelock.desktop"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/facelock.png"
rm -f "$HOME/.local/share/pixmaps/facelock.png"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "  Desktop files and icons removed."

echo ""
echo "[3/4] User Data and Configuration:"
read -p "Do you want to delete all saved face data, intruder snapshots, and settings (~/.facelock)? [y/N]: " -r data_resp
if [[ "$data_resp" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    rm -rf "$HOME/.facelock"
    echo "  Face data and settings wiped."
else
    echo "  Keeping face data and settings for future reinstall."
fi

echo ""
echo "[4/4] Python Virtual Environment:"
read -p "Do you want to delete the local virtual environment (.env)? [y/N]: " -r env_resp
if [[ "$env_resp" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    rm -rf "$APP_DIR/.env"
    echo "  Virtual environment removed."
fi

echo ""
echo "==================================================================="
echo "                     UNINSTALLATION COMPLETE"
echo "FaceLock has been removed from your system."
echo "==================================================================="
echo ""
exit 0
