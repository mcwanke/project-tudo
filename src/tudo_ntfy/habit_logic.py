from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


def is_habit_measurable(habit: dict) -> bool:
    """Mirrors habitEngine.js::normalizeConfig's `measurable` derivation."""
    polarity = habit.get("habit_polarity")
    target = habit.get("habit_target_value")
    return (
        polarity == "build"
        and isinstance(target, (int, float))
        and not isinstance(target, bool)
        and target > 0
    )


def is_habit_open(habit: dict) -> bool:
    """Day-level gate: is this habit still awaiting a check-in today."""
    progress = habit.get("habit_progress") or {}
    return bool(progress.get("scheduled_today")) and not progress.get(
        "met"
    ) and not progress.get("skipped")


def habit_reminder_due(
    habit: dict, now: datetime, *, notify_time: time, tz: ZoneInfo
) -> bool:
    """Time-level gate: open today AND past the habit's reminder instant.

    Uses the habit's own habit_reminder_time ("HH:mm") when set, otherwise
    falls back to the global notify_time -- same pattern as due_time for
    tasks.
    """
    if not is_habit_open(habit):
        return False

    reminder_time_str = habit.get("habit_reminder_time")
    if reminder_time_str:
        hour, minute = reminder_time_str.split(":")
        instant_time = time(int(hour), int(minute))
    else:
        instant_time = notify_time

    today = now.astimezone(tz).date()
    reminder_instant = datetime.combine(today, instant_time, tzinfo=tz)
    return now >= reminder_instant
