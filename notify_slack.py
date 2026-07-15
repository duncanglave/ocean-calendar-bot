#!/usr/bin/env python3
"""
Strong Coast ocean-events calendar -> Slack Incoming Webhook notifier.

Standalone (stdlib only, no pip install needed) so it runs unmodified inside
GitHub Actions. Resolves ocean_calendar.json to concrete dates for today and
posts a formatted reminder to a Slack Incoming Webhook URL if anything is
due today or within its heads-up window.

Usage:
    SLACK_WEBHOOK_URL=https://hooks.slack.com/services/... python3 notify_slack.py
    python3 notify_slack.py --date 2026-06-08 --dry-run   # print instead of posting, for testing
"""
import json
import os
import sys
import argparse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    from datetime import datetime
    TODAY_TZ = datetime.now(ZoneInfo("America/Toronto")).date()
except Exception:
    TODAY_TZ = date.today()

CALENDAR_PATH = Path(__file__).parent / "ocean_calendar.json"


def easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm for the date of Easter Sunday."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: Monday=0 ... Sunday=6. n: 1-indexed occurrence."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    d += timedelta(days=offset)
    d += timedelta(weeks=n - 1)
    return d


def last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    d = next_month_first - timedelta(days=1)
    offset = (d.weekday() - weekday) % 7
    return d - timedelta(days=offset)


def before_fixed_date(year: int, weekday: int, before_month: int, before_day: int) -> date:
    target = date(year, before_month, before_day)
    delta = (target.weekday() - weekday) % 7
    if delta == 0:
        delta = 7
    return target - timedelta(days=delta)


def resolve(event: dict, year: int) -> date:
    t = event["date_type"]
    p = event["params"]
    if t == "fixed":
        return date(year, p["month"], p["day"])
    if t == "nth_weekday":
        return nth_weekday_of_month(year, p["month"], p["weekday"], p["n"])
    if t == "last_weekday_of_month":
        return last_weekday_of_month(year, p["month"], p["weekday"])
    if t == "before_fixed_date":
        return before_fixed_date(year, p["weekday"], p["before_month"], p["before_day"])
    if t == "before_easter":
        return easter_sunday(year) + timedelta(days=p["offset_days"])
    raise ValueError(f"Unknown date_type: {t}")


def year_allowed(event: dict, year: int) -> bool:
    parity = event.get("year_parity")
    if parity == "odd" and year % 2 == 0:
        return False
    if parity == "even" and year % 2 != 0:
        return False
    cycle = event.get("recurrence_filter")
    if cycle and cycle.get("type") == "cycle":
        if (year - cycle["start_year"]) % cycle["interval"] != 0:
            return False
    return True


def find_matches(today: date, notice_days: int):
    data = json.loads(CALENDAR_PATH.read_text())
    matches = []
    for event in data["events"]:
        candidate_years = [y for y in (today.year, today.year + 1) if year_allowed(event, y)]
        if not candidate_years:
            continue
        candidates = [resolve(event, y) for y in candidate_years]
        best = min(candidates, key=lambda d: abs((d - today).days))
        days_until = (best - today).days
        window = event.get("notice_days_override", notice_days)
        if 0 <= days_until <= window:
            matches.append({
                "name": event["name"],
                "category": event["category"],
                "note": event.get("note", ""),
                "date": best.isoformat(),
                "days_until": days_until,
                "status": "today" if days_until == 0 else "upcoming",
            })
    matches.sort(key=lambda m: m["days_until"])
    return matches


def format_slack_message(today: date, matches: list) -> str:
    CATEGORY_EMOJI = {"ocean": "\U0001F30A", "bc_holiday": "\U0001F1E8\U0001F1E6", "bc_ocean": "\U0001F30A", "salmon_herring": "\U0001F41F"}
    lines = [f"*Ocean & BC calendar — {today.strftime('%A, %B %-d, %Y')}*"]
    for m in matches:
        emoji = CATEGORY_EMOJI.get(m["category"], "\U0001F4C5")
        when = "*today*" if m["status"] == "today" else f"in *{m['days_until']} day(s)*, on {m['date']}"
        lines.append(f"{emoji} *{m['name']}* — {when}\n> {m['note']}")
    return "\n\n".join(lines)


def post_to_slack(webhook_url: str, text: str) -> None:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        if resp.status != 200 or body.strip() != "ok":
            raise RuntimeError(f"Slack webhook returned status {resp.status}: {body}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Simulate this date (YYYY-MM-DD) instead of today")
    parser.add_argument("--notice-days", type=int, default=3, help="Heads-up window in days (default 3)")
    parser.add_argument("--dry-run", action="store_true", help="Print the message instead of posting to Slack")
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else TODAY_TZ
    matches = find_matches(today, args.notice_days)

    if not matches:
        print(f"No ocean-related events or BC holidays within {args.notice_days} days of {today.isoformat()}. Nothing posted.")
        return

    message = format_slack_message(today, matches)
    print(message)

    if args.dry_run:
        print("\n[dry-run] Not posting to Slack.")
        return

    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("ERROR: SLACK_WEBHOOK_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    post_to_slack(webhook_url, message)
    print("\nPosted to Slack successfully.")


if __name__ == "__main__":
    main()
