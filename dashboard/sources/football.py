"""Team fixtures, results and league table from ESPN's public JSON (no key).
shortcut: unofficial API, shape may change; build.py isolates failures to the football card."""
from . import get_json

BASE = "https://site.api.espn.com/apis"


def _split(event, team_id):
    comps = event["competitions"][0]["competitors"]
    us = next(c for c in comps if c["id"] == team_id)
    them = next(c for c in comps if c["id"] != team_id)
    return us, them


def parse_schedule(played, upcoming, team_id):
    nxt = None
    pre = sorted((e for e in upcoming["events"] if e["competitions"][0]["status"]["type"]["state"] == "pre"),
                 key=lambda e: e["date"])
    if pre:
        us, them = _split(pre[0], team_id)
        nxt = {"opponent": them["team"]["displayName"], "date": pre[0]["date"], "home": us["homeAway"] == "home",
               "competition": pre[0].get("league", {}).get("abbreviation", "")}
    results = []
    post = sorted((e for e in played["events"] if e["competitions"][0]["status"]["type"]["state"] == "post"),
                  key=lambda e: e["date"], reverse=True)
    for e in post[:5]:
        us, them = _split(e, team_id)
        a, b = int(us["score"]["value"]), int(them["score"]["value"])
        results.append({"date": e["date"], "opponent": them["team"]["displayName"], "home": us["homeAway"] == "home",
                        "score": f"{a}-{b}", "outcome": "W" if a > b else "L" if a < b else "D"})
    return {"next": nxt, "results": results}


def parse_table(raw, team_id):
    rows = []
    for e in raw["children"][0]["standings"]["entries"]:
        s = {x["name"]: x.get("value") for x in e["stats"]}
        rows.append({"pos": int(s["rank"]), "team": e["team"]["displayName"], "played": int(s["gamesPlayed"]),
                     "gd": int(s["pointDifferential"]), "points": int(s["points"]), "is_team": e["team"]["id"] == team_id})
    return sorted(rows, key=lambda r: r["pos"])


def fetch(cfg):
    f = cfg["football"]
    sched = f"{BASE}/site/v2/sports/soccer/{f['league']}/teams/{f['team_id']}/schedule"
    out = parse_schedule(get_json(sched), get_json(sched + "?fixture=true"), f["team_id"])
    out["table"] = parse_table(get_json(f"{BASE}/v2/sports/soccer/{f['league']}/standings"), f["team_id"])
    return out
