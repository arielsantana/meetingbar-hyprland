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
echo "2. Add to ~/.config/waybar/config:"
echo "   (copy from: $INSTALL_DIR/themes/waybar-module.json)"
echo "   Update the exec path to: python3 $INSTALL_DIR/waybar.py"
echo ""
echo "3. Add to ~/.config/waybar/style.css:"
echo "   (copy from: $INSTALL_DIR/themes/waybar.css)"
echo ""
echo "4. Reload Waybar:  killall -SIGUSR2 waybar"
echo "   Reload Hyprland config:  hyprctl reload"
echo ""
