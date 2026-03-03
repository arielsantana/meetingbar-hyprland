"""
GTK4 fullscreen overlay shown ~N minutes before a meeting.

Called as a subprocess by daemon.py:
    python3 overlay.py /tmp/meetingbar_event_XXXX.json

Hyprland window rules (~/.config/hypr/hyprland.conf):
    windowrule {
        float      = class:(meetingbar.overlay)
        stayfocused = class:(meetingbar.overlay)
        pin        = class:(meetingbar.overlay)
    }
    # gtk4-layer-shell handles fullscreen when available
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from i18n import t

# Map RSVP status → border accent color
RSVP_COLORS = {
    "accepted":    "#33ccff",
    "tentative":   "#f0a500",
    "needsAction": "#888899",
    "declined":    "#555566",
}


class MeetingOverlay(Gtk.ApplicationWindow):
    def __init__(self, app, event):
        super().__init__(application=app)
        self.event = event
        self._blink_state = True
        self._app = app

        self.set_title("MeetingBar")
        self.set_decorated(False)

        self._try_layer_shell()
        self._apply_css()
        self._build_ui()

        rsvp = event.get("rsvp", "needsAction")
        if rsvp in ("accepted", "tentative"):
            GLib.timeout_add(600, self._blink)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self.add_controller(key_ctrl)

    def _try_layer_shell(self):
        try:
            gi.require_version("Gtk4LayerShell", "1.0")
            from gi.repository import Gtk4LayerShell
            Gtk4LayerShell.init_for_window(self)
            Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_exclusive_zone(self, -1)
            for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
                Gtk4LayerShell.set_anchor(self, getattr(Gtk4LayerShell.Edge, edge), True)
        except Exception:
            pass  # Hyprland window rules handle positioning via app_id

    def _apply_css(self):
        rsvp = self.event.get("rsvp", "needsAction")
        accent = RSVP_COLORS.get(rsvp, RSVP_COLORS["needsAction"])

        css = f"""
        * {{
            font-family: "JetBrainsMonoNL Nerd Font", "JetBrains Mono", monospace;
        }}
        window {{
            background: rgba(0, 0, 15, 0.72);
        }}
        .overlay-card {{
            background: rgba(18, 20, 32, 0.96);
            border: 2px solid {accent};
            border-radius: 24px;
            padding: 64px 120px;
            min-width: 860px;
        }}
        .overlay-card.blink-on  {{ border-color: {accent}; }}
        .overlay-card.blink-off {{ border-color: rgba(18, 20, 32, 0.3); }}
        .meeting-title {{
            font-size: 58px;
            font-weight: bold;
            color: #e8eaf6;
        }}
        .meeting-time {{
            font-size: 34px;
            color: {accent};
        }}
        .meeting-rsvp {{
            font-size: 22px;
            color: rgba(200, 200, 220, 0.60);
        }}
        .btn-dismiss {{
            font-size: 24px;
            padding: 16px 52px;
            background: rgba(255,255,255,0.07);
            color: rgba(200,200,220,0.80);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 12px;
        }}
        .btn-dismiss:hover {{ background: rgba(255,255,255,0.13); }}
        .btn-join {{
            font-size: 24px;
            font-weight: bold;
            padding: 16px 52px;
            background: {accent};
            color: #0d0f1a;
            border: none;
            border-radius: 12px;
        }}
        .btn-join:hover {{ opacity: 0.88; }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self):
        event = self.event
        rsvp = event.get("rsvp", "needsAction")
        title = event.get("summary", "Meeting")
        start = event["start"]
        if isinstance(start, str):
            start = datetime.fromisoformat(start)

        now = datetime.now().astimezone()
        mins = int((start - now).total_seconds() / 60)
        if mins > 0:
            time_text = t("starts_in", mins=mins, s="s" if mins != 1 else "")
        elif mins == 0:
            time_text = t("starting_now")
        else:
            abs_mins = abs(mins)
            time_text = t("started_ago", mins=abs_mins, s="s" if abs_mins != 1 else "")

        # Card
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.card.set_halign(Gtk.Align.CENTER)
        self.card.set_valign(Gtk.Align.CENTER)
        self.card.add_css_class("overlay-card")
        self.card.add_css_class("blink-on")

        lbl_title = Gtk.Label(label=title)
        lbl_title.set_wrap(True)
        lbl_title.add_css_class("meeting-title")
        self.card.append(lbl_title)

        lbl_time = Gtk.Label(label=time_text)
        lbl_time.add_css_class("meeting-time")
        self.card.append(lbl_time)

        rsvp_label = t(f"rsvp_{rsvp}")
        lbl_rsvp = Gtk.Label(label=rsvp_label)
        lbl_rsvp.add_css_class("meeting-rsvp")
        self.card.append(lbl_rsvp)

        # Buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        btn_row.set_halign(Gtk.Align.CENTER)
        btn_row.set_margin_top(16)

        btn_dismiss = Gtk.Button(label=t("dismiss"))
        btn_dismiss.add_css_class("btn-dismiss")
        btn_dismiss.connect("clicked", lambda _: self._dismiss())
        btn_row.append(btn_dismiss)

        if event.get("meeting_link"):
            btn_join = Gtk.Button(label=t("join"))
            btn_join.add_css_class("btn-join")
            btn_join.connect("clicked", lambda _: self._join())
            btn_row.append(btn_join)

        self.card.append(btn_row)

        overlay = Gtk.Overlay()
        bg = Gtk.Box()
        overlay.set_child(bg)
        overlay.add_overlay(self.card)
        self.set_child(overlay)

    def _blink(self):
        if not self.get_visible():
            return False
        self._blink_state = not self._blink_state
        self.card.remove_css_class("blink-on")
        self.card.remove_css_class("blink-off")
        self.card.add_css_class("blink-on" if self._blink_state else "blink-off")
        return True

    def _on_key(self, controller, keyval, keycode, state):
        pass  # only buttons close the overlay

    def _dismiss(self):
        self._app.quit()

    def _join(self):
        url = (self.event.get("meeting_link") or {}).get("url", "")
        if url:
            subprocess.Popen(["xdg-open", url])
        self._app.quit()


def main():
    if len(sys.argv) < 2:
        print("Usage: overlay.py <event_json_file>", file=sys.stderr)
        sys.exit(1)

    event_file = Path(sys.argv[1])
    event = json.loads(event_file.read_text())
    try:
        event_file.unlink(missing_ok=True)
    except (PermissionError, OSError):
        pass

    def on_activate(app):
        win = MeetingOverlay(app, event)
        win.set_default_size(3840, 2160)
        win.present()

    app = Gtk.Application(application_id="meetingbar.overlay")
    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()
