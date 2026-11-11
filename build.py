"""Fetch every source, derive extras, write the encrypted site/data.enc.
Usage: python build.py [--plain data.json]   (plain copy is for local debugging only)"""
import json, os, pathlib, sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dashboard import rules
from dashboard.crypto import encrypt
from dashboard.sources import calendar, football, mail, weather

ROOT = pathlib.Path(__file__).parent


def _run(fn, secret):
    try:
        return fn()
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        return {"error": (msg.replace(secret, "***") if secret else msg)[:200]}  # redact before truncating


def _ok(x):
    return isinstance(x, list) or (isinstance(x, dict) and "error" not in x)


def assemble(cfg, sources, now, secret=""):
    data = {k: _run(fn, secret) for k, fn in sources.items()}
    today = now.astimezone(ZoneInfo(cfg["timezone"])).date()
    events = data["events"] if _ok(data["events"]) else []
    emails = data["emails"] if _ok(data["emails"]) else []
    data["generated"] = now.isoformat()
    data["deadlines"] = rules.find_deadlines(events, emails, today, cfg)
    data["week"] = {}
    for i in range(7):
        day = (today + timedelta(days=i)).isoformat()
        on_day = [e for e in events if not e["all_day"] and e["start"][:10] <= day <= e["end"][:10]]
        data["week"][day] = {
            "wear": rules.what_to_wear(data["weather"]["hourly"], day) if _ok(data["weather"]) else None,
            "gaps": rules.free_gaps(on_day, day, cfg["timezone"]) if _ok(data["events"]) else [],
        }
    data.update(data["week"][today.isoformat()])  # wear + gaps for today
    return data


def main(out=ROOT / "site" / "data.enc", plain=None):
    passphrase = os.environ.get("DASHBOARD_PASSPHRASE")
    if not passphrase:
        print("DASHBOARD_PASSPHRASE is not set", file=sys.stderr)
        return 2
    cfg = json.loads((ROOT / "config.json").read_text())
    user, pw = os.environ.get("ICLOUD_EMAIL"), os.environ.get("ICLOUD_APP_PASSWORD")

    def icloud(fetch):
        return (lambda: fetch(cfg, user, pw)) if user and pw else (lambda: {"error": "missing credentials"})

    data = assemble(cfg, {
        "events": icloud(calendar.fetch), "emails": icloud(mail.fetch),
        "weather": lambda: weather.fetch(cfg), "football": lambda: football.fetch(cfg),
    }, datetime.now(timezone.utc), secret=pw or "")

    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out).write_text(json.dumps(encrypt(data, passphrase)))
    if plain:
        pathlib.Path(plain).write_text(json.dumps(data, indent=2))
    for k in ("events", "emails", "weather", "football"):
        print(k, "ERROR " + data[k]["error"] if not _ok(data[k]) else f"ok ({len(data[k]) if isinstance(data[k], list) else 'dict'})")
    return 1 if not _ok(data["events"]) and not _ok(data["emails"]) else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(main(plain=args[1] if args[:1] == ["--plain"] else None))
