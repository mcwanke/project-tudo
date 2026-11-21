from datetime import datetime, time
from zoneinfo import ZoneInfo

from tudo_ntfy.habit_logic import (
    habit_reminder_due,
    is_habit_measurable,
    is_habit_open,
)

TZ = ZoneInfo("America/New_York")
NOTIFY_TIME = time(7, 0)


def test_is_habit_measurable_true_for_build_with_positive_target():
    habit = {"habit_polarity": "build", "habit_target_value": 4}
    assert is_habit_measurable(habit)


def test_is_habit_measurable_false_for_quit_polarity():
    habit = {"habit_polarity": "quit", "habit_target_value": 4}
    assert not is_habit_measurable(habit)


def test_is_habit_measurable_false_without_target_value():
    assert not is_habit_measurable({"habit_polarity": "build", "habit_target_value": None})
    assert not is_habit_measurable({"habit_polarity": "build", "habit_target_value": 0})
    assert not is_habit_measurable({"habit_polarity": "build"})


def test_is_habit_open_true_when_scheduled_and_unmet():
    habit = {"habit_progress": {"scheduled_today": True, "met": False, "skipped": False}}
    assert is_habit_open(habit)


def test_is_habit_open_false_when_met_or_skipped_or_not_scheduled():
    base = {"scheduled_today": True, "met": False, "skipped": False}
    assert not is_habit_open({"habit_progress": {**base, "met": True}})
    assert not is_habit_open({"habit_progress": {**base, "skipped": True}})
    assert not is_habit_open({"habit_progress": {**base, "scheduled_today": False}})
    assert not is_habit_open({"habit_progress": None})
    assert not is_habit_open({})


def test_habit_reminder_due_uses_habit_reminder_time():
    habit = {
        "habit_progress": {"scheduled_today": True, "met": False, "skipped": False},
        "habit_reminder_time": "20:00",
    }
    before = datetime(2026, 11, 20, 19, 59, tzinfo=TZ)
    at = datetime(2026, 11, 20, 20, 0, tzinfo=TZ)
    assert not habit_reminder_due(habit, before, notify_time=NOTIFY_TIME, tz=TZ)
    assert habit_reminder_due(habit, at, notify_time=NOTIFY_TIME, tz=TZ)


def test_habit_reminder_due_falls_back_to_notify_time():
    habit = {
        "habit_progress": {"scheduled_today": True, "met": False, "skipped": False},
        "habit_reminder_time": None,
    }
    before = datetime(2026, 11, 20, 6, 59, tzinfo=TZ)
    at = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)
    assert not habit_reminder_due(habit, before, notify_time=NOTIFY_TIME, tz=TZ)
    assert habit_reminder_due(habit, at, notify_time=NOTIFY_TIME, tz=TZ)


def test_habit_reminder_due_false_when_not_open():
    habit = {
        "habit_progress": {"scheduled_today": True, "met": True, "skipped": False},
        "habit_reminder_time": "00:00",
    }
    now = datetime(2026, 11, 20, 23, 0, tzinfo=TZ)
    assert not habit_reminder_due(habit, now, notify_time=NOTIFY_TIME, tz=TZ)
