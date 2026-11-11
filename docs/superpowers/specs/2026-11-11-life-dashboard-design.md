# Life Dashboard — Design

Date: 2026-11-11
Status: awaiting review

## Goal

A personal dashboard Ollie opens on phone or laptop each morning. It shows the day's
calendar, deadlines, emails that need attention, London weather with what to wear, and
Chelsea news. It refreshes itself daily in the cloud. The only accounts it connects to
are iCloud Mail and iCloud Calendar.

Success = opening the page at 7am shows today's real events, the right flagged emails,
an accurate weather/clothing line, and the next Chelsea match — with no manual step.

## Decisions (agreed)

| Topic | Decision |
|---|---|
| Hosting | GitHub Pages, data encrypted with a passphrase, decrypted in the browser |
| Refresh | GitHub Actions, daily 05:30 UTC, plus manual `workflow_dispatch` |
| Calendar | iCloud CalDAV, all calendars, today + next 7 days, recurrences expanded |
| Email | iCloud IMAP, read-only, INBOX, last 3 days, rule-based scoring |
| Deadlines | Calendar events with deadline keywords + dates found in high-scoring emails |
| Football | Chelsea (Premier League) via ESPN public JSON, no key |
| Weather | London via Open-Meteo, no key |
| Auth | iCloud app-specific password, stored only as a GitHub Actions secret |

## Architecture

```
GitHub Actions (cron 05:30 UTC)
  └─ build.py
       ├─ sources/calendar.py  → events[]        (CalDAV)
       ├─ sources/mail.py      → emails[]        (IMAP)
       ├─ sources/weather.py   → weather{}       (Open-Meteo)
       ├─ sources/football.py  → football{}      (ESPN)
       ├─ derive: deadlines[], wear{}, free gaps
       └─ encrypt JSON → site/data.enc
  └─ deploy site/ to GitHub Pages

Browser: site/index.html
  passphrase → PBKDF2 → AES-GCM decrypt data.enc → render tabs
```

Each source is a function `fetch(config) -> data`. `build.py` calls each in a
`try`; a failure stores `{"error": "<message>"}` for that section and the build
continues. If **both** iCloud sources fail, the workflow exits non-zero so GitHub emails
the failure (the site is still deployed with whatever loaded).

## Sources

### Calendar (`caldav`, `icalendar`, `recurring-ical-events`)
- Connect to `https://caldav.icloud.com` with Apple ID email + app-specific password.
- For every calendar, expand events in [today 00:00, today+8 00:00) Europe/London.
- Output per event: `title, start, end, all_day, calendar, location`.

### Email (stdlib `imaplib`, `email`)
- `imap.mail.me.com:993`, `SELECT INBOX` readonly, `SEARCH SINCE <3 days ago>`.
- Fetch headers only plus the first ~300 chars of text body (`BODY.PEEK`, never marks read).
- Score (keep if score ≥ 3):
  - +3 sender domain ends in a uni domain (configured, e.g. `.ac.uk`)
  - +2 unread
  - +2 per keyword in subject (deadline, due, urgent, action required, reminder,
    payment, overdue, interview, offer, submission, exam, invoice), max +4
  - +1 per keyword in preview, max +2
  - −4 has `List-Unsubscribe` header or sender matches `noreply|no-reply|newsletter|marketing`
- Output per email: `from, subject, date, preview, unread, score, reasons[]`. Top 15 by score.

### Weather (Open-Meteo)
- London lat 51.5072, lon −0.1276, timezone Europe/London.
- Hourly: temperature, apparent temperature, precipitation probability, wind speed, weather code.
- Daily: min/max, sunrise, sunset, precipitation probability max.

### Football (ESPN `site.api.espn.com`, league `eng.1`, Chelsea team id 363)
- Team schedule → next fixture (opponent, date, home/away, competition) + last 5 results.
- Standings → full table, Chelsea row highlighted.
- If ESPN changes shape, the football card shows "couldn't load"; nothing else is affected.

## Derived data

- **Deadlines**: events whose title matches `deadline|due|submit|submission|hand.?in|exam`
  (case-insensitive), plus emails with score ≥ 5 whose subject/preview contains a date
  parseable as within the next 30 days. Output `title, due, source, days_left`, sorted by due.
- **What to wear**: from 08:00–20:00 hourly data:
  - feels-like min < 5 → "Heavy coat, layers"; < 12 → "Jacket or jumper"; < 18 → "Light layer"; else "T-shirt weather"
  - any hour precip prob ≥ 50 → append "+ umbrella (rain from HH:00)"
  - wind ≥ 30 km/h → append "+ windproof"
- **Free gaps**: gaps ≥ 60 min between timed events, 08:00–22:00 today.

## Encryption

- `build.py`: random 16-byte salt, 12-byte IV, PBKDF2-HMAC-SHA256 600,000 iterations →
  256-bit key, AES-GCM (`cryptography` package). Write `data.enc` as JSON
  `{salt, iv, ct}` base64.
- `index.html`: same derivation with WebCrypto `SubtleCrypto`. Passphrase optionally
  remembered in `localStorage` (checkbox, per device). Wrong passphrase → clear error.
- Repo can be public: only ciphertext is published. Security rests on passphrase
  strength — spec requires 4+ random words.

## Page (`site/index.html`, single file, no build step)

Tabs:
1. **Today** — date + last-updated time; weather card with what-to-wear line and
   sunrise/sunset; timeline of today's events with free gaps; deadlines due ≤ 7 days;
   flagged emails (top 5); next Chelsea match.
2. **Week** — 7 day columns (stacked on phone) with events per day; deadlines marked.
3. **Inbox** — all flagged emails with score reasons.
4. **Football** — next fixture, last 5 results, league table.

Responsive down to 375 px, light/dark via `prefers-color-scheme`, keyboard-accessible
tabs. A section with `error` shows "Couldn't load <source>" instead of its content.

## Config

`config.json` (committed, no secrets): location, team id, uni domains, keywords,
timezone. Secrets in GitHub Actions: `ICLOUD_EMAIL`, `ICLOUD_APP_PASSWORD`,
`DASHBOARD_PASSPHRASE`.

## Testing

- `tests/test_rules.py`: email scoring, what-to-wear, deadline keyword matching, free gaps.
- `tests/test_crypto.py`: encrypt in Python → decrypt in Python round-trip; a fixed
  vector also checked in the browser by opening the page locally.
- One manual end-to-end run via `workflow_dispatch` with real accounts.

## Out of scope

AI summaries, other teams/leagues, news, to-do lists, push notifications, writing back
to calendar or mail.

## User actions required

1. Create an app-specific password at appleid.apple.com.
2. Add the three secrets to the GitHub repo.
3. Choose the passphrase.
