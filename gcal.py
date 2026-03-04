"""
Google Calendar client using GNOME Online Accounts (GOA).

No credentials.json or Google Cloud Console needed — reads OAuth tokens
from accounts already configured in GNOME Settings → Online Accounts.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import logging
import gi
gi.require_version("Goa", "1.0")
from gi.repository import Goa

log = logging.getLogger("meetingbar")

from meeting_links import find_meeting_link

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CALENDAR_API = "https://www.googleapis.com/calendar/v3/calendars"


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub(" ", text)


def _short_name(email: str) -> str:
    """user@example.com → example"""
    domain = email.split("@")[-1]
    return domain.split(".")[0]


class GoaCalendarClient:
    def __init__(self, goa_object):
        account = goa_object.get_account()
        self._goa_object = goa_object
        self._oauth2 = goa_object.get_oauth2_based()
        self.email = account.props.identity
        self.account_name = _short_name(self.email)

    def _get_token(self) -> str:
        token, _ = self._oauth2.call_get_access_token_sync(None)
        return token

    def _api_get(self, path: str, params: dict) -> dict:
        token = self._get_token()
        url = f"{_CALENDAR_API}/{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def fetch_today_events(self) -> list[dict]:
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        try:
            data = self._api_get("primary/events", {
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
            })
        except Exception as e:
            log.error(f"[gcal:{self.account_name}] Error fetching events: {e}")
            return []

        events = []
        for item in data.get("items", []):
            self._log_raw_event(item)
            event = self._parse_event(item)
            if event:
                events.append(event)
        return events

    def _log_raw_event(self, item: dict):
        name = item.get("account_name", self.account_name)
        summary = item.get("summary", "?")
        location = item.get("location", "—")
        description = (item.get("description") or "")[:80].replace("\n", " ")
        conf = item.get("conferenceData")
        conf_entries = []
        if conf:
            for ep in conf.get("entryPoints", []):
                conf_entries.append(f"{ep.get('entryPointType')}={ep.get('uri')}")
        log.debug(
            f"[gcal:{self.account_name}] RAW '{summary}' | "
            f"location='{location}' | desc='{description}' | "
            f"conferenceData={conf_entries or '—'}"
        )

    def _parse_event(self, item: dict) -> dict | None:
        start_raw = item.get("start", {})
        end_raw = item.get("end", {})

        if "dateTime" in start_raw:
            start_dt = datetime.fromisoformat(start_raw["dateTime"])
            end_dt = datetime.fromisoformat(end_raw["dateTime"])
            all_day = False
        elif "date" in start_raw:
            start_dt = datetime.fromisoformat(start_raw["date"]).astimezone()
            end_dt = datetime.fromisoformat(end_raw["date"]).astimezone()
            all_day = True
        else:
            return None

        rsvp = "needsAction"
        for attendee in item.get("attendees", []):
            if attendee.get("self"):
                rsvp = attendee.get("responseStatus", "needsAction")
                break

        location = item.get("location") or ""
        html_link = item.get("htmlLink") or ""
        description = item.get("description") or ""
        desc_stripped = _strip_html(description)

        # conferenceData is the modern way Google Calendar stores Meet links
        conference_url = ""
        for entry in (item.get("conferenceData") or {}).get("entryPoints", []):
            if entry.get("entryPointType") == "video":
                conference_url = entry.get("uri") or ""
                break

        meeting_link = None
        for text in [conference_url, location, description, desc_stripped]:
            if text:
                meeting_link = find_meeting_link(text)
                if meeting_link:
                    if meeting_link["service"] == "meet" and self.email:
                        sep = "&" if "?" in meeting_link["url"] else "?"
                        meeting_link["url"] += f"{sep}authuser={self.email}"
                    break

        return {
            "id": f"{self.account_name}:{item['id']}",
            "summary": item.get("summary") or "No title",
            "start": start_dt,
            "end": end_dt,
            "all_day": all_day,
            "rsvp": rsvp,
            "meeting_link": meeting_link,
            "location": location,
            "updated": item.get("updated") or "",
            "account": self.account_name,
        }


def discover_accounts() -> list[GoaCalendarClient]:
    """Return a GoaCalendarClient for each Google account in GOA with calendar enabled."""
    try:
        client = Goa.Client.new_sync(None)
    except Exception as e:
        log.error(f"[gcal] Error connecting to GOA: {e}")
        return []

    clients = []
    for obj in client.get_accounts():
        account = obj.get_account()
        if account.props.provider_type != "google":
            continue
        if account.props.calendar_disabled:
            continue
        oauth2 = obj.get_oauth2_based()
        if oauth2 is None:
            continue
        c = GoaCalendarClient(obj)
        log.info(f"[gcal] GOA account: {c.email}")
        clients.append(c)

    return clients
