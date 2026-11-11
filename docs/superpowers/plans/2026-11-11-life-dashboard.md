# Life Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily-refreshed, passphrase-encrypted personal dashboard (calendar, deadlines, flagged email, London weather + what to wear, Chelsea) hosted on GitHub Pages.

**Architecture:** A Python `build.py` run by GitHub Actions calls four source modules (CalDAV, IMAP, Open-Meteo, ESPN), derives deadlines/wear/free gaps with pure functions in `rules.py`, encrypts the JSON with AES-GCM, and deploys `site/` to Pages. A single `site/index.html` decrypts with WebCrypto and renders four tabs.

**Tech Stack:** Python 3.12 (Actions) / 3.14 local; `caldav`, `icalendar`, `recurring-ical-events`, `cryptography`, `pytest`; stdlib `imaplib`, `email`, `urllib`, `zoneinfo`; vanilla HTML/CSS/JS.

**Spec:** `docs/superpowers/specs/2026-11-11-life-dashboard-design.md`

## Global Constraints

- Timezone for all display and day boundaries: `Europe/London`.
- Only iCloud requires credentials; weather and football use no keys.
- IMAP access is read-only: `SELECT INBOX` with `readonly=True`, fetch with `BODY.PEEK`.
- Email kept only if score ≥ 3; at most 15 emails, sorted by score desc then date desc.
- Encryption: PBKDF2-HMAC-SHA256, 600,000 iterations, 16-byte salt, 12-byte IV, AES-256-GCM; file `site/data.enc` = JSON `{"salt","iv","ct"}` base64.
- Secrets env vars: `ICLOUD_EMAIL`, `ICLOUD_APP_PASSWORD`, `DASHBOARD_PASSPHRASE`. Never committed, never logged.
- Only `site/index.html` and `site/data.enc` are published; plaintext JSON never written into `site/`.
- Page works at 375 px wide, light + dark, keyboard-operable tabs.
- Cron `30 5 * * *` UTC plus `workflow_dispatch`.

## Review Focus

1. **Event stored in UTC or another timezone** → shown at London local time and on the correct day. Test in Task 4.
2. **All-day / multi-day events** → appear on every day they cover, not counted as busy time for free gaps. Tests in Tasks 1 and 4.
3. **Encoded email headers** (`=?UTF-8?B?...?=`, non-ASCII names) → decoded to readable text. Test in Task 4.
4. **Wrong or empty passphrase** → page shows "Wrong passphrase", no crash; remembered passphrase that is now wrong is cleared. Checked in Task 6.
5. **Empty day / empty inbox / one source failing** → friendly empty or "Couldn't load" state, rest renders. Tests in Task 5, checked in Task 6.

---

## File Structure

```
config.json                  non-secret settings
requirements.txt
dashboard/__init__.py
dashboard/rules.py           pure: score_email, what_to_wear, is_deadline, free_gaps, find_deadlines
dashboard/crypto.py          encrypt(obj, passphrase) / decrypt(blob, passphrase)
dashboard/sources/weather.py fetch(cfg) -> dict ; parse(raw) -> dict
dashboard/sources/football.py fetch(cfg) -> dict ; parse_schedule(raw, team_id), parse_table(raw, team_id)
dashboard/sources/calendar.py fetch(cfg, user, pw) -> list ; normalise(component, tz) -> dict
dashboard/sources/mail.py    fetch(cfg, user, pw) -> list ; parse_message(raw_bytes, flags) -> dict
build.py                     orchestrates, writes site/data.enc
site/index.html              UI
tests/test_rules.py, test_crypto.py, test_sources.py, test_build.py
.github/workflows/daily.yml
.gitignore                   .venv, __pycache__, data.json, .env
```

## Data contract (`build.py` output, before encryption)

```json
{
  "generated": "2026-11-11T05:30:00+00:00",
  "events":   [{"title","start","end","all_day","calendar","location"}] | {"error"},
  "emails":   [{"from","subject","date","preview","unread","score","reasons"}] | {"error"},
  "weather":  {"hourly":[{"time","temp","feels","rain","wind","code"}],
               "daily":[{"date","min","max","sunrise","sunset","rain"}]} | {"error"},
  "football": {"next":{"opponent","date","home","competition"}|null,
               "results":[{"date","opponent","home","score","outcome"}],
               "table":[{"pos","team","played","gd","points","is_team"}]} | {"error"},
  "deadlines":[{"title","due","source","days_left"}],
  "wear":     {"text"} | null,
  "gaps":     [{"start","end","minutes"}]
}
```
Datetimes are ISO 8601 strings with offset; all-day dates are `YYYY-MM-DD`.

---

### Task 1: Project scaffold + pure rules

**Files:**
- Create: `config.json`, `requirements.txt`, `.gitignore`, `dashboard/__init__.py`, `dashboard/rules.py`
- Test: `tests/test_rules.py`

**Interfaces:**
- Produces:
  - `score_email(sender: str, subject: str, preview: str, unread: bool, has_unsubscribe: bool, cfg: dict) -> tuple[int, list[str]]`
  - `what_to_wear(hourly: list[dict], day: str) -> dict | None` — uses hours 08–20 of `day`; returns `{"text": str}`
  - `is_deadline(title: str, cfg: dict) -> bool`
  - `free_gaps(events: list[dict], day: str, tz: str) -> list[dict]` — `{"start","end","minutes"}`
  - `find_deadlines(events: list[dict], emails: list[dict], today: date, cfg: dict) -> list[dict]`

- [ ] **Step 1: `git init`, write `config.json`**

```json
{
  "timezone": "Europe/London",
  "location": {"name": "London", "lat": 51.5072, "lon": -0.1276},
  "football": {"league": "eng.1", "team_id": "363", "team_name": "Chelsea"},
  "mail": {"days": 3, "min_score": 3, "max": 15,
           "uni_domains": [".ac.uk"],
           "keywords": ["deadline","due","urgent","action required","reminder","payment",
                        "overdue","interview","offer","submission","exam","invoice"],
           "noise": "noreply|no-reply|newsletter|marketing"},
  "deadline_pattern": "deadline|due|submit|submission|hand.?in|exam",
  "calendar_days": 8
}
```
`requirements.txt`: `caldav`, `icalendar`, `recurring-ical-events`, `cryptography`, `pytest`.

- [ ] **Step 2: Write failing tests in `tests/test_rules.py`**

```python
def test_uni_unread_deadline_scores_high():
    s, r = score_email("Tutor <a.b@kcl.ac.uk>", "Coursework deadline Friday", "", True, False, CFG)
    assert s == 3 + 2 + 2 and "uni sender" in r

def test_newsletter_penalised():
    s, _ = score_email("Shop <noreply@shop.com>", "Payment offer", "", True, True, CFG)
    assert s < 3

def test_subject_keyword_cap():
    s, _ = score_email("x@y.com", "urgent payment overdue invoice", "", False, False, CFG)
    assert s == 4

def test_wear_cold_rain():
    hourly = [h("2026-11-11T%02d:00" % i, feels=3, rain=60 if i >= 15 else 0, wind=10) for i in range(24)]
    assert what_to_wear(hourly, "2026-11-11")["text"] == "Heavy coat, layers + umbrella (rain from 15:00)"

def test_wear_warm_windy():
    hourly = [h("2026-11-11T%02d:00" % i, feels=20, rain=0, wind=35) for i in range(24)]
    assert what_to_wear(hourly, "2026-11-11")["text"] == "T-shirt weather + windproof"

def test_is_deadline():
    assert is_deadline("ML coursework DUE", CFG) and is_deadline("Hand-in essay", CFG)
    assert not is_deadline("Football training", CFG)

def test_free_gaps_ignores_all_day_and_short_gaps():
    ev = [allday("Holiday", "2026-11-11"), timed("10:00", "11:00"), timed("11:30", "12:00"), timed("15:00", "16:00")]
    gaps = free_gaps(ev, "2026-11-11", "Europe/London")
    assert [(g["start"][11:16], g["end"][11:16]) for g in gaps] == [("08:00","10:00"), ("12:00","15:00"), ("16:00","22:00")]

def test_free_gaps_empty_day():
    assert free_gaps([], "2026-11-11", "Europe/London")[0]["minutes"] == 840

def test_find_deadlines_from_events_sorted():
    d = find_deadlines([timed_on("2026-11-14", "Essay due"), timed_on("2026-11-12", "Exam")], [], date(2026,11,11), CFG)
    assert [x["title"] for x in d] == ["Exam", "Essay due"] and d[0]["days_left"] == 1
```
Helpers `h`, `allday`, `timed`, `timed_on` build dicts in the data-contract shape; `CFG` loads `config.json`.

- [ ] **Step 3: Run** `pytest tests/test_rules.py -v` → FAIL (import error).

- [ ] **Step 4: Implement `dashboard/rules.py`**

Score values from the spec: +3 uni domain (sender address ends with any `uni_domains`), +2 unread, +2 per subject keyword (cap +4), +1 per preview keyword (cap +2), −4 if `has_unsubscribe` or sender matches `noise`. Reasons strings: `"uni sender"`, `"unread"`, `"subject: <kw>"`, `"preview: <kw>"`, `"newsletter"`.
Wear thresholds use min feels-like over 08–20: `<5` "Heavy coat, layers", `<12` "Jacket or jumper", `<18` "Light layer", else "T-shirt weather"; append `" + umbrella (rain from HH:00)"` at first hour rain ≥ 50; append `" + windproof"` if any wind ≥ 30. Return `None` if no hours for that day.
Free gaps: window 08:00–22:00 local, ignore all-day, merge overlapping events, keep gaps ≥ 60 min.
`find_deadlines` emails rule: emails with score ≥ 5 whose subject+preview contain a date matching `\b(\d{1,2})(st|nd|rd|th)? (Jan|Feb|...|Dec)\w*` within the next 30 days (assume current year, roll to next year if past). `source` is `"calendar"` or `"email"`.

- [ ] **Step 5: Run** `pytest tests/test_rules.py -v` → all PASS.

- [ ] **Step 6: Commit** `feat: scaffold and rules`.

---

### Task 2: Encryption

**Files:** Create `dashboard/crypto.py`; Test `tests/test_crypto.py`

**Interfaces:**
- Produces: `encrypt(obj: dict, passphrase: str) -> dict` (`{"salt","iv","ct"}` base64 strings); `decrypt(blob: dict, passphrase: str) -> dict`

- [ ] **Step 1: Failing tests**

```python
def test_round_trip():
    assert decrypt(encrypt({"a": "é"}, "pw"), "pw") == {"a": "é"}

def test_wrong_passphrase_raises():
    with pytest.raises(Exception): decrypt(encrypt({"a": 1}, "pw"), "nope")

def test_fresh_salt_each_time():
    assert encrypt({}, "pw")["salt"] != encrypt({}, "pw")["salt"]
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** with `cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC` + `AESGCM`; plaintext is UTF-8 JSON; `ct` includes the GCM tag (WebCrypto expects tag appended — AESGCM already does this).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: AES-GCM encryption`.

---

### Task 3: Weather + football sources

**Files:** Create `dashboard/sources/__init__.py`, `weather.py`, `football.py`; Test `tests/test_sources.py`

**Interfaces:**
- Produces: `weather.fetch(cfg) -> dict`, `weather.parse(raw: dict) -> dict`; `football.fetch(cfg) -> dict`, `football.parse_schedule(raw: dict, team_id: str) -> dict` (`{"next","results"}`), `football.parse_table(raw: dict, team_id: str) -> list`
- Endpoints:
  - `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&timezone=Europe/London&forecast_days=7&hourly=temperature_2m,apparent_temperature,precipitation_probability,wind_speed_10m,weather_code&daily=temperature_2m_min,temperature_2m_max,sunrise,sunset,precipitation_probability_max`
  - `https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams/363/schedule` (results) and same with `?fixture=true` (upcoming)
  - `https://site.api.espn.com/apis/v2/sports/soccer/eng.1/standings`

- [ ] **Step 1: Failing tests** using small inline dicts shaped like each API's response:

```python
def test_weather_parse_zips_hourly():
    raw = {"hourly": {"time": ["2026-11-11T08:00"], "temperature_2m": [7.1], "apparent_temperature": [4.0],
                      "precipitation_probability": [20], "wind_speed_10m": [12], "weather_code": [3]},
           "daily": {"time": ["2026-11-11"], "temperature_2m_min": [5], "temperature_2m_max": [9],
                     "sunrise": ["2026-11-11T07:10"], "sunset": ["2026-11-11T16:20"], "precipitation_probability_max": [40]}}
    w = parse(raw)
    assert w["hourly"][0] == {"time": "2026-11-11T08:00", "temp": 7.1, "feels": 4.0, "rain": 20, "wind": 12, "code": 3}
    assert w["daily"][0]["sunset"] == "2026-11-11T16:20"

def test_parse_table_marks_team(): ...   # 2 rows, team id "363" → is_team True on that row only
def test_parse_schedule_next_and_results(): ...  # one completed event (score 2-1, home win) + one scheduled → next.opponent, results[0].outcome == "W"
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Fetch with `urllib.request` (timeout 20 s, User-Agent `life-dashboard`). Before writing parsers, `curl` each ESPN endpoint once and match the real JSON paths; fix test fixtures to that real shape. Last 5 results, newest first.
- [ ] **Step 4: Run** → PASS. Also run `python -c "from dashboard.sources import weather, football; import json; print(json.dumps(football.fetch(json.load(open('config.json')))['next']))"` → prints Chelsea's real next fixture.
- [ ] **Step 5: Commit** `feat: weather and football sources`.

---

### Task 4: Calendar + mail sources

**Files:** Create `dashboard/sources/calendar.py`, `dashboard/sources/mail.py`; Test append to `tests/test_sources.py`

**Interfaces:**
- Produces: `calendar.fetch(cfg, user: str, pw: str) -> list[dict]`; `calendar.normalise(component, tz: ZoneInfo) -> dict`; `mail.fetch(cfg, user: str, pw: str) -> list[dict]`; `mail.parse_message(raw: bytes, flags: bytes, cfg: dict) -> dict | None` (None when below min score)

- [ ] **Step 1: Failing tests**

```python
def test_normalise_utc_event_to_london():
    ev = vevent("Lecture", "20260715T090000Z", "20260715T100000Z")   # BST date
    assert normalise(ev, LONDON)["start"].startswith("2026-07-15T10:00")

def test_normalise_all_day_multi_day():
    n = normalise(vevent_date("Trip", "20261111", "20261114"), LONDON)
    assert n["all_day"] and n["start"] == "2026-11-11" and n["end"] == "2026-11-14"

def test_parse_message_decodes_utf8_headers_and_scores():
    raw = b"From: =?UTF-8?B?Sm9zw6k=?= <j@kcl.ac.uk>\r\nSubject: =?UTF-8?Q?Exam_r=C3=A9sum=C3=A9?=\r\nDate: Wed, 11 Nov 2026 09:00:00 +0000\r\n\r\nPlease read."
    m = parse_message(raw, b"", CFG)
    assert m["from"].startswith("José") and "résumé" in m["subject"] and m["unread"]

def test_parse_message_drops_newsletter():
    raw = b"From: noreply@x.com\r\nList-Unsubscribe: <x>\r\nSubject: Sale\r\n\r\nhi"
    assert parse_message(raw, b"\\Seen", CFG) is None
```
`vevent`/`vevent_date` build `icalendar.Event` objects.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Calendar: `caldav.DAVClient("https://caldav.icloud.com", username, password).principal().calendars()`; for each, `cal.search(start, end, event=True, expand=False)` then `recurring_ical_events.of(ical).between(start, end)`; skip calendars that raise (Reminders lists). Floating times are treated as London. Mail: `imaplib.IMAP4_SSL("imap.mail.me.com", 993)`, `select("INBOX", readonly=True)`, `search(None, "SINCE", "<dd-Mon-yyyy>")`, `fetch(ids, "(FLAGS BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.2000>)")`; preview = first 300 chars of the text part with whitespace collapsed and HTML tags stripped; headers decoded with `email.header.make_header(decode_header(...))`. Always `logout()` in `finally`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: iCloud calendar and mail sources`.

---

### Task 5: Build orchestration

**Files:** Create `build.py`; Test `tests/test_build.py`

**Interfaces:**
- Consumes: all source `fetch` functions, `rules.*`, `crypto.encrypt`
- Produces: `assemble(cfg: dict, sources: dict[str, Callable[[], Any]], now: datetime) -> dict` (data contract); `main() -> int` exit code; CLI `python build.py [--plain data.json]` writes plaintext for local debugging (gitignored, never under `site/`).

- [ ] **Step 1: Failing tests**

```python
def test_failing_source_isolated():
    data = assemble(CFG, {"events": lambda: [], "emails": boom, "weather": lambda: W, "football": boom}, NOW)
    assert data["emails"] == {"error": "boom"} and data["football"] == {"error": "boom"}
    assert data["wear"] is not None and data["gaps"]

def test_deadlines_tolerate_errored_inputs():
    data = assemble(CFG, {"events": boom, "emails": boom, "weather": boom, "football": boom}, NOW)
    assert data["deadlines"] == [] and data["wear"] is None

def test_main_exit_code_when_both_icloud_fail(monkeypatch, tmp_path): ...  # → 1, and site/data.enc still written
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Read secrets from env; missing secrets → both iCloud sources error with `"missing credentials"`. Error messages must not include the password (use `type(e).__name__ + ": " + str(e)` truncated to 200 chars, and strip any occurrence of the password string). Write `site/data.enc`.
- [ ] **Step 4: Run** `pytest -v` → all PASS.
- [ ] **Step 5: Commit** `feat: build orchestration`.

---

### Task 6: Dashboard page

**Files:** Create `site/index.html`; create `scripts/sample_data.py` (writes `site/data.enc` from a fixed sample dict, passphrase `test`)

**Interfaces:**
- Consumes: `site/data.enc` format from Task 2, data contract above.

Before writing, load the `frontend-design` and `artifact-design` guidance for visual direction (calm, information-dense, mobile-first; not a template look).

- [ ] **Step 1: Write `scripts/sample_data.py`** with realistic sample: 4 events today incl. one all-day, events across the week, 2 deadlines, 4 emails, real-shaped weather/football, plus a variant flag `--errors` that sets `emails` and `football` to `{"error": ...}`.
- [ ] **Step 2: Implement `site/index.html`.** Lock screen (passphrase field, "Remember on this device" checkbox, Unlock button, error line). WebCrypto: `importKey('raw', pw)` → `deriveKey({name:'PBKDF2', salt, iterations:600000, hash:'SHA-256'}, ..., {name:'AES-GCM', length:256})` → `decrypt`. Tabs with `role="tablist"`, arrow-key navigation. Today / Week / Inbox / Football per spec. Times displayed with `Intl.DateTimeFormat('en-GB', {timeZone:'Europe/London'})`. Weather code → short label + emoji map. Header shows "Updated HH:MM" and a stale warning if `generated` is > 26 h old.
- [ ] **Step 3: Verify in browser.** `python scripts/sample_data.py && python -m http.server -d site 8000`, open in the browser pane:
  - wrong passphrase → "Wrong passphrase", page still usable; `test` → dashboard renders all four tabs
  - remembered wrong passphrase in localStorage → cleared, lock screen shown
  - `--errors` sample → Inbox and Football cards show "Couldn't load …", other cards fine
  - 375 px viewport: no horizontal scroll; dark scheme readable; Tab/arrow keys move between tabs
- [ ] **Step 4: Commit** `feat: dashboard page`.

---

### Task 7: Cloud deploy

**Files:** Create `.github/workflows/daily.yml`, `README.md` (setup steps only)

- [ ] **Step 1: Write workflow.** Triggers: `schedule: cron '30 5 * * *'`, `workflow_dispatch`. Permissions `pages: write`, `id-token: write`, `contents: read`. Job: checkout → setup-python 3.12 → `pip install -r requirements.txt` → `pytest -q` → `python build.py` (env from secrets; `continue-on-error: false`, but deploy step runs `if: always()` when `site/data.enc` exists) → `actions/upload-pages-artifact` (path `site`) → `actions/deploy-pages`.
- [ ] **Step 2: Create repo** — ask user public vs private, then `gh repo create <name> --source . --push`; enable Pages with source "GitHub Actions" (`gh api -X POST repos/{owner}/{repo}/pages -f build_type=workflow`).
- [ ] **Step 3: User adds secrets** `ICLOUD_EMAIL`, `ICLOUD_APP_PASSWORD`, `DASHBOARD_PASSPHRASE` (README gives exact `gh secret set` commands for them to run). Claude never handles these values.
- [ ] **Step 4: Verify.** `gh workflow run daily.yml`, then `gh run watch` → success; open the Pages URL, unlock with the passphrase, confirm today's real events and emails appear.
- [ ] **Step 5: Commit** `ci: daily build and deploy`.
