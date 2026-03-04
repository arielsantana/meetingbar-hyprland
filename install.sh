#!/usr/bin/env bash
# install.sh — MeetingBar installer
# Detects install location, creates venv, generates systemd service, enables it.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="meetingbar.service"
SERVICE_PATH="$SERVICE_DIR/$SERVICE_NAME"

echo "========================================"
echo "  MeetingBar installer"
echo "========================================"
echo "Install directory: $INSTALL_DIR"
echo ""

# --- Dependency pre-check --------------------------------------------------
# We check for required tools and warn about optional ones.
# We don't install anything — each distro uses a different package manager.

echo "[0/4] Checking dependencies..."

_missing=0

_check_required() {
    local cmd="$1" pkg_arch="$2" pkg_fedora="$3" pkg_ubuntu="$4"
    if ! command -v "$cmd" &>/dev/null; then
        echo "  MISSING (required): $cmd"
        echo "    Arch:    sudo pacman -S $pkg_arch"
        echo "    Fedora:  sudo dnf install $pkg_fedora"
        echo "    Ubuntu:  sudo apt install $pkg_ubuntu"
        _missing=1
    fi
}

# systemctl --user: required for service management
if ! systemctl --user status &>/dev/null && ! systemctl --user list-units &>/dev/null 2>&1; then
    echo "  MISSING (required): systemd user session"
    echo "    This project requires systemd. Void, Alpine, Artix, etc. are not supported."
    _missing=1
fi

_check_required python3        python          python3              python3
_check_required notify-send    libnotify       libnotify            libnotify-bin
_check_required xdg-open       xdg-utils       xdg-utils            xdg-utils

# python-gobject: check via python import (it's a system package, not pip)
if ! python3 -c "import gi" 2>/dev/null; then
    echo "  MISSING (required): python-gobject (gi module)"
    echo "    Arch:    sudo pacman -S python-gobject"
    echo "    Fedora:  sudo dnf install python3-gobject"
    echo "    Ubuntu:  sudo apt install python3-gi"
    _missing=1
fi

# GNOME Online Accounts DBus service
if ! python3 -c "import gi; gi.require_version('Goa', '1.0'); from gi.repository import Goa; Goa.Client.new_sync(None)" 2>/dev/null; then
    echo "  MISSING (required): gnome-online-accounts"
    echo "    Arch:    sudo pacman -S gnome-online-accounts"
    echo "    Fedora:  sudo dnf install gnome-online-accounts"
    echo "    Ubuntu:  sudo apt install gnome-online-accounts"
    _missing=1
fi

# Sound: at least one of pw-play / paplay / aplay (optional — no sound if missing)
_sound_found=false
for _cmd in pw-play paplay aplay; do
    if command -v "$_cmd" &>/dev/null; then
        _sound_found=true
        break
    fi
done
if ! $_sound_found; then
    echo "  WARNING (optional): no sound player found (pw-play / paplay / aplay)"
    echo "    Meeting sounds will be disabled. To enable:"
    echo "    PipeWire — Arch: sudo pacman -S pipewire  |  Fedora: sudo dnf install pipewire-utils  |  Ubuntu: sudo apt install pipewire"
    echo "    PulseAudio — Arch: sudo pacman -S libpulse  |  Ubuntu: sudo apt install pulseaudio-utils"
fi

# gtk4-layer-shell: optional — overlay falls back to Hyprland window rules
if ! python3 -c "import gi; gi.require_version('Gtk4LayerShell', '1.0'); from gi.repository import Gtk4LayerShell" 2>/dev/null; then
    echo "  WARNING (optional): gtk4-layer-shell not found"
    echo "    Fullscreen overlay will rely on Hyprland window rules instead."
    echo "    To install: Arch: sudo pacman -S gtk4-layer-shell"
fi

if [ "$_missing" -eq 1 ]; then
    echo ""
    echo "ERROR: Install missing required dependencies above, then re-run install.sh."
    exit 1
fi
echo "      OK."
echo ""

# 1. Create virtual environment
echo "[1/4] Creating virtual environment..."
python3 -m venv --system-site-packages "$INSTALL_DIR/.venv"
echo "      Done: $INSTALL_DIR/.venv"

# 2. Install Python dependencies
echo "[2/4] Installing Python dependencies..."
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
echo "      Done."

# 3. Generate systemd service from template
echo "[3/4] Generating systemd service..."
mkdir -p "$SERVICE_DIR"
sed "s|{INSTALL_DIR}|$INSTALL_DIR|g" "$INSTALL_DIR/meetingbar.service.template" > "$SERVICE_PATH"
echo "      Written: $SERVICE_PATH"

# 4. Enable and start the service
echo "[4/4] Enabling and starting meetingbar service..."
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"
echo "      Done."

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
echo "Check service status:"
echo "  systemctl --user status meetingbar"
echo "  journalctl --user -u meetingbar -f"
echo ""
echo "--------------------------------------"
echo "  Next steps (manual config)"
echo "--------------------------------------"
echo ""
echo "1. Add to ~/.config/hypr/hyprland.conf:"
echo "   (copy from: $INSTALL_DIR/themes/hyprland-rules.conf)"
echo ""
echo "2. Add to ~/.config/waybar/config — paste this block:"
echo ""
sed "s|{INSTALL_DIR}|$INSTALL_DIR|g" "$INSTALL_DIR/themes/waybar-module.json"
echo ""
echo "   Also add \"custom/meetingbar\" to your modules-left/center/right array."
echo "   For the on-click handler also add:"
echo "   \"on-click\": \"python3 $INSTALL_DIR/click.py\""
echo ""
echo "3. Add to ~/.config/waybar/style.css:"
echo "   (copy from: $INSTALL_DIR/themes/waybar.css)"
echo ""
echo "4. Reload Waybar:  killall -SIGUSR2 waybar"
echo "   Reload Hyprland config:  hyprctl reload"
echo ""
