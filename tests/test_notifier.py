from datetime import datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tudo_ntfy import dedup_store, notifier
from tudo_ntfy.config import Config

TZ = ZoneInfo("America/New_York")


def make_config(**overrides) -> Config:
    defaults = dict(
        tududi_url="https://tududi.example",
        tududi_token="tt_secret",
        ntfy_url="http://ntfy.example",
        ntfy_topic="tudo",
        ntfy_auth="",
        relay_url="http://relay.example:8787",
        relay_secret="relay_secret",
        timezone=TZ,
        notify_time=time(7, 0),
    )
    defaults.update(overrides)
    return Config(**defaults)


def make_conn():
    return dedup_store.init_db(":memory:")


def test_process_task_dry_run_never_touches_dedup_state(capsys):
    """--dry-run must not consume the real dedup window, or testing with it
    would silently suppress the first real notification afterwards."""
    config = make_config()
    conn = make_conn()
    now = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    task = {
        "uid": "t1",
        "name": "Pay rent",
        "due_date": "2026-11-18",
        "due_has_time": False,
        "recurrence_type": "monthly",
        "priority": 0,
        "tags": [],
        "project_uid": None,
    }

    notifier.process_task(task, config, now, conn, frozenset(), dry_run=True)
    out = capsys.readouterr().out
    assert "dry-run task t1" in out
    assert dedup_store.get_last_notified(conn, "task", "t1", "2026-11-18|") is None

    # Calling again in dry-run always re-prints -- nothing was marked notified.
    later_same_day = datetime(2026, 11, 20, 9, 0, tzinfo=TZ)
    notifier.process_task(task, config, later_same_day, conn, frozenset(), dry_run=True)
    out = capsys.readouterr().out
    assert "dry-run task t1" in out


def test_process_task_real_send_marks_notified_and_dedups():
    config = make_config()
    conn = make_conn()
    now = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    task = {
        "uid": "t1",
        "name": "Pay rent",
        "due_date": "2026-11-18",
        "due_has_time": False,
        "recurrence_type": "monthly",
        "priority": 0,
        "tags": [],
        "project_uid": None,
    }

    with patch("tudo_ntfy.notifier.ntfy_client.publish", return_value=True) as publish:
        notifier.process_task(task, config, now, conn, frozenset(), dry_run=False)
    assert publish.call_count == 1
    assert dedup_store.get_last_notified(conn, "task", "t1", "2026-11-18|") == now

    # Same calendar day, same slot already used -> no second send.
    later_same_day = datetime(2026, 11, 20, 9, 0, tzinfo=TZ)
    with patch("tudo_ntfy.notifier.ntfy_client.publish", return_value=True) as publish:
        notifier.process_task(task, config, later_same_day, conn, frozenset(), dry_run=False)
    assert publish.call_count == 0


def test_process_task_failed_publish_does_not_mark_notified():
    config = make_config()
    conn = make_conn()
    now = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    task = {
        "uid": "t1",
        "name": "Pay rent",
        "due_date": "2026-11-18",
        "due_has_time": False,
        "recurrence_type": "monthly",
        "priority": 0,
        "tags": [],
        "project_uid": None,
    }

    with patch("tudo_ntfy.notifier.ntfy_client.publish", return_value=False):
        notifier.process_task(task, config, now, conn, frozenset(), dry_run=False)
    assert dedup_store.get_last_notified(conn, "task", "t1", "2026-11-18|") is None


def test_process_task_skipped_by_tag(capsys):
    config = make_config()
    conn = make_conn()
    now = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    task = {
        "uid": "t2",
        "name": "Ignore me",
        "due_date": "2026-11-18",
        "due_has_time": False,
        "recurrence_type": "none",
        "priority": None,
        "tags": [{"name": "no-remind"}],
        "project_uid": None,
    }
    config = make_config(skip_tags=frozenset({"no-remind"}))

    notifier.process_task(task, config, now, conn, frozenset(), dry_run=True)
    assert capsys.readouterr().out == ""
    assert dedup_store.get_last_notified(conn, "task", "t2", "2026-11-18|") is None


def test_process_task_skipped_by_muted_project(capsys):
    config = make_config(skip_tags=frozenset({"muted"}))
    conn = make_conn()
    now = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    task = {
        "uid": "t3",
        "name": "Under muted project",
        "due_date": "2026-11-18",
        "due_has_time": False,
        "recurrence_type": "none",
        "priority": None,
        "tags": [],
        "project_uid": "proj-muted",
    }

    notifier.process_task(
        task, config, now, conn, frozenset({"proj-muted"}), dry_run=True
    )
    assert capsys.readouterr().out == ""


def test_process_task_not_yet_due_does_nothing(capsys):
    config = make_config()
    conn = make_conn()
    now = datetime(2026, 11, 20, 6, 0, tzinfo=TZ)  # before notify_time
    task = {
        "uid": "t4",
        "name": "Future-ish",
        "due_date": "2026-11-20",
        "due_has_time": False,
        "recurrence_type": "none",
        "priority": None,
        "tags": [],
        "project_uid": None,
    }

    notifier.process_task(task, config, now, conn, frozenset(), dry_run=True)
    assert capsys.readouterr().out == ""


def test_process_habit_measurable_dry_run(capsys):
    config = make_config()
    conn = make_conn()
    now = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    habit = {
        "uid": "h1",
        "name": "Drink water",
        "habit_mode": True,
        "habit_polarity": "build",
        "habit_target_value": 4,
        "habit_reminder_time": "07:00",
        "habit_progress": {
            "scheduled_today": True,
            "met": False,
            "skipped": False,
            "period_start": "2026-11-20",
            "goal": 4,
            "today_check_ins": 0,
        },
        "tags": [],
        "project_uid": None,
    }

    notifier.process_habit(habit, config, now, conn, frozenset(), dry_run=True)
    out = capsys.readouterr().out
    assert "dry-run habit h1" in out
    assert dedup_store.get_last_notified(conn, "habit", "h1", "2026-11-20") is None


def test_process_habit_skipped_by_tag(capsys):
    config = make_config(skip_tags=frozenset({"no-remind"}))
    conn = make_conn()
    now = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    habit = {
        "uid": "h2",
        "name": "Muted habit",
        "habit_polarity": "build",
        "habit_target_value": None,
        "habit_reminder_time": "07:00",
        "habit_progress": {"scheduled_today": True, "met": False, "skipped": False, "period_start": "2026-11-20"},
        "tags": [{"name": "no-remind"}],
        "project_uid": None,
    }

    notifier.process_habit(habit, config, now, conn, frozenset(), dry_run=True)
    assert capsys.readouterr().out == ""
