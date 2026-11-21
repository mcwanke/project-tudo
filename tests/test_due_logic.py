from datetime import datetime, time
from zoneinfo import ZoneInfo

from tudo_ntfy.due_logic import compute_due_instant, is_task_due

TZ = ZoneInfo("America/New_York")
NOTIFY_TIME = time(7, 0)


def test_compute_due_instant_none_without_due_date():
    assert compute_due_instant({"due_date": None}, notify_time=NOTIFY_TIME, tz=TZ) is None


def test_compute_due_instant_whole_day_uses_notify_time():
    task = {"due_date": "2026-11-20", "due_has_time": False}
    instant = compute_due_instant(task, notify_time=NOTIFY_TIME, tz=TZ)
    assert instant == datetime(2026, 11, 20, 7, 0, tzinfo=TZ)


def test_compute_due_instant_timed_uses_due_time():
    task = {
        "due_date": "2026-11-20",
        "due_has_time": True,
        "due_time": "14:30",
    }
    instant = compute_due_instant(task, notify_time=NOTIFY_TIME, tz=TZ)
    assert instant == datetime(2026, 11, 20, 14, 30, tzinfo=TZ)


def test_is_task_due_false_without_due_date():
    now = datetime(2026, 11, 20, 12, 0, tzinfo=TZ)
    task = {"due_date": None}
    assert not is_task_due(
        task, now, lead_minutes=0, notify_time=NOTIFY_TIME, tz=TZ
    )


def test_is_task_due_overdue_is_true():
    now = datetime(2026, 11, 21, 8, 0, tzinfo=TZ)
    task = {"due_date": "2026-11-20", "due_has_time": False}
    assert is_task_due(task, now, lead_minutes=0, notify_time=NOTIFY_TIME, tz=TZ)


def test_is_task_due_future_is_false():
    now = datetime(2026, 11, 19, 8, 0, tzinfo=TZ)
    task = {"due_date": "2026-11-20", "due_has_time": False}
    assert not is_task_due(
        task, now, lead_minutes=0, notify_time=NOTIFY_TIME, tz=TZ
    )


def test_is_task_due_lead_minutes_pulls_it_forward():
    task = {
        "due_date": "2026-11-20",
        "due_has_time": True,
        "due_time": "14:00",
    }
    just_before_lead = datetime(2026, 11, 20, 13, 44, tzinfo=TZ)
    at_lead = datetime(2026, 11, 20, 13, 45, tzinfo=TZ)
    assert not is_task_due(
        task, just_before_lead, lead_minutes=15, notify_time=NOTIFY_TIME, tz=TZ
    )
    assert is_task_due(
        task, at_lead, lead_minutes=15, notify_time=NOTIFY_TIME, tz=TZ
    )
