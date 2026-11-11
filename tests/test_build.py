import json
from datetime import datetime
from zoneinfo import ZoneInfo
import build
from dashboard.crypto import decrypt

NOW = datetime(2026, 11, 11, 5, 30, tzinfo=ZoneInfo("UTC"))
W = {"hourly": [{"time": "2026-11-11T%02d:00" % i, "temp": 8, "feels": 6, "rain": 0, "wind": 5, "code": 3} for i in range(24)],
     "daily": []}
EV = [{"title": "Essay due", "start": "2026-11-11T10:00:00+00:00", "end": "2026-11-11T11:00:00+00:00",
       "all_day": False, "calendar": "Uni", "location": ""}]

def boom():
    raise RuntimeError("boom")


def test_failing_source_isolated(CFG):
    data = build.assemble(CFG, {"events": lambda: EV, "emails": boom, "weather": lambda: W, "football": boom}, NOW)
    assert data["emails"] == {"error": "RuntimeError: boom"} and data["football"] == {"error": "RuntimeError: boom"}
    assert data["wear"] == {"text": "Jacket or jumper"} and data["gaps"][0]["start"].startswith("2026-11-11T08:00")
    assert data["deadlines"][0]["title"] == "Essay due" and data["generated"] == NOW.isoformat()


def test_deadlines_tolerate_errored_inputs(CFG):
    data = build.assemble(CFG, {"events": boom, "emails": boom, "weather": boom, "football": boom}, NOW)
    assert data["deadlines"] == [] and data["wear"] is None and data["gaps"] == []


def test_error_message_never_contains_password(CFG):
    def leak():
        raise RuntimeError("login failed for hunter2-secret")
    data = build.assemble(CFG, {"events": leak, "emails": boom, "weather": boom, "football": boom}, NOW, secret="hunter2-secret")
    assert "hunter2-secret" not in json.dumps(data)


def test_main_exit_code_when_both_icloud_fail(CFG, tmp_path, monkeypatch):
    monkeypatch.setenv("DASHBOARD_PASSPHRASE", "pw")
    monkeypatch.delenv("ICLOUD_EMAIL", raising=False)
    monkeypatch.setattr(build.weather, "fetch", lambda c: W)
    monkeypatch.setattr(build.football, "fetch", lambda c: {"next": None, "results": [], "table": []})
    out = tmp_path / "data.enc"
    assert build.main(out) == 1
    data = decrypt(json.loads(out.read_text()), "pw")
    assert data["events"] == {"error": "missing credentials"} and data["wear"]


def test_main_refuses_without_passphrase(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHBOARD_PASSPHRASE", raising=False)
    assert build.main(tmp_path / "data.enc") == 2 and not (tmp_path / "data.enc").exists()


def test_gaps_include_multi_day_timed_event_overlapping_today(CFG):
    span = [{"title": "Conference", "start": "2026-11-10T09:00:00+00:00", "end": "2026-11-11T17:00:00+00:00",
             "all_day": False, "calendar": "Uni", "location": ""}]
    data = build.assemble(CFG, {"events": lambda: span, "emails": boom, "weather": boom, "football": boom}, NOW)
    assert [(g["start"][11:16], g["end"][11:16]) for g in data["gaps"]] == [("17:00", "22:00")]


def test_redaction_survives_truncation(CFG):
    secret = "abcd-efgh-ijkl-mnop"
    def leak():
        raise RuntimeError("x" * 180 + secret)
    data = build.assemble(CFG, {"events": leak, "emails": boom, "weather": boom, "football": boom}, NOW, secret=secret)
    assert "abcd-e" not in data["events"]["error"]
