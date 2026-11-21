# project-tudo

*A docker container to poll a Tududi instance and push notifications to a
Ntfy instance. Basically a better android notifications system than using
the Tasks.org app with Caldav.*

Polls a self-hosted [Tududi](https://github.com/chrisvel/tududi) instance for
due tasks and habits, and sends [ntfy](https://ntfy.sh) push notifications
with action buttons (Complete / Cancel for tasks, Complete / Skip for
habits) that call the Tududi API directly from your phone when tapped.

See [docs/tududi-api-notes.md](docs/tududi-api-notes.md) for the API details
this was built against, and the plan file this was implemented from for the
full reminder-policy design.

## How it works

Every `POLL_INTERVAL` seconds, the service:

1. Fetches your open tasks, habits, and projects from Tududi.
2. Drops anything tagged (directly, or via its project) with one of
   `SKIP_TAGS`.
3. Drops anything not due yet (tasks with no due date are *never* due).
4. Figures out how often this specific item should be re-notified (see the
   policy table below) and checks whether that's elapsed since it was last
   notified.
5. Sends an ntfy notification whose buttons already contain the exact
   Tududi API call (URL, token, method, body) to run when tapped. The
   service itself never sees the tap — the ntfy Android app fires the
   request directly.

### Reminder cadence

| Item | Cadence | Stops when |
|---|---|---|
| Task, `low`/no priority, daily/weekly recurrence | once, never repeats | n/a |
| Task, `low`/no priority, monthly/yearly/one-off | once per calendar day | `done`/`cancelled` |
| Task, `medium` priority | twice a day (`MEDIUM_PRIORITY_TIMES`) | same, but capped to that occurrence's own day/week window if the task is daily/weekly-recurring |
| Task, `high` priority | every `HIGH_PRIORITY_INTERVAL_MINUTES` | same window cap as medium |
| Habit, plain yes/no | once a day (`habit_reminder_time` or `NOTIFY_TIME`) | you complete or skip it |
| Habit, measurable (tracks a number) | every `HABIT_UNIT_REMIND_INTERVAL_MINUTES`, each Complete logs 1 unit | goal met, or skipped |

Habits ignore the `priority` field entirely, even though habits are stored
as regular Tududi tasks under the hood.

## Important limitations

- **The Tududi token is visible to anyone who can read your ntfy topic.**
  Each notification button embeds `Authorization: Bearer <token>` so the
  ntfy app can call Tududi directly. Use a private ntfy topic (ideally with
  `NTFY_AUTH` set) and a dedicated, revocable Tududi API token — not your
  main one.
- **Your phone needs network access to `TUDUDI_URL`** to actually complete
  the HTTP request when you tap a button. LAN-only Tududi won't work for
  button taps made away from home unless you have a VPN (Tailscale,
  WireGuard) or Tududi is reachable over the public internet.
- **There is no way to detect a dismissed/swiped-away notification.** ntfy
  doesn't expose that to publishers, so "stop nagging" only happens because
  the item actually left the open set in Tududi (you tapped a button, or
  completed it elsewhere) — not because you looked at your phone. Repeat
  reminders resend on a timer regardless of whether the previous one is
  still visible.

## Setup

```bash
cp .env.example .env
# fill in TUDUDI_URL, TUDUDI_TOKEN, NTFY_URL, NTFY_TOPIC, TIMEZONE, etc.
```

### Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .

set -a; source .env; set +a
python -m tudo_ntfy --dry-run --once   # prints payloads instead of sending, single cycle
python -m tudo_ntfy --once             # really sends, single cycle
python -m tudo_ntfy                    # runs forever on POLL_INTERVAL
```

### Run with Docker

```bash
docker compose up --build -d
docker compose logs -f
```

## Testing

```bash
.venv/bin/python -m pytest
```

Unit tests cover due-date/habit-due logic, the full reminder-policy table
(including window-cutoff edge cases), tag/project exclusion, the SQLite
dedup store, and ntfy payload construction — all against mocked HTTP, no
network required.

### Manual end-to-end test

1. In Tududi, create a task due in ~2 minutes with no recurrence.
2. Run `python -m tudo_ntfy --once` (or let the loop run) and confirm the
   notification arrives on your phone with Complete/Cancel buttons.
3. Tap **Complete** and confirm the task shows as done in Tududi's web UI,
   and that the notification clears.
4. Repeat for a habit: create one due today, confirm it notifies around its
   `habit_reminder_time` (or `NOTIFY_TIME` if unset), and that tapping
   Complete logs a check-in.
5. Tag a task (or its project) with one of your `SKIP_TAGS` and confirm it
   never notifies regardless of due date.

## `scripts/verify-api.sh`

A one-off script used during development to confirm assumptions about the
live Tududi API (not part of the running service — safe to delete once
you've confirmed your own instance behaves the same way documented in
`docs/tududi-api-notes.md`).
