"""
Meeting URL detection — regex patterns ported from MeetingBar (Swift → Python).
Searches location, url, description fields in that priority order.
"""
import re

# Ordered by likelihood — most common first
MEETING_REGEXES = [
    ("meet",        r"https?://meet\.google\.com/(_meet/)?[a-z-]+"),
    ("zoom",        r"https://(?:[a-zA-Z0-9-.]+)?zoom(-x)?\.(?:us|com|com\.cn|de)/(?:my|[a-z]{1,2}|webinar)/[-a-zA-Z0-9()@:%_\+.~#?&=\/]*"),
    ("zoom_native", r"zoommtg://([a-z0-9-.]+)?zoom(-x)?\.(?:us|com|com\.cn|de)/join[-a-zA-Z0-9()@:%_\+.~#?&=\/]*"),
    ("teams",       r"https?://(gov\.)?teams\.microsoft\.(com|us)/l/meetup-join/[a-zA-Z0-9_%\/=\-\+\.?]+"),
    ("webex",       r"https?://(?:[A-Za-z0-9-]+\.)?webex\.com(?:/[-A-Za-z0-9]+/j\.php\?MTID=[A-Za-z0-9]+(?:&\S*)?|/(?:meet|join)/[A-Za-z0-9\-._@]+(?:\?\S*)?)"),
    ("jitsi",       r"https?://meet\.jit\.si/[^\s]*"),
    ("hangouts",    r"https?://hangouts\.google\.com/[^\s]*"),
    ("meet_stream", r"https?://stream\.meet\.google\.com/stream/[a-z0-9-]+"),
    ("slack",       r"https?://app\.slack\.com/huddle/[A-Za-z0-9./]+"),
    ("discord",     r"(http|https|discord)://(www\.)?(canary\.)?discord(app)?\.([a-zA-Z]{2,})(.+)?"),
    ("whereby",     r"https?://whereby\.com/[^\s]*"),
    ("ringcentral", r"https?://([a-z0-9.]+)?ringcentral\.com/[^\s]*"),
    ("gotomeeting", r"https?://([a-z0-9.]+)?gotomeeting\.com/[^\s]*"),
    ("bluejeans",   r"https?://([a-z0-9.]+)?bluejeans\.com/[^\s]*"),
    ("chime",       r"https?://([a-z0-9-.]+)?chime\.aws/[0-9]*"),
    ("skype",       r"https?://join\.skype\.com/[^\s]*"),
    ("youtube",     r"https?://((www|m)\.)?(youtube\.com|youtu\.be)/[^\s]*"),
    ("tuple",       r"https://tuple\.app/c/[^\s]*"),
    ("gather",      r"https?://app\.gather\.town/app/[A-Za-z0-9]+/[A-Za-z0-9_%\-]+\?(spawnToken|meeting)=[^\s]*"),
]

_COMPILED = [(svc, re.compile(pattern)) for svc, pattern in MEETING_REGEXES]


def find_meeting_link(text: str) -> dict | None:
    """Return {'service': str, 'url': str} for the first meeting URL found in text, or None."""
    if "://" not in text:
        return None
    for service, regex in _COMPILED:
        match = regex.search(text)
        if match:
            return {"service": service, "url": match.group(0)}
    return None
