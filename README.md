# meetingbar-hyprland

Calendar meeting overlay and Waybar status for Hyprland — zero auth setup, native GTK4 fullscreen.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<!-- Add a screenshot here: ![Screenshot](screenshot.png) -->

## Features

- **GTK4 fullscreen overlay** — blocks your screen N minutes before each meeting with Join/Dismiss buttons; nobody else has this
- **Zero auth setup** — uses GNOME Online Accounts (already configured in Settings → Online Accounts); no Cloud Console, no credentials.json
- **Hyprland-native** — gtk4-layer-shell, `pin`/`float`/`stayfocused` window rules, works with Hyprland 0.42+
- **Waybar integration** — status module with CSS classes (`free`, `upcoming`, `soon`, `urgent`, `now`)
- **Multi-account** — merges meetings from all your Google accounts with account tags
- **RSVP-aware** — color-coded border per response status (accepted/tentative/no-response/declined)
- **i18n** — English and Spanish UI; set `LANG` in `config.py`

## Requirements

| Dependency | Required | Notes |
|------------|----------|-------|
| Hyprland | Yes | 0.42+ for block window rule syntax |
| Waybar | Yes | For the status module |
| systemd | Yes | User sessions (`systemctl --user`); distros without systemd not supported |
| GNOME Online Accounts | Yes | Runtime DBus service — configure via Settings → Online Accounts |
| Python 3.11+ | Yes | |
| `python-gobject` | Yes | System package (`python3-gi` on Debian/Ubuntu); required for GTK4 and GOA |
| `libnotify` (`notify-send`) | Yes | Desktop notifications before meetings |
| `xdg-utils` (`xdg-open`) | Yes | Opens meeting links in your browser |
| Sound player | No | `pw-play` (PipeWire), `paplay` (PulseAudio), or `aplay` (ALSA) — tried in that order; missing = no sound |
| `gtk4-layer-shell` | No | Recommended — enables native fullscreen overlay; falls back to Hyprland window rules |

## Quick Install

```bash
git clone https://github.com/arielsantana/meetingbar-hyprland.git ~/meetingbar
cd ~/meetingbar
./install.sh
```

Then add snippets from `themes/` to your Waybar and Hyprland configs (the installer prints exact instructions).

## Configuration

Edit `config.py`:

| Option | Default | Description |
|--------|---------|-------------|
| `NOTIFY_BEFORE_MINUTES` | `2` | Show overlay this many minutes before start |
| `POLL_INTERVAL` | `300` | Refresh Google Calendar every N seconds |
| `CHECK_INTERVAL` | `10` | Check for upcoming events every N seconds |
| `MAX_TITLE_LENGTH` | `25` | Truncate meeting title in Waybar after N chars |
| `LOG_LEVEL` | `"INFO"` | `"DEBUG"` logs every event on each tick |
| `LANG` | `"en"` | UI language: `"en"` or `"es"` |

## Customization

### Waybar

Paste the module block from `themes/waybar-module.json` into your Waybar config, and the styles from `themes/waybar.css` into your `style.css`. Update the `exec` path if you installed to a different directory.

### Hyprland window rules

Paste the block from `themes/hyprland-rules.conf` into your `hyprland.conf`. Already using the 0.42+ block syntax — no `windowrulev2` lines needed.

### Language

```python
# config.py
LANG = "es"   # Spanish overlay and Waybar text
```

## How it works

```
gcal.py      reads today's events from Google Calendar API using GOA OAuth tokens
daemon.py    polls gcal every POLL_INTERVAL s, writes Waybar state, spawns overlay
waybar.py    reads the state file, prints a JSON line for Waybar on each call
overlay.py   GTK4 fullscreen window with Join/Dismiss, launched as subprocess
```

The daemon runs as a `systemd --user` service. It never stores credentials — GNOME Online Accounts handles OAuth token refresh transparently.

## Troubleshooting

**Service not starting**
```bash
journalctl --user -u meetingbar -n 20
```

**Overlay doesn't appear**

Check `WAYLAND_DISPLAY` is exported to the service:
```bash
systemctl --user show-environment | grep WAYLAND
```
If missing, add to `hyprland.conf` and reboot:
```
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR DISPLAY DBUS_SESSION_BUS_ADDRESS
```

**No events fetched**

Verify GNOME Online Accounts: Settings → Online Accounts → your Google account → Calendar enabled.

**Overlay stays behind other windows**

Install `gtk4-layer-shell` from your package manager (`pacman -S gtk4-layer-shell` on Arch), then restart the service.

**Waybar module not showing**

Make sure `"custom/meetingbar"` is in your modules array and the `exec` path in the module config matches where you installed meetingbar.

**Wrong language in overlay**

Set `LANG = "es"` (or `"en"`) in `config.py`, then restart the service:
```bash
systemctl --user restart meetingbar
```

## Contributing

Bug reports, feature requests, and questions are welcome — open an [issue](https://github.com/arielsantana/meetingbar-hyprland/issues).

## Credits

Inspired by [MeetingBar](https://github.com/leits/MeetingBar) for macOS by [@leits](https://github.com/leits).

## License

[MIT](LICENSE) © 2026 Ariel Santana
