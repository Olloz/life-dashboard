from dashboard.sources import weather, football


def test_weather_parse_zips_hourly():
    raw = {"hourly": {"time": ["2026-11-11T08:00"], "temperature_2m": [7.1], "apparent_temperature": [4.0],
                      "precipitation_probability": [20], "wind_speed_10m": [12], "weather_code": [3]},
           "daily": {"time": ["2026-11-11"], "temperature_2m_min": [5], "temperature_2m_max": [9],
                     "sunrise": ["2026-11-11T07:10"], "sunset": ["2026-11-11T16:20"], "precipitation_probability_max": [40]}}
    w = weather.parse(raw)
    assert w["hourly"][0] == {"time": "2026-11-11T08:00", "temp": 7.1, "feels": 4.0, "rain": 20, "wind": 12, "code": 3}
    assert w["daily"][0] == {"date": "2026-11-11", "min": 5, "max": 9, "sunrise": "2026-11-11T07:10",
                             "sunset": "2026-11-11T16:20", "rain": 40}


def _comp(tid, name, home, score=None, winner=None):
    s = None if score is None else {"value": float(score), "displayValue": str(score)}
    return {"id": tid, "homeAway": "home" if home else "away", "score": s, "winner": winner,
            "team": {"id": tid, "displayName": name}}

def _event(date, comps, state, league="Premier League"):
    return {"date": date, "league": {"abbreviation": league},
            "competitions": [{"competitors": comps, "status": {"type": {"state": state}}}]}


def test_parse_schedule_next_and_results():
    played = {"events": [
        _event("2026-10-31T15:00Z", [_comp("363", "Chelsea", True, 1), _comp("1", "Spurs", False, 1)], "post"),
        _event("2026-11-08T15:00Z", [_comp("370", "Fulham", True, 2, False), _comp("363", "Chelsea", False, 3, True)], "post"),
    ]}
    upcoming = {"events": [
        _event("2026-11-27T20:00Z", [_comp("363", "Chelsea", False), _comp("9", "Everton", True)], "pre"),
        _event("2026-11-21T15:00Z", [_comp("363", "Chelsea", True), _comp("357", "Leeds United", False)], "pre"),
    ]}
    s = football.parse_schedule(played, upcoming, "363")
    assert s["next"] == {"opponent": "Leeds United", "date": "2026-11-21T15:00Z", "home": True, "competition": "Premier League"}
    assert s["results"][0] == {"date": "2026-11-08T15:00Z", "opponent": "Fulham", "home": False, "score": "3-2", "outcome": "W"}
    assert s["results"][1]["outcome"] == "D" and s["results"][1]["score"] == "1-1"


def test_parse_schedule_no_upcoming():
    assert football.parse_schedule({"events": []}, {"events": []}, "363") == {"next": None, "results": []}


def _row(tid, name, rank, pts):
    stats = [{"name": "rank", "value": rank}, {"name": "points", "value": pts},
             {"name": "gamesPlayed", "value": 10.0}, {"name": "pointDifferential", "value": 4.0}]
    return {"team": {"id": tid, "displayName": name}, "stats": stats}


def test_parse_table_marks_team_sorted():
    raw = {"children": [{"standings": {"entries": [_row("363", "Chelsea", 2.0, 20.0), _row("359", "Arsenal", 1.0, 27.0)]}}]}
    t = football.parse_table(raw, "363")
    assert [r["team"] for r in t] == ["Arsenal", "Chelsea"]
    assert t[1] == {"pos": 2, "team": "Chelsea", "played": 10, "gd": 4, "points": 20, "is_team": True}
    assert t[0]["is_team"] is False


# --- calendar + mail ---
from datetime import date, datetime
from zoneinfo import ZoneInfo
from icalendar import Event
from dashboard.sources import calendar as cal, mail

LONDON = ZoneInfo("Europe/London")


def _vevent(title, start, end, **extra):
    e = Event()
    if title:
        e.add("summary", title)
    e.add("dtstart", start)
    if end is not None:
        e.add("dtend", end)
    for k, v in extra.items():
        e.add(k, v)
    return e


def test_normalise_utc_event_to_london():
    ev = _vevent("Lecture", datetime(2026, 7, 15, 9, tzinfo=ZoneInfo("UTC")), datetime(2026, 7, 15, 10, tzinfo=ZoneInfo("UTC")),
                 location="Bush House")
    n = cal.normalise(ev, LONDON, "Uni")
    assert n == {"title": "Lecture", "start": "2026-07-15T10:00:00+01:00", "end": "2026-07-15T11:00:00+01:00",
                 "all_day": False, "calendar": "Uni", "location": "Bush House"}


def test_normalise_floating_time_is_london():
    n = cal.normalise(_vevent("Gym", datetime(2026, 11, 11, 18), datetime(2026, 11, 11, 19)), LONDON, "Home")
    assert n["start"] == "2026-11-11T18:00:00+00:00"


def test_normalise_all_day_multi_day():
    n = cal.normalise(_vevent("Trip", date(2026, 11, 11), date(2026, 11, 14)), LONDON, "Home")
    assert n["all_day"] and n["start"] == "2026-11-11" and n["end"] == "2026-11-14"


def test_normalise_missing_end_and_title():
    n = cal.normalise(_vevent(None, datetime(2026, 11, 11, 9, tzinfo=LONDON), None), LONDON, "Home")
    assert n["end"] == n["start"] and n["title"] == "(no title)"


def test_parse_message_decodes_utf8_headers_and_scores(CFG):
    raw = (b"From: =?UTF-8?B?Sm9zw6k=?= <j@kcl.ac.uk>\r\nSubject: =?UTF-8?Q?Exam_r=C3=A9sum=C3=A9?=\r\n"
           b"Date: Wed, 11 Nov 2026 09:00:00 +0000\r\n\r\nPlease   read\r\n this.")
    m = mail.parse_message(raw, b"", CFG)
    assert m["from"].startswith("José") and "résumé" in m["subject"] and m["unread"]
    assert m["preview"] == "Please read this." and m["date"] == "2026-11-11T09:00:00+00:00"
    assert m["score"] >= 3 and "uni sender" in m["reasons"]


def test_parse_message_html_only_preview(CFG):
    raw = (b"From: a@kcl.ac.uk\r\nSubject: Hi\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
           b"<html><style>p{}</style><p>Your <b>deadline</b> moved</p></html>")
    assert mail.parse_message(raw, b"\\Seen", CFG)["preview"] == "Your deadline moved"


def test_parse_message_drops_newsletter(CFG):
    raw = b"From: noreply@x.com\r\nList-Unsubscribe: <x>\r\nSubject: Sale\r\n\r\nhi"
    assert mail.parse_message(raw, b"\\Seen", CFG) is None
