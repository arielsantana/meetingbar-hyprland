"""Simple translation system for user-visible strings.

Reads config.LANG to pick the active language. System logs always stay in English.

Usage:
    from i18n import t
    t("dismiss")                         # → "Dismiss" or "Ignorar"
    t("starts_in", mins=3, s="s")        # → "Starts in 3 minutes"
"""
import config

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # Overlay buttons
        "dismiss":          "Dismiss",
        "join":             "Join meeting",
        # Overlay time labels
        "starting_now":     "Starting now!",
        "starts_in":        "Starts in {mins} minute{s}",
        "started_ago":      "Started {mins} minute{s} ago",
        # RSVP labels
        "rsvp_accepted":    "✓ Accepted",
        "rsvp_tentative":   "? Tentative",
        "rsvp_needsAction": "○ No response",
        "rsvp_declined":    "✗ Declined",
        # Waybar / daemon UI
        "free":             "Free",
        "now":              "(now)",
        "remaining":        "{remaining} left",
        "next_in":          "→ next in {mins}m",
        "next_meeting_warn": "Next: {title} in {mins} min{s}",
        "loading":          "Loading...",
        "no_meetings":      "No meetings today",
    },
    "es": {
        # Overlay buttons
        "dismiss":          "Ignorar",
        "join":             "Unirse a la meeting",
        # Overlay time labels
        "starting_now":     "¡Comenzando ahora!",
        "starts_in":        "Comienza en {mins} minuto{s}",
        "started_ago":      "Comenzó hace {mins} minuto{s}",
        # RSVP labels
        "rsvp_accepted":    "✓ Aceptaste",
        "rsvp_tentative":   "? Tentativo",
        "rsvp_needsAction": "○ Sin respuesta",
        "rsvp_declined":    "✗ Declinaste",
        # Waybar / daemon UI
        "free":             "Libre",
        "now":              "(ahora)",
        "remaining":        "quedan {remaining}",
        "next_in":          "→ próx en {mins}m",
        "next_meeting_warn": "Próx: {title} en {mins} min{s}",
        "loading":          "Iniciando meetingbar...",
        "no_meetings":      "Sin meetings hoy",
    },
}


def t(key: str, **kwargs) -> str:
    """Return the translated string for *key* in the configured language."""
    lang = getattr(config, "LANG", "en")
    strings = _STRINGS.get(lang) or _STRINGS["en"]
    template = strings.get(key) or _STRINGS["en"].get(key, key)
    return template.format(**kwargs) if kwargs else template
