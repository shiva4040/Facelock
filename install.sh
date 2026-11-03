#!/usr/bin/env bash
# ===================================================================
#               FaceLock Linux App Installer v1.0
#       macOS-styled facial recognition security for your laptop
# ===================================================================
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "==================================================================="
echo "               FaceLock Linux App Installer"
echo "==================================================================="
echo ""

# 1. Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 is not installed on your system."
    echo "Please install Python 3.10+ using your package manager:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install -y python3 python3-pip python3-venv"
    echo "  Fedora:        sudo dnf install -y python3 python3-pip"
    echo "  Arch Linux:    sudo pacman -S python python-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[1/6] Detected Python $PYTHON_VERSION"

# Check camera group permissions
if [ -e /dev/video0 ]; then
    if ! groups | grep -q "video"; then
        echo "[INFO] Note: If your camera is inaccessible, add your user to the video group:"
        echo "       sudo usermod -a -G video \$USER (then log out and log back in)"
    fi
fi

# 2. Setup Virtual Environment
echo ""
echo "[2/6] Setting up isolated Python virtual environment (.env)..."
if [ ! -f "$APP_DIR/.env/bin/python" ]; then
    if ! python3 -m venv "$APP_DIR/.env" >/dev/null 2>&1; then
        echo "[ERROR] Failed to create virtual environment."
        echo "You may need to install the python3-venv package:"
        echo "  Ubuntu/Debian: sudo apt install -y python3-venv"
        exit 1
    fi
    echo "  Created virtual environment in $APP_DIR/.env"
else
    echo "  Existing virtual environment found."
fi

VENV_PY="$APP_DIR/.env/bin/python"

# 3. Install Dependencies
echo ""
echo "[3/6] Installing dependencies (PySide6, OpenCV, Cryptography)..."
"$VENV_PY" -m pip install --upgrade pip >/dev/null 2>&1 || true
"$VENV_PY" -m pip install -r "$APP_DIR/requirements.txt"
"$VENV_PY" -m pip install -e "$APP_DIR" >/dev/null 2>&1 || true

# 4. Pre-download AI Models
echo ""
echo "[4/6] Verifying on-device neural network models (YuNet + SFace)..."
"$VENV_PY" -c "
from core.detector import check_and_download_models
d, r = check_and_download_models()
print('  Models verified at:\n  - ' + d + '\n  - ' + r)
" || echo "[WARNING] Model pre-download skipped; models will download on first launch."

# 5. Install Binary Launcher to ~/.local/bin
echo ""
echo "[5/6] Installing launcher executable to ~/.local/bin/facelock..."
mkdir -p "$HOME/.local/bin"

cat << EOF > "$HOME/.local/bin/facelock"
#!/usr/bin/env bash
# FaceLock Application Launcher
APP_DIR="$APP_DIR"
exec "\$APP_DIR/.env/bin/python" "\$APP_DIR/main.py" "\$@"
EOF

chmod +x "$HOME/.local/bin/facelock"
echo "  Installed ~/.local/bin/facelock"

# Ensure ~/.local/bin is in PATH if not already
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "  [NOTE] Make sure ~/.local/bin is in your PATH (e.g. export PATH=\"\$HOME/.local/bin:\$PATH\" in ~/.bashrc)"
fi

# 6. Install Desktop Entry and Icons (XDG Standard)
echo ""
echo "[6/6] Integrating with Linux Desktop (GNOME / KDE / XFCE)..."

# Icons
mkdir -p "$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$HOME/.local/share/pixmaps"
cp "$APP_DIR/assets/icon.png" "$HOME/.local/share/icons/hicolor/256x256/apps/facelock.png"
cp "$APP_DIR/assets/icon.png" "$HOME/.local/share/pixmaps/facelock.png"
echo "  Installed application icons."

# Desktop file
mkdir -p "$HOME/.local/share/applications"
cat << EOF > "$HOME/.local/share/applications/facelock.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=FaceLock
GenericName=Face Recognition Lock
Comment=macOS-styled facial recognition security system for laptops
Exec=$HOME/.local/bin/facelock
Icon=facelock
Terminal=false
Categories=Utility;Security;System;
Keywords=facelock;face;recognition;lock;security;webcam;biometrics;
StartupNotify=true
StartupWMClass=FaceLock
EOF

chmod +x "$HOME/.local/share/applications/facelock.desktop"
echo "  Created ~/.local/share/applications/facelock.desktop"

# Optional Desktop shortcut if ~/Desktop exists
if [ -d "$HOME/Desktop" ]; then
    cp "$HOME/.local/share/applications/facelock.desktop" "$HOME/Desktop/facelock.desktop"
    chmod +x "$HOME/Desktop/facelock.desktop"
    if command -v gio >/dev/null 2>&1; then
        gio set "$HOME/Desktop/facelock.desktop" metadata::trusted true >/dev/null 2>&1 || true
    fi
    echo "  Created ~/Desktop/facelock.desktop"
fi

# Update desktop and icon databases
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo ""
echo "==================================================================="
echo "                     INSTALLATION COMPLETE!"
echo ""
echo "FaceLock is now installed on your Linux system."
echo "You can launch it anytime by:"
echo "  1. Selecting 'FaceLock' from your Application Menu (Super / App launcher)"
echo "  2. Typing in terminal: facelock"
echo "  3. Running: $APP_DIR/run.sh"
echo "==================================================================="
echo ""

read -p "Would you like to launch FaceLock now? [y/N]: " -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Launching FaceLock..."
    "$HOME/.local/bin/facelock" >/dev/null 2>&1 &
fi

exit 0
