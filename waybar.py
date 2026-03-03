"""
Waybar custom module script.

Waybar calls this every 30 seconds and expects a JSON line on stdout.
It reads the state file written by daemon.py — no direct API calls.

See themes/waybar-module.json for the Waybar config block.

Waybar CSS classes emitted:
    free     → no events coming up
    upcoming → meeting in >10 min (neutral)
    soon     → meeting in ≤10 min (yellow)
    urgent   → meeting in ≤2 min  (red, pulsing via CSS)
    now      → meeting already started
"""
import json
import sys
from pathlib import Path

import config  # noqa: F401 — must be importable before i18n
from i18n import t

STATE_FILE = Path.home() / ".cache" / "meetingbar" / "waybar.json"


def main():
    if not STATE_FILE.exists():
        # Daemon not running yet
        print(json.dumps({"text": "󰃰", "class": "loading", "tooltip": t("loading")}))
        return

    try:
        data = json.loads(STATE_FILE.read_text())
        print(json.dumps(data))
    except Exception as e:
        print(json.dumps({"text": "󰃰 !", "class": "error", "tooltip": str(e)}))


if __name__ == "__main__":
    main()
