# Tududi API notes

Derived from reading `chrisvel/tududi` source on GitHub (main branch), not from
a live instance — the HTML returned by `<TUDUDI_URL>/api-docs` was just the SPA
shell because `/api-docs` requires `Authorization` like every other API route;
an unauthenticated browser request falls through to the frontend's catch-all.
Once we have a token, `GET <TUDUDI_URL>/api-docs/swagger.json` should give the
same info in machine form — worth a quick sanity check against this doc.

## Base path & auth

- All API routes are mounted under `/api` by default (`backend/app.js`,
  `API_BASE_PATH`). So e.g. `GET <TUDUDI_URL>/api/tasks`.
- Auth: `Authorization: Bearer tt_<token>` header. Tokens starting with `tt_`
  are looked up via `apiTokenService.findValidTokenByValue` (bcrypt-hashed in
  the DB, so the server can't leak it back to us even on error). Confirms the
  paste's assumption — personal access tokens really are the mechanism, no
  separate OAuth dance needed unless OIDC is enabled on the instance.
- `/api/health`, `/api/login`, `/api/current_user` are the only unauthenticated
  paths; everything else requires a valid session or bearer token.

## Task identifiers

- Tasks have both a numeric `id` (autoincrement PK) and a string `uid` (15
  chars). Routes are written as `/api/task/:uid` but a middleware
  (`numericIdParam`) transparently accepts either form and resolves a numeric
  id to the real uid when the caller has access. Simplest for us: just use
  whatever `uid` field comes back from `GET /api/tasks` and always address
  tasks by that string — no need to ever send a numeric id.

## Listing tasks

`GET /api/tasks` — query params that matter for us:

- `status=active` — server-side filter that excludes `done`, `archived`, and
  `cancelled` (i.e. `not_started`, `in_progress`, `waiting`, `planned`). This
  is the right filter for "open tasks" — cleaner than fetching everything and
  filtering client-side.
- `limit` / `offset` — pagination; without them you get the default (20)
  unpaginated-feeling response, so we should pass explicit `limit`/`offset`
  and page through if the account has more than one page of open tasks.
- `order_by` — e.g. `due_date:asc` lets us stop paging early once we see a
  `due_date` past our notify window, instead of always fetching everything.

Each task in the response (per `backend/modules/tasks/core/serializers.js`)
includes at least:

- `uid` (string, stable identifier — use this for dedup keys and for
  `PATCH`/`DELETE` calls)
- `name` (display name — for a recurring *parent* task this gets replaced
  with "Daily"/"Weekly"/etc.; `original_name` holds the real text. We should
  notify using `original_name` if present, falling back to `name`.)
- `status` (integer, see enum below)
- `due_date` — **date-only string** (`YYYY-MM-DD` in the user's timezone), or
  `null`. Time is NOT embedded here.
- `due_has_time` (boolean) and `due_time` (`HH:mm` string or `null`) — if
  `due_has_time` is true, combine `due_date` + `due_time` for the real
  due-instant; if false, it's a whole-day due date and we should use our own
  configurable notify time (the paste's `09:00 local` idea still applies).
- `priority` (integer 0/1/2 — see enum below)
- `completed_at` (ISO datetime or `null`)
- `Project` (object with `uid`, `name`, ... or `null`), `Area` similarly
- `tags` (array)
- `recurrence_type` (`'none' | 'daily' | 'weekly' | 'monthly' | ...`) and
  `recurring_parent_uid`

## Status & priority enums (`backend/models/task.js`)

```
STATUS:   not_started=0, in_progress=1, done=2, archived=3,
          waiting=4, cancelled=5, planned=6
PRIORITY: low=0, medium=1, high=2
```

**Cancel has a clean, direct mapping**: there's a real `cancelled` status.
`Cancel` button → `PATCH /api/task/:uid` with `{"status": "cancelled"}` (the
update route's `parseStatus` helper accepts either the string name or the
integer — worth sending the string for readability, but confirm `cancelled`
string works like `done` does by testing once before relying on it).

## Completing a task

`PATCH /api/task/:uid` with `{"status": "done"}`:

- Server sets `completed_at = now()` automatically
  (`operations/completion.js`); we should not send `completed_at` ourselves.
- **Recurring tasks auto-advance on completion.** When a recurring task's
  status is set to `done`, the route computes the next occurrence
  (`planOccurrenceAdvance`) and — if there is a next occurrence — immediately
  resets the *same task record* back to `status: not_started` with
  `due_date` moved forward, rather than leaving it `done`. So after we mark a
  recurring task complete, the next `GET /api/tasks` poll will show the *same
  `uid`* again with a new `due_date`. Our dedup logic needs to key on
  `(uid, due_date)`, not just `uid`, so the next occurrence notifies again —
  this matches what the paste already assumed, good.
- A completed non-recurring task simply disappears from `status=active`
  results going forward.

## Deleting

`DELETE /api/task/:uid` — hard delete. Not needed for our "Cancel" button
since `cancelled` status covers that; keeping delete out of scope unless you
want it as a separate, more destructive action.

## Snooze (+1h)

No dedicated endpoint; same `PATCH /api/task/:uid`, just send an updated
`due_date` (and `due_time`/`due_has_time` if the task had a specific time).
Need to confirm the exact accepted input format for `due_date` on write (the
*response* format is a plain date string, but write-side helpers reference
ISO datetimes in places) — worth a one-off test call before wiring up Snooze.

## Open gap: "clear notification if completed elsewhere" is not achievable as described

The original paste assumed ntfy's `sequence_id` could be used to delete an
already-delivered notification from the phone if the task got completed via
the web UI first. I checked ntfy's docs: **`sequence_id`-based
replace/delete only works for scheduled (not-yet-delivered) messages.**
There is no API to delete or update a notification that has already reached
the phone. So that feature from the paste doesn't actually exist — we need a
different plan for "task got completed elsewhere, now the ntfy notification
is stale." Options to discuss with you:

1. Do nothing special — the stale notification just sits there; tapping
   Complete on an already-done task is a harmless no-op (sending
   `status: done` to an already-done task), so the only cost is a mildly
   confusing notification, not a broken one.
2. Next poll, if we see the task is no longer open, send a *new* ntfy message
   saying "already handled" so at least there's a visual cue (doesn't remove
   the old one, just adds a second message).
3. Drop this feature entirely for v1 and revisit later.

My instinct is (1) for v1 — it's the only option that requires no extra
mechanism, and the failure mode (tapping a stale button) is harmless given
how we're implementing Complete. Flagging for your decision rather than
picking silently since this changes a documented behavior from the paste.

## Confirmed against a real instance (2026-11-20, via scripts/verify-api.sh)

- `GET /api/tasks?status=active&limit=1` → `HTTP 200`, no subscription/entitlement
  gating in the way.
- `PATCH /api/task/:uid` with `{"status":"cancelled"}` → `HTTP 200`, response
  shows `"status":5`. The string form works, no need to send the integer.
- `PATCH /api/task/:uid` with `{"due_date":"<ISO datetime, UTC>"}` → `HTTP 200`,
  accepted. The returned `due_date` is the **local calendar date** for that
  instant in the user's timezone (not the UTC date) — matches
  `processDueDateForResponse`'s documented behavior above.
- **New finding — snooze needs `due_has_time` too.** Sending `due_date` alone
  did *not* set `due_has_time: true` or populate `due_time` — both stayed
  `false`/`null` after the write. So a "Snooze +1h" button that wants the
  task to actually carry a specific due time (not just a date) must also send
  `due_has_time: true` in the same PATCH, not just a new `due_date`. We
  haven't yet confirmed the exact field name/format for writing the time
  component itself (`due_time` as `"HH:mm"`, presumably, mirroring the
  read-side field) — worth one more quick test before relying on it, or just
  ship Snooze as "push due_date forward by 1h, accept that due_has_time may
  need a separate explicit test."
- **New finding — `priority` can be `null` in real data**, not only
  `0|1|2`. The model declares `defaultValue: 0`, but that's only applied on
  insert for new rows — existing rows (like the one we tested against) can
  have `priority: null`. Payload-building code must treat `null` as
  "no priority" rather than coercing it to `low`.
