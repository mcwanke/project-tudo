from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import Config
from .habit_logic import is_habit_measurable

SHORT_RECURRENCE = {"daily", "weekly"}


def compute_recurrence_window_end(
    task: dict, recurrence_type: str, tz: ZoneInfo
) -> datetime | None:
    """End of the window a short-cycle (daily/weekly) occurrence owns.

    Past this instant, resending about this occurrence is abandoned in
    favor of whatever the next occurrence turns out to be.
    """
    due_date = task.get("due_date")
    if not due_date:
        return None
    day = date.fromisoformat(due_date)
    start = datetime.combine(day, time(0, 0), tzinfo=tz)
    days = 1 if recurrence_type == "daily" else 7
    return start + timedelta(days=days)


def resolve_task_policy(task: dict, config: Config) -> dict | None:
    if task.get("due_date") is None:
        return None  # shopping-list-style items never notify

    priority = task.get("priority")  # 0/1/2 or None
    recurrence_type = task.get("recurrence_type") or "none"
    short_recurrence = recurrence_type in SHORT_RECURRENCE
    window_end = (
        compute_recurrence_window_end(task, recurrence_type, config.timezone)
        if short_recurrence
        else None
    )

    if priority == 2:  # high
        policy: dict = {
            "kind": "interval",
            "minutes": config.high_priority_interval_minutes,
        }
    elif priority == 1:  # medium
        policy = {"kind": "daily_slots", "slots": config.medium_priority_slots}
    elif short_recurrence:
        policy = {"kind": "one_shot"}
    else:
        policy = {"kind": "daily_slots", "slots": [config.notify_time]}

    policy["window_end"] = window_end
    return policy


def resolve_habit_policy(habit: dict, config: Config) -> dict:
    # Priority is intentionally ignored for habits.
    if is_habit_measurable(habit):
        return {
            "kind": "interval",
            "minutes": config.habit_unit_remind_interval_minutes,
            "window_end": None,
        }
    return {"kind": "one_shot", "window_end": None}


def occurrence_key_for_task(task: dict) -> str:
    return f"{task.get('due_date')}|{task.get('due_time') or ''}"


def occurrence_key_for_habit(habit: dict) -> str:
    progress = habit.get("habit_progress") or {}
    return str(progress.get("period_start") or "")


def latest_slot_instant(slots: list[time], now: datetime, tz: ZoneInfo) -> datetime:
    """The most recent configured daily slot-instant at or before `now`."""
    today = now.astimezone(tz).date()
    candidates = [datetime.combine(today, s, tzinfo=tz) for s in slots]
    candidates += [
        datetime.combine(today - timedelta(days=1), s, tzinfo=tz) for s in slots
    ]
    past = [c for c in candidates if c <= now]
    return max(past) if past else min(candidates)


def should_notify(
    policy: dict | None,
    last_notified_at: datetime | None,
    now: datetime,
    *,
    tz: ZoneInfo,
) -> bool:
    if policy is None:
        return False

    window_end = policy.get("window_end")
    if window_end is not None and now >= window_end:
        return False  # occurrence abandoned in favor of the next one

    if last_notified_at is None:
        return True

    kind = policy["kind"]
    if kind == "one_shot":
        return False
    if kind == "daily_slots":
        latest_slot = latest_slot_instant(policy["slots"], now, tz)
        return last_notified_at < latest_slot <= now
    if kind == "interval":
        return now >= last_notified_at + timedelta(minutes=policy["minutes"])
    raise ValueError(f"unknown policy kind: {kind}")
