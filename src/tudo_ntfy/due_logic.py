from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def compute_due_instant(
    task: dict, *, notify_time: time, tz: ZoneInfo
) -> datetime | None:
    """The instant a task becomes due, or None if it has no due_date at all.

    due_has_time tasks use their own due_time; whole-day tasks fall back to
    the configured notify_time.
    """
    due_date = task.get("due_date")
    if not due_date:
        return None

    day = date.fromisoformat(due_date)
    due_time = task.get("due_time")
    if task.get("due_has_time") and due_time:
        hour, minute = due_time.split(":")
        instant_time = time(int(hour), int(minute))
    else:
        instant_time = notify_time

    return datetime.combine(day, instant_time, tzinfo=tz)


def is_task_due(
    task: dict,
    now: datetime,
    *,
    lead_minutes: int,
    notify_time: time,
    tz: ZoneInfo,
) -> bool:
    """Whether a task is due now or overdue, honoring an optional lead time.

    A task with no due_date is never due -- this is what keeps undated
    (shopping-list-style) tasks from ever notifying.
    """
    due_instant = compute_due_instant(task, notify_time=notify_time, tz=tz)
    if due_instant is None:
        return False
    return now >= due_instant - timedelta(minutes=lead_minutes)
