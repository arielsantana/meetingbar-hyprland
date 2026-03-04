# Setup Guide

## Prerequisites

- Hyprland (any recent version)
- Waybar
- Python 3.11+
- `gtk4-layer-shell` package (recommended for fullscreen overlay)
- GNOME Online Accounts configured with at least one Google account

## 1. Google Account (GNOME Online Accounts)

No Cloud Console, no credentials.json, no OAuth dance needed.

1. Open **GNOME Settings → Online Accounts**
2. Click **Add account → Google**
3. Sign in with your Google account
4. Make sure **Calendar** is toggled on
5. That's it — GOA handles token refresh automatically

> If you don't have GNOME Settings, install `gnome-control-center`. GOA itself
> (`gnome-online-accounts`) is the only runtime dependency.

## 2. Install

```bash
git clone https://github.com/arielsantana/meetingbar-hyprland.git ~/meetingbar
cd ~/meetingbar
./install.sh
```

`install.sh` will:
- Create a virtualenv at `.venv/` with system site-packages (required for PyGObject/GTK)
- Install Python dependencies
- Generate `~/.config/systemd/user/meetingbar.service` with the correct paths
- Enable and start the service

## 3. Hyprland — window rules

Add to `~/.config/hypr/hyprland.conf` (Hyprland 0.42+ block syntax):

```
windowrule {
    float       = class:(meetingbar.overlay)
    stayfocused = class:(meetingbar.overlay)
    pin         = class:(meetingbar.overlay)
}

exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR DISPLAY DBUS_SESSION_BUS_ADDRESS
```

See `themes/hyprland-rules.conf` for a ready-to-paste snippet.

> `gtk4-layer-shell` handles fullscreen natively when installed, so no
> `fullscreen` window rule is needed.

## 4. Waybar

Add to your Waybar config (see `themes/waybar-module.json`):

```json
"custom/meetingbar": {
    "exec": "python3 /path/to/meetingbar/waybar.py",
    "interval": 30,
    "return-type": "json",
    "format": "{}"
}
```

> `install.sh` prints the exact block with the correct path for your system — just copy-paste from its output.

Add `"custom/meetingbar"` to your `modules-left`, `modules-center`, or `modules-right` array.

Add CSS from `themes/waybar.css` to your `style.css`.

## 5. Verify

```bash
systemctl --user status meetingbar
journalctl --user -u meetingbar -f
```

## Troubleshooting

**Service fails to start**
```bash
journalctl --user -u meetingbar -n 30
```
Check that the venv exists at the install path and that PyGObject is accessible:
```bash
# Replace with your actual install path (printed by install.sh)
/path/to/meetingbar/.venv/bin/python3 -c "import gi; print('OK')"
```

**Overlay doesn't appear / blank screen**

Make sure `WAYLAND_DISPLAY` is exported to the service:
```bash
systemctl --user show-environment | grep WAYLAND
```
If missing, add the `exec-once` import line to your Hyprland config (see step 3) and reboot.

**No calendar events fetched**

- Check GOA is configured: GNOME Settings → Online Accounts
- Make sure Calendar is enabled for your Google account
- Look for GOA errors: `journalctl --user -u meetingbar -f`

**Overlay appears but stays behind windows**

Install `gtk4-layer-shell` from your package manager, then restart the service:
```bash
sudo pacman -S gtk4-layer-shell   # Arch
systemctl --user restart meetingbar
```

**Multiple Google accounts**

Add each account in GNOME Online Accounts. The daemon will discover and merge
all of them automatically. Account tags appear in the Waybar tooltip.
