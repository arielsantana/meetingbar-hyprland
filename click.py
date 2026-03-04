"""
Waybar on-click handler: opens the next meeting link if available.
Add to waybar config:
    "on-click": "python3 /path/to/meetingbar/click.py"
"""
import json
import subprocess
import sys
import time
from pathlib import Path

STATE_FILE = Path.home() / ".cache" / "meetingbar" / "waybar.json"

# Known browser window classes (lowercase). Add yours if missing.
_BROWSER_CLASSES = {
    "chromium", "google-chrome", "chrome",
    "firefox", "firefox-esr",
    "brave-browser", "brave",
    "vivaldi", "opera", "microsoft-edge",
}


def _find_browser() -> tuple[int, str] | None:
    """Return (workspace_id, window_class) for the first browser window found."""
    try:
        raw = subprocess.check_output(["hyprctl", "clients", "-j"], stderr=subprocess.DEVNULL)
        clients = json.loads(raw)
    except Exception:
        return None

    for client in clients:
        cls = client.get("class", "")
        cls_lower = cls.lower()
        if cls_lower in _BROWSER_CLASSES or any(b in cls_lower for b in ("chrome", "firefox", "brave", "vivaldi")):
            ws_id = (client.get("workspace") or {}).get("id", 0)
            if ws_id > 0:
                return ws_id, cls

    return None


def main():
    if not STATE_FILE.exists():
        sys.exit(0)

    try:
        data = json.loads(STATE_FILE.read_text())
    except Exception:
        sys.exit(0)

    url = data.get("link")
    if not url:
        sys.exit(0)

    browser = _find_browser()

    if browser:
        ws_id, cls = browser
        # Switch to the workspace where the browser lives
        subprocess.run(["hyprctl", "dispatch", "workspace", str(ws_id)], capture_output=True)

    subprocess.Popen(["xdg-open", url])

    if browser:
        _, cls = browser
        # Give the browser a moment to receive the new tab, then bring it to front
        time.sleep(0.3)
        subprocess.run(["hyprctl", "dispatch", "focuswindow", f"class:{cls}"], capture_output=True)


if __name__ == "__main__":
    main()
