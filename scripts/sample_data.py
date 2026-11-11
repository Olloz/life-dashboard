"""Write site/data.enc from realistic sample data (passphrase: test) for UI work.
Usage: python scripts/sample_data.py [--errors]"""
import json, math, pathlib, sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from build import assemble  # noqa: E402
from dashboard.crypto import encrypt  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
L = ZoneInfo("Europe/London")
today = datetime.now(L).date()


def ev(day, title, s, e, cal="Uni", loc=""):
    d = today + timedelta(days=day)
    mk = lambda hm: datetime.combine(d, datetime.strptime(hm, "%H:%M").time(), L).isoformat()
    return {"title": title, "start": mk(s), "end": mk(e), "all_day": False, "calendar": cal, "location": loc}


def allday(day, title, days=1, cal="Home"):
    d = today + timedelta(days=day)
    return {"title": title, "start": d.isoformat(), "end": (d + timedelta(days=days)).isoformat(),
            "all_day": True, "calendar": cal, "location": ""}


events = [
    allday(0, "Reading week starts"),
    {**ev(-1, "Hackathon", "18:00", "18:00", cal="Personal"), "end": ev(0, "x", "08:30", "08:30")["end"]},
    ev(0, "Machine Learning lecture", "09:00", "11:00", loc="Bush House 2.01"),
    ev(0, "Group project meeting", "13:00", "14:00", loc="Library café"),
    ev(0, "Five-a-side", "18:30", "19:30", cal="Personal", loc="Elephant & Castle"),
    ev(1, "Algorithms tutorial", "10:00", "11:00"),
    ev(1, "Dentist", "15:30", "16:00", cal="Personal"),
    ev(2, "ML coursework due", "12:00", "12:00"),
    ev(2, "Shift at café", "17:00", "21:00", cal="Work"),
    ev(3, "Databases lab", "14:00", "16:00"),
    allday(4, "Weekend at home", days=2),
    ev(5, "Lunch with Sam", "13:00", "14:30", cal="Personal"),
    ev(6, "Essay submission", "23:59", "23:59"),
]

emails = [
    {"from": "Dr Patel <r.patel@kcl.ac.uk>", "subject": f"Coursework deadline moved to {(today + timedelta(days=9)).day} Nov",
     "date": (datetime.now(L) - timedelta(hours=3)).isoformat(), "preview": "Hi all, due to the server outage the ML coursework deadline has moved. Please make sure your submission includes the notebook.",
     "unread": True, "score": 9, "reasons": ["uni sender", "unread", "subject: deadline", "preview: submission"]},
    {"from": "Student Finance England <info@slc.co.uk>", "subject": "Action required: confirm your details",
     "date": (datetime.now(L) - timedelta(hours=20)).isoformat(), "preview": "You need to confirm your attendance before your next payment can be released.",
     "unread": True, "score": 6, "reasons": ["unread", "subject: action required", "preview: payment"]},
    {"from": "Sam Okafor <sam.okafor@gmail.com>", "subject": "Re: interview prep on Thursday?",
     "date": (datetime.now(L) - timedelta(days=1, hours=2)).isoformat(), "preview": "Yeah Thursday works, shall we do 4pm in the library? Bring your CV.",
     "unread": True, "score": 4, "reasons": ["unread", "subject: interview"]},
    {"from": "Accommodation Office <housing@kcl.ac.uk>", "subject": "Rent reminder",
     "date": (datetime.now(L) - timedelta(days=2)).isoformat(), "preview": "This is a reminder that your next rent instalment is due on 1 December.",
     "unread": False, "score": 5, "reasons": ["uni sender", "subject: reminder"]},
]

hourly = []
for dd in range(7):
    for hh in range(24):
        t = datetime.combine(today + timedelta(days=dd), datetime.min.time()) + timedelta(hours=hh)
        temp = round(7 + 4 * math.sin((hh - 9) / 24 * 2 * math.pi) + dd * 0.3, 1)
        hourly.append({"time": t.strftime("%Y-%m-%dT%H:%M"), "temp": temp, "feels": round(temp - 2.5, 1),
                       "rain": 70 if (dd == 0 and 15 <= hh <= 18) else (40 if dd == 2 else 10),
                       "wind": 18, "code": 61 if (dd == 0 and 15 <= hh <= 18) else 3})
daily = [{"date": (today + timedelta(days=d)).isoformat(), "min": 4 + d * 0.3, "max": 11 + d * 0.3,
          "sunrise": f"{(today + timedelta(days=d)).isoformat()}T07:12", "sunset": f"{(today + timedelta(days=d)).isoformat()}T16:15",
          "rain": [80, 20, 40, 10, 10, 30, 60][d]} for d in range(7)]

table_teams = ["Arsenal", "Manchester City", "Liverpool", "Aston Villa", "Chelsea", "Newcastle United", "Tottenham Hotspur",
               "Brighton & Hove Albion", "Manchester United", "Brentford", "Fulham", "Crystal Palace", "Bournemouth",
               "Nottingham Forest", "West Ham United", "Everton", "Sunderland", "Wolverhampton Wanderers", "Leeds United", "Burnley"]
football = {
    "next": {"opponent": "Leeds United", "date": datetime.combine(today + timedelta(days=10), datetime.min.time(), L).replace(hour=15).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
             "home": True, "competition": "Premier League"},
    "results": [
        {"date": "2026-11-08T14:00Z", "opponent": "Sunderland", "home": False, "score": "0-1", "outcome": "L"},
        {"date": "2026-10-31T15:00Z", "opponent": "Tottenham Hotspur", "home": True, "score": "2-2", "outcome": "D"},
        {"date": "2026-10-24T15:00Z", "opponent": "Everton", "home": False, "score": "3-1", "outcome": "W"},
        {"date": "2026-10-17T15:00Z", "opponent": "Brentford", "home": True, "score": "2-0", "outcome": "W"},
        {"date": "2026-10-10T15:00Z", "opponent": "Fulham", "home": False, "score": "3-2", "outcome": "W"},
    ],
    "table": [{"pos": i + 1, "team": t, "played": 10, "gd": 12 - i * 2 + (i > 10), "points": 27 - i - (i > 5),
               "is_team": t == "Chelsea"} for i, t in enumerate(table_teams)],
}

err = "--errors" in sys.argv
cfg = json.loads((ROOT / "config.json").read_text())
boom = lambda: (_ for _ in ()).throw(ConnectionError("timed out reaching the server"))
data = assemble(cfg, {"events": lambda: events, "emails": boom if err else (lambda: emails),
                      "weather": lambda: {"hourly": hourly, "daily": daily}, "football": boom if err else (lambda: football)},
                datetime.now(timezone.utc))
(ROOT / "site" / "data.enc").write_text(json.dumps(encrypt(data, "test")))
print("wrote site/data.enc", "(with errors)" if err else "")
