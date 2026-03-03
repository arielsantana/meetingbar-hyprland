"""
MeetingBar daemon for Hyprland + Waybar.

Runs as a systemd user service. Every CHECK_INTERVAL seconds:
  - Refreshes Google Calendar events (every POLL_INTERVAL seconds)
  - Updates the Waybar state file
  - Shows overlay + notification + sound when a meeting is about to start
"""
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import config
from gcal import discover_accounts
from i18n import t

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL, logging.INFO), format="%(levelname)-5s %(message)s")
log = logging.getLogger("meetingbar")

CACHE_DIR = Path.home() / ".cache" / "meetingbar"
WAYBAR_STATE = CACHE_DIR / "waybar.json"

# Waybar CSS class thresholds (minutes)
THRESHOLD_URGENT = config.NOTIFY_BEFORE_MINUTES
THRESHOLD_SOON = 10

# Sound files to try in order (PipeWire → PulseAudio → ALSA)
SOUND_CANDIDATES = [
    ("pw-play",  "/usr/share/sounds/freedesktop/stereo/bell.oga"),
    ("paplay",   "/usr/share/sounds/freedesktop/stereo/bell.oga"),
    ("aplay",    "/usr/share/sounds/alsa/Front_Center.wav"),
]


class MeetingBarDaemon:
    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.clients = discover_accounts()

        self.events: list[dict] = []
        self.last_refresh: datetime | None = None
        # processed: event_id → {'updated': str, 'end': datetime}
        # Tracks events we already showed the overlay for.
        # If the event is modified (updated field changes), we re-show it.
        self.processed: dict[str, dict] = {}
        self.overlay_proc: subprocess.Popen | None = None

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    # ------------------------------------------------------------------ loop

    def run(self):
        log.info("[meetingbar] Starting daemon...")
        while True:
            try:
                self._tick()
            except Exception as e:
                log.error(f"[meetingbar] Error in tick: {e}")
            time.sleep(config.CHECK_INTERVAL)

    def _handle_signal(self, signum, _frame):
        log.info(f"[meetingbar] Signal {signum} received, shutting down.")
        if self.overlay_proc and self.overlay_proc.poll() is None:
            self.overlay_proc.terminate()
        sys.exit(0)

    def _tick(self):
        now = datetime.now().astimezone()

        # Refresh events from Google Calendar periodically
        if self.last_refresh is None or (now - self.last_refresh).total_seconds() >= config.POLL_INTERVAL:
            log.info("[meetingbar] Syncing calendars...")
            all_events = []
            for client in self.clients:
                all_events.extend(client.fetch_today_events())
            all_events.sort(key=lambda e: e["start"])
            self.events = all_events
            self.last_refresh = now
            timed = [e for e in self.events if not e["all_day"]]
            log.info(f"[meetingbar] {len(timed)} events today.")
            for e in timed:
                log.debug(
                    f"[meetingbar]   • {e['start'].strftime('%H:%M')} '{e['summary']}' "
                    f"link={bool(e.get('meeting_link'))} rsvp={e['rsvp']}"
                )

        # Clean up processed entries for events that already ended
        self.processed = {
            eid: info
            for eid, info in self.processed.items()
            if info["end"] > now
        }

        # Check each event for the notification window
        for event in self.events:
            if event["all_day"]:
                continue
            if event["rsvp"] == "declined":
                continue

            seconds_until = (event["start"] - now).total_seconds()
            minutes_until = seconds_until / 60
            in_window = -0.25 < minutes_until < config.NOTIFY_BEFORE_MINUTES

            if not in_window:
                continue

            event_id = event["id"]
            already_shown = (
                event_id in self.processed
                and self.processed[event_id].get("updated") == event["updated"]
            )
            if already_shown:
                log.debug(f"[meetingbar] overlay already shown for '{event['summary']}', skip.")
                continue

            if event.get("meeting_link"):
                log.info(f"[meetingbar] >>> Showing overlay for '{event['summary']}'")
                self._show_overlay(event)
                self._send_notification(event, minutes_until)
                self._play_sound()
            else:
                log.info(f"[meetingbar] No meeting link for '{event['summary']}', skipping overlay.")

            self.processed[event_id] = {"updated": event["updated"], "end": event["end"]}

        self._update_waybar(now)

    # ---------------------------------------------------------- notifications

    def _show_overlay(self, event: dict):
        if self.overlay_proc and self.overlay_proc.poll() is None:
            return  # overlay already visible

        # Serialize datetimes to ISO strings for JSON
        payload = {
            **event,
            "start": event["start"].isoformat(),
            "end": event["end"].isoformat(),
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix="meetingbar_", delete=False
        ) as f:
            json.dump(payload, f)
            tmp_path = f.name

        env = os.environ.copy()
        wayland = env.get("WAYLAND_DISPLAY", "NOT SET")
        log.debug(f"[meetingbar] spawning overlay (WAYLAND_DISPLAY={wayland})")
        script = Path(__file__).parent / "overlay.py"
        self.overlay_proc = subprocess.Popen(
            [sys.executable, str(script), tmp_path],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        log.info(f"[meetingbar] overlay PID={self.overlay_proc.pid}")

    def _send_notification(self, event: dict, minutes_until: float):
        title = event.get("summary", "Meeting")
        mins = int(minutes_until)
        if mins > 0:
            body = t("starts_in", mins=mins, s="s" if mins != 1 else "")
        else:
            body = t("starting_now")

        subprocess.Popen(
            ["notify-send", "-u", "critical", "-t", "30000", title, body],
            stderr=subprocess.DEVNULL,
        )

    def _play_sound(self):
        for cmd, sound_file in SOUND_CANDIDATES:
            try:
                subprocess.Popen([cmd, sound_file], stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue

    # ------------------------------------------------------------ waybar state

    @staticmethod
    def _fmt_mins(mins: int) -> str:
        if mins < 60:
            return f"{mins}m"
        h, m = divmod(mins, 60)
        return f"{h}h {m}m" if m else f"{h}h"

    def _update_waybar(self, now: datetime):
        next_event = self._next_event(now)

        if next_event is None:
            data = {
                "text": f"󰃰 {t('free')}",
                "class": "free",
                "tooltip": self._build_tooltip(now),
            }
        else:
            mins = int((next_event["start"] - now).total_seconds() / 60)
            title = next_event["summary"]
            short_title = title[: config.MAX_TITLE_LENGTH] + ("…" if len(title) > config.MAX_TITLE_LENGTH else "")
            acc_tag = f" [{next_event['account']}]" if len(self.clients) > 1 else ""

            fmt = self._fmt_mins(mins)
            if mins < 0:
                css_class = "now"
                text = f"󰃰 {short_title} {t('now')}{acc_tag}"
            elif mins <= THRESHOLD_URGENT:
                css_class = "urgent"
                text = f"󰃰 {short_title} en {fmt}{acc_tag}"
            elif mins <= THRESHOLD_SOON:
                css_class = "soon"
                text = f"󰃰 {short_title} en {fmt}{acc_tag}"
            else:
                css_class = "upcoming"
                text = f"󰃰 en {fmt}{acc_tag}"

            link = (next_event.get("meeting_link") or {}).get("url", "")
            data = {
                "text": text,
                "class": css_class,
                "tooltip": self._build_tooltip(now),
                "link": link,
            }

        WAYBAR_STATE.write_text(json.dumps(data))

    def _next_event(self, now: datetime) -> dict | None:
        candidates = [
            e for e in self.events
            if not e["all_day"]
            and e["rsvp"] != "declined"
            and e["end"] > now
        ]
        if not candidates:
            return None

        # If one or more meetings are already in progress, show the most
        # recently started one — it's the one that needs attention right now.
        ongoing = [e for e in candidates if e["start"] <= now]
        if ongoing:
            ongoing.sort(key=lambda e: e["start"], reverse=True)
            return ongoing[0]

        # No meeting in progress — show the next upcoming one.
        candidates.sort(key=lambda e: e["start"])
        return candidates[0]

    def _build_tooltip(self, now: datetime) -> str:
        timed = [e for e in self.events if not e["all_day"]]
        if not timed:
            return t("no_meetings")

        RSVP_ICON = {
            "accepted":    "✓",
            "declined":    "✗",
            "tentative":   "?",
            "needsAction": "○",
        }
        lines = []
        for e in timed:
            past = e["end"] < now
            icon = RSVP_ICON.get(e["rsvp"], "○")
            start_str = e["start"].strftime("%H:%M")
            link_icon = " 🔗" if e.get("meeting_link") else ""
            acc_tag = f" [{e['account']}]" if len(self.clients) > 1 else ""
            line = f"{icon} {start_str}  {e['summary']}{link_icon}{acc_tag}"
            if past:
                line = f"<s>{line}</s>"  # strikethrough for past events
            lines.append(line)

        return "\n".join(lines)


if __name__ == "__main__":
    daemon = MeetingBarDaemon()
    daemon.run()
