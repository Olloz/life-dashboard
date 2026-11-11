"""iCloud calendar over CalDAV, recurring events expanded."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import caldav
import recurring_ical_events

URL = "https://caldav.icloud.com"


def _when(value, tz):
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=tz)).astimezone(tz)
    return value  # a date: all-day


def normalise(comp, tz, calendar_name):
    start = _when(comp.decoded("dtstart"), tz)
    if "dtend" in comp:
        end = _when(comp.decoded("dtend"), tz)
    elif "duration" in comp:
        end = start + comp.decoded("duration")
    else:
        end = start
    return {"title": str(comp.get("summary") or "(no title)"), "start": start.isoformat(), "end": end.isoformat(),
            "all_day": not isinstance(start, datetime), "calendar": calendar_name,
            "location": str(comp.get("location") or "")}


def fetch(cfg, user, pw):
    tz = ZoneInfo(cfg["timezone"])
    start = datetime.combine(date.today(), datetime.min.time(), tz)
    end = start + timedelta(days=cfg["calendar_days"])
    events = []
    with caldav.DAVClient(url=URL, username=user, password=pw) as client:
        for c in client.principal().calendars():
            try:
                found = c.search(start=start, end=end, event=True, expand=False)
            except Exception:
                continue  # e.g. Reminders lists that reject event queries
            for obj in found:
                for comp in recurring_ical_events.of(obj.icalendar_instance).between(start, end):
                    events.append(normalise(comp, tz, c.name or ""))
    return sorted(events, key=lambda e: (e["start"][:10], not e["all_day"], e["start"]))
