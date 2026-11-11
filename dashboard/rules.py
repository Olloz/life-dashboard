"""Pure rules: email scoring, what to wear, deadlines, free gaps."""
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
DATE_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")[a-z]*\b", re.I)


def _keywords(text, words, each, cap, label, reasons):
    text = text.lower()
    hits = [w for w in words if w in text]
    reasons += [f"{label}: {w}" for w in hits]
    return min(len(hits) * each, cap)


def score_email(sender, subject, preview, unread, has_unsubscribe, cfg):
    m = cfg["mail"]
    reasons = []
    score = 0
    addr = sender.rsplit("<", 1)[-1].rstrip(">").strip().lower()
    if any(addr.endswith(d) for d in m["uni_domains"]):
        score += 3
        reasons.append("uni sender")
    if unread:
        score += 2
        reasons.append("unread")
    score += _keywords(subject, m["keywords"], 2, 4, "subject", reasons)
    score += _keywords(preview, m["keywords"], 1, 2, "preview", reasons)
    if has_unsubscribe or re.search(m["noise"], sender, re.I):
        score -= 4
        reasons.append("newsletter")
    return score, reasons


def what_to_wear(hourly, day):
    hours = [x for x in hourly if x["time"].startswith(day) and 8 <= int(x["time"][11:13]) <= 20]
    if not hours:
        return None
    feels = min(x["feels"] for x in hours)
    text = ("Heavy coat, layers" if feels < 5 else "Jacket or jumper" if feels < 12
            else "Light layer" if feels < 18 else "T-shirt weather")
    wet = next((x for x in hours if (x["rain"] or 0) >= 50), None)
    if wet:
        text += f" + umbrella (rain from {wet['time'][11:16]})"
    if any((x["wind"] or 0) >= 30 for x in hours):
        text += " + windproof"
    return {"text": text}


def is_deadline(title, cfg):
    return bool(re.search(cfg["deadline_pattern"], title, re.I))


def free_gaps(events, day, tz):
    z = ZoneInfo(tz)
    d = date.fromisoformat(day)
    lo, hi = datetime.combine(d, time(8), z), datetime.combine(d, time(22), z)
    busy = sorted(
        (max(datetime.fromisoformat(e["start"]), lo), min(datetime.fromisoformat(e["end"]), hi))
        for e in events if not e["all_day"]
    )
    gaps, cursor = [], lo
    for s, e in busy:
        if s > cursor and (s - cursor) >= timedelta(minutes=60):
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if hi - cursor >= timedelta(minutes=60):
        gaps.append((cursor, hi))
    return [{"start": s.isoformat(), "end": e.isoformat(), "minutes": int((e - s).total_seconds() // 60)}
            for s, e in gaps]


def _email_due(text, today):
    for m in DATE_RE.finditer(text):
        day, mon = int(m.group(1)), MONTHS.index(m.group(2)[:3].lower()) + 1
        try:
            due = date(today.year, mon, day)
            if due < today:
                due = date(today.year + 1, mon, day)
        except ValueError:
            continue
        if (due - today).days <= 30:
            return due
    return None


def find_deadlines(events, emails, today, cfg):
    out = []
    for e in events:
        if is_deadline(e["title"], cfg):
            due = date.fromisoformat(e["start"][:10])
            if due >= today:
                out.append({"title": e["title"], "due": due.isoformat(), "source": "calendar",
                            "days_left": (due - today).days})
    for m in emails:
        if m["score"] >= 5:
            due = _email_due(f"{m['subject']} {m['preview']}", today)
            if due:
                out.append({"title": m["subject"], "due": due.isoformat(), "source": "email",
                            "days_left": (due - today).days})
    return sorted(out, key=lambda x: x["due"])
