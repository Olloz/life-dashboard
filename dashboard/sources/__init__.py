import json, urllib.request


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "life-dashboard"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)
