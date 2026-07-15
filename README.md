# Strong Coast Ocean Calendar Reminders

Posts daily reminders for ocean observances, BC statutory holidays, and BC/transboundary
salmon & herring run info to Slack, via a GitHub Actions cron job + a Slack Incoming Webhook.
No servers to maintain — GitHub runs it for you, for free, on a public or private repo.

## What's in this folder

- `ocean_calendar.json` — the event calendar (45 events). Edit this file to add, remove, or
  adjust events; no code changes needed for date/note tweaks.
- `notify_slack.py` — standalone script (Python 3 standard library only, no pip installs
  needed). Resolves the calendar for today, and if anything is due (today or within its
  heads-up window — 3 days for most events, longer for a couple flagged ones), posts a
  formatted message to a Slack Incoming Webhook URL.
- `.github/workflows/ocean-calendar-reminders.yml` — GitHub Actions workflow that runs the
  script daily at 12:00 UTC (8am America/Toronto during EDT) and on-demand via the Actions tab.

## One-time setup

### 1. Create a Slack Incoming Webhook

This has to be done by someone with permission to add apps in your Slack workspace — it's
an OAuth-gated action, so it can't be scripted from outside Slack's own UI.

1. Go to https://api.slack.com/apps and click **Create New App** → **From scratch**.
2. Name it something like "Ocean Calendar Bot" and pick your workspace.
3. In the app's settings, open **Incoming Webhooks** (left sidebar) and toggle it **On**.
4. Click **Add New Webhook to Workspace**, choose the `#strong-coast-oceans-calendar`
   channel, and click **Allow**.
5. Copy the generated URL — it looks like
   `https://hooks.slack.com/services/T000/B000/XXXXXXXXXXXXXXXXXXXXXXXX`.
   Treat this URL as a secret: anyone who has it can post to that channel.

### 2. Create a GitHub repo for this

- Create a new repo (private is fine — this doesn't need to be public), or add this folder
  to an existing repo your team already uses.
- Commit all the files in this folder, preserving the `.github/workflows/` path exactly
  (GitHub only picks up workflows from that specific location).

### 3. Add the webhook URL as a repo secret

- In the repo: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
- Name: `SLACK_WEBHOOK_URL`
- Value: the URL you copied in step 1.
- Save.

### 4. Test it

- Go to the **Actions** tab → **Strong Coast Ocean Calendar Reminders** workflow →
  **Run workflow** (this uses the `workflow_dispatch` trigger, so you don't have to wait
  for the schedule). Check the run logs and your Slack channel.
- If nothing was due that day, the run will succeed but post nothing (by design) — you'll
  see "No ocean-related events or BC holidays within 3 days of ..." in the logs instead.

From then on it runs automatically every day at 12:00 UTC with no further action needed.

## Adjusting things later

- **Change the time it posts:** edit the `cron:` line in the workflow YAML
  (cron is UTC, minute hour day month weekday).
- **Change the heads-up window:** edit `notify_slack.py`'s `main()` — the `--notice-days`
  default is 3; a couple of events (the Adams River dominant-year festival) override it
  individually via `notice_days_override` in the calendar JSON.
- **Add/remove events:** edit `ocean_calendar.json` directly — see the `_meta` block at the
  top of the file for the date-rule formats (fixed date, nth weekday of month, days before
  Easter, etc.) and optional fields (`year_parity`, `recurrence_filter`, `notice_days_override`).
- **Test any date without waiting:** `python3 notify_slack.py --date 2026-06-08 --dry-run`
  prints the message without posting to Slack.
