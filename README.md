# Life Dashboard

A private morning dashboard: calendar, deadlines, emails that need you, London weather with
what to wear, and Chelsea. Rebuilt every day at 05:30 UTC by GitHub Actions and published to
GitHub Pages. Everything on the site is encrypted with your passphrase.

## One-time setup

1. **App-specific password**: go to <https://account.apple.com> → Sign-In and Security →
   App-Specific Passwords → generate one called "Life Dashboard".
2. **Secrets**: run these in this folder (each prompts for the value, so nothing lands in your
   shell history):
   ```bash
   gh secret set ICLOUD_EMAIL
   gh secret set ICLOUD_APP_PASSWORD
   gh secret set DASHBOARD_PASSPHRASE
   ```
   Use 4 or more random words for the passphrase. The encrypted data is public, so the
   passphrase is what keeps it private.
3. **First run**: `gh workflow run daily.yml`, then open the Pages URL and unlock.

## Changing things

Edit `config.json`: location, team (`team_id` from ESPN), uni email domains, keywords that flag
an email, and what counts as a deadline.

## Local development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest
.venv/bin/python scripts/sample_data.py      # sample data, passphrase "test"
python3 -m http.server 8765 -d site          # open http://localhost:8765
```

## If the daily update stops

GitHub pauses scheduled workflows in a public repo after 60 days with no commits, and emails you
first. Re-enable it from the repo's Actions tab, or push any small change.
