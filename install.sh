#!/usr/bin/env bash
# install.sh — MeetingBar installer
# Detects install location and init system, creates venv, generates the
# matching service unit, enables it.
#
# Supported init systems: systemd (user session) and dinit (user mode).
# Neither one is required: with --init=none the daemon is launched straight
# from hyprland.conf and no service manager is involved.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SYSTEMD_DIR="$HOME/.config/systemd/user"
SYSTEMD_UNIT="meetingbar.service"

DINIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/dinit.d"
DINIT_UNIT="meetingbar"
LOG_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/meetingbar/daemon.log"
ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/meetingbar/env"

INIT_SYSTEM=""

usage() {
    cat <<'EOF'
Usage: ./install.sh [--init=systemd|dinit|none]

  --init=systemd   Generate a systemd user unit (default where systemd runs)
  --init=dinit     Generate a dinit user service
  --init=none      No service manager; print the hyprland exec-once line
  -h, --help       This message

With no flag the init system is detected, and you are asked if it is ambiguous.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --init=systemd|--init=dinit|--init=none) INIT_SYSTEM="${arg#--init=}" ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $arg"; usage; exit 1 ;;
    esac
done

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

# --- Init system detection -------------------------------------------------
# A service manager is optional. We probe for one that can actually manage
# services right now, not merely for an installed binary: on both systemd and
# dinit the user instance has to be running for enable/start to do anything.

has_systemd() {
    systemctl --user list-units &>/dev/null || systemctl --user status &>/dev/null
}

has_dinit() {
    command -v dinitctl &>/dev/null && dinitctl list &>/dev/null
}

detect_init() {
    local found=()
    has_systemd && found+=("systemd")
    has_dinit  && found+=("dinit")

    case "${#found[@]}" in
        1)
            INIT_SYSTEM="${found[0]}"
            echo "      Detected: $INIT_SYSTEM"
            ;;
        0)
            if command -v dinitctl &>/dev/null; then
                echo "      dinitctl found, but no user dinit instance is reachable."
                echo "      Start one (e.g. 'dinit --user') and re-run, or continue without a"
                echo "      service manager."
            else
                echo "      No usable service manager found."
            fi
            ask_init "none"
            ;;
        *)
            echo "      Both systemd and dinit are available."
            ask_init "systemd"
            ;;
    esac
}

ask_init() {
    local default="$1" reply
    if [ ! -t 0 ]; then
        INIT_SYSTEM="$default"
        echo "      Not a terminal; defaulting to --init=$default"
        return
    fi
    echo ""
    echo "      Which should MeetingBar use?"
    echo "        1) systemd   user unit"
        echo "        2) dinit     user service"
    echo "        3) none      launch from hyprland.conf, no service manager"
    read -r -p "      Choice [default: $default]: " reply
    case "$reply" in
        1|systemd) INIT_SYSTEM="systemd" ;;
        2|dinit)   INIT_SYSTEM="dinit" ;;
        3|none)    INIT_SYSTEM="none" ;;
        "")        INIT_SYSTEM="$default" ;;
        *)         echo "      Unrecognised, using $default"; INIT_SYSTEM="$default" ;;
    esac
}

echo "[0b/4] Init system..."
if [ -n "$INIT_SYSTEM" ]; then
    echo "      Forced by --init=$INIT_SYSTEM"
else
    detect_init
fi

# Guard against being told to use something that is not actually there.
case "$INIT_SYSTEM" in
    systemd) has_systemd || { echo "ERROR: --init=systemd but no systemd user session."; exit 1; } ;;
    dinit)   command -v dinitctl &>/dev/null || { echo "ERROR: --init=dinit but dinitctl is not installed."; exit 1; } ;;
esac
echo ""

# 1. Create virtual environment
echo "[1/4] Creating virtual environment..."
python3 -m venv --system-site-packages "$INSTALL_DIR/.venv"
echo "      Done: $INSTALL_DIR/.venv"

# 2. Install Python dependencies
echo "[2/4] Installing Python dependencies..."
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
echo "      Done."

# 3. Generate the service description for the chosen init system
echo "[3/4] Generating service description..."
case "$INIT_SYSTEM" in
    systemd)
        mkdir -p "$SYSTEMD_DIR"
        sed "s|{INSTALL_DIR}|$INSTALL_DIR|g" \
            "$INSTALL_DIR/meetingbar.service.template" > "$SYSTEMD_DIR/$SYSTEMD_UNIT"
        echo "      Written: $SYSTEMD_DIR/$SYSTEMD_UNIT"
        ;;
    dinit)
        mkdir -p "$DINIT_DIR" "$(dirname "$LOG_FILE")"
        sed -e "s|{INSTALL_DIR}|$INSTALL_DIR|g" \
            -e "s|{LOG_FILE}|$LOG_FILE|g" \
            -e "s|{ENV_FILE}|$ENV_FILE|g" \
            "$INSTALL_DIR/meetingbar.dinit.template" > "$DINIT_DIR/$DINIT_UNIT"
        echo "      Written: $DINIT_DIR/$DINIT_UNIT"
        echo "      Log file: $LOG_FILE"
        if command -v dinit-check &>/dev/null; then
            if dinit-check -d "$DINIT_DIR" "$DINIT_UNIT"; then
                echo "      dinit-check: OK"
            else
                echo "      WARNING: dinit-check reported problems (see above)."
            fi
        else
            echo "      (dinit-check not installed — service file not validated)"
        fi
        ;;
    none)
        echo "      Skipped: no service manager selected."
        ;;
esac

# 4. Enable and start
echo "[4/4] Enabling and starting..."
case "$INIT_SYSTEM" in
    systemd)
        systemctl --user daemon-reload
        systemctl --user enable "$SYSTEMD_UNIT"
        systemctl --user restart "$SYSTEMD_UNIT"
        echo "      Done."
        ;;
    dinit)
        # 'reload' picks up a changed description; on a first install the
        # service is not loaded yet and it fails, which is expected.
        dinitctl reload "$DINIT_UNIT" &>/dev/null || true
        # 'enable' adds a persistent waits-for dependency from the boot service.
        dinitctl enable "$DINIT_UNIT"
        # 'restart' errors if the service was never started; fall back to start.
        dinitctl restart "$DINIT_UNIT" 2>/dev/null || dinitctl start "$DINIT_UNIT"
        echo "      Done."
        ;;
    none)
        echo "      Skipped. Add this to ~/.config/hypr/hyprland.conf (or machine.conf):"
        echo ""
        echo "        exec-once = $INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/daemon.py"
        echo ""
        echo "      Launching it from Hyprland means it inherits WAYLAND_DISPLAY,"
        echo "      XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS automatically."
        echo "      Trade-off: no automatic restart if the daemon crashes."
        ;;
esac

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
case "$INIT_SYSTEM" in
    systemd)
        echo "Check service status:"
        echo "  systemctl --user status meetingbar"
        echo "  journalctl --user -u meetingbar -f"
        ;;
    dinit)
        echo "Check service status:"
        echo "  dinitctl status $DINIT_UNIT"
        echo "  tail -f $LOG_FILE"
        echo ""
        echo "If the daemon starts but the overlay never appears, the dinit user"
        echo "instance probably lacks the Wayland session environment. Capture it"
        echo "from inside the session and point env-file at it:"
        echo "  mkdir -p $(dirname "$ENV_FILE")"
        echo "  printenv WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS  # inspect"
        echo "  then uncomment env-file in $DINIT_DIR/$DINIT_UNIT"
        ;;
    none)
        echo "Check it is running:"
        echo "  pgrep -af 'daemon\\.py'"
        ;;
esac
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
