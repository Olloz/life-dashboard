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
