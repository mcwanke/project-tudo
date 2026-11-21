from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from tudo_ntfy.config import Config
from tudo_ntfy.remind_policy import (
    latest_slot_instant,
    occurrence_key_for_habit,
    occurrence_key_for_task,
    resolve_habit_policy,
    resolve_task_policy,
    should_notify,
)

TZ = ZoneInfo("America/New_York")


def make_config(**overrides) -> Config:
    defaults = dict(
        tududi_url="https://tududi.example",
        tududi_token="tt_test",
        ntfy_url="http://ntfy.example",
        ntfy_topic="tudo",
        ntfy_auth="",
        timezone=TZ,
        notify_time=time(7, 0),
        medium_priority_slots=[time(7, 0), time(19, 0)],
        high_priority_interval_minutes=60,
        habit_unit_remind_interval_minutes=120,
    )
    defaults.update(overrides)
    return Config(**defaults)


CONFIG = make_config()


def test_resolve_task_policy_none_without_due_date():
    assert resolve_task_policy({"due_date": None}, CONFIG) is None


@pytest.mark.parametrize("recurrence_type", ["daily", "weekly"])
def test_low_priority_short_recurrence_is_one_shot(recurrence_type):
    task = {"due_date": "2026-11-20", "recurrence_type": recurrence_type, "priority": 0}
    policy = resolve_task_policy(task, CONFIG)
    assert policy["kind"] == "one_shot"
    assert policy["window_end"] is not None


def test_low_priority_daily_window_is_one_day():
    task = {"due_date": "2026-11-20", "recurrence_type": "daily", "priority": None}
    policy = resolve_task_policy(task, CONFIG)
    assert policy["window_end"] == datetime(2026, 11, 21, 0, 0, tzinfo=TZ)


def test_low_priority_weekly_window_is_seven_days():
    task = {"due_date": "2026-11-20", "recurrence_type": "weekly", "priority": None}
    policy = resolve_task_policy(task, CONFIG)
    assert policy["window_end"] == datetime(2026, 11, 27, 0, 0, tzinfo=TZ)


@pytest.mark.parametrize("recurrence_type", ["monthly", "monthly_weekday", "monthly_last_day", "yearly", "none"])
def test_low_priority_long_recurrence_is_daily_slots_unbounded(recurrence_type):
    task = {"due_date": "2026-11-20", "recurrence_type": recurrence_type, "priority": 0}
    policy = resolve_task_policy(task, CONFIG)
    assert policy["kind"] == "daily_slots"
    assert policy["slots"] == [CONFIG.notify_time]
    assert policy["window_end"] is None


def test_medium_priority_daily_is_bounded_daily_slots():
    task = {"due_date": "2026-11-20", "recurrence_type": "daily", "priority": 1}
    policy = resolve_task_policy(task, CONFIG)
    assert policy["kind"] == "daily_slots"
    assert policy["slots"] == CONFIG.medium_priority_slots
    assert policy["window_end"] == datetime(2026, 11, 21, 0, 0, tzinfo=TZ)


def test_medium_priority_monthly_is_unbounded():
    task = {"due_date": "2026-11-20", "recurrence_type": "monthly", "priority": 1}
    policy = resolve_task_policy(task, CONFIG)
    assert policy["kind"] == "daily_slots"
    assert policy["window_end"] is None


def test_high_priority_weekly_is_bounded_interval():
    task = {"due_date": "2026-11-20", "recurrence_type": "weekly", "priority": 2}
    policy = resolve_task_policy(task, CONFIG)
    assert policy["kind"] == "interval"
    assert policy["minutes"] == CONFIG.high_priority_interval_minutes
    assert policy["window_end"] == datetime(2026, 11, 27, 0, 0, tzinfo=TZ)


def test_high_priority_one_off_is_unbounded_interval():
    task = {"due_date": "2026-11-20", "recurrence_type": "none", "priority": 2}
    policy = resolve_task_policy(task, CONFIG)
    assert policy["kind"] == "interval"
    assert policy["window_end"] is None


def test_resolve_habit_policy_ignores_priority():
    measurable = {
        "habit_polarity": "build",
        "habit_target_value": 4,
        "priority": 0,
    }
    policy = resolve_habit_policy(measurable, CONFIG)
    assert policy["kind"] == "interval"
    assert policy["minutes"] == CONFIG.habit_unit_remind_interval_minutes

    non_measurable = {"habit_polarity": "build", "habit_target_value": None, "priority": 2}
    policy = resolve_habit_policy(non_measurable, CONFIG)
    assert policy["kind"] == "one_shot"


def test_occurrence_keys():
    task = {"due_date": "2026-11-20", "due_time": "14:00"}
    assert occurrence_key_for_task(task) == "2026-11-20|14:00"

    task_no_time = {"due_date": "2026-11-20", "due_time": None}
    assert occurrence_key_for_task(task_no_time) == "2026-11-20|"

    habit = {"habit_progress": {"period_start": "2026-11-16"}}
    assert occurrence_key_for_habit(habit) == "2026-11-16"


def test_latest_slot_instant_picks_most_recent_past_slot():
    slots = [time(7, 0), time(19, 0)]
    now = datetime(2026, 11, 20, 20, 0, tzinfo=TZ)
    assert latest_slot_instant(slots, now, TZ) == datetime(2026, 11, 20, 19, 0, tzinfo=TZ)


def test_latest_slot_instant_falls_back_to_yesterday():
    slots = [time(7, 0), time(19, 0)]
    now = datetime(2026, 11, 20, 3, 0, tzinfo=TZ)
    assert latest_slot_instant(slots, now, TZ) == datetime(2026, 11, 19, 19, 0, tzinfo=TZ)


def test_should_notify_none_policy_is_false():
    assert not should_notify(None, None, datetime.now(TZ), tz=TZ)


def test_should_notify_respects_window_end_even_on_first_send():
    policy = {"kind": "one_shot", "window_end": datetime(2026, 11, 21, 0, 0, tzinfo=TZ)}
    too_late = datetime(2026, 11, 21, 0, 0, tzinfo=TZ)
    assert not should_notify(policy, None, too_late, tz=TZ)


def test_should_notify_first_time_is_true():
    policy = {"kind": "one_shot", "window_end": None}
    assert should_notify(policy, None, datetime.now(TZ), tz=TZ)


def test_should_notify_one_shot_never_repeats():
    policy = {"kind": "one_shot", "window_end": None}
    last = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)
    later = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    assert not should_notify(policy, last, later, tz=TZ)


def test_should_notify_daily_slots_resends_after_new_slot():
    policy = {"kind": "daily_slots", "slots": [time(7, 0), time(19, 0)], "window_end": None}
    last = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)
    before_next_slot = datetime(2026, 11, 20, 18, 59, tzinfo=TZ)
    at_next_slot = datetime(2026, 11, 20, 19, 0, tzinfo=TZ)
    assert not should_notify(policy, last, before_next_slot, tz=TZ)
    assert should_notify(policy, last, at_next_slot, tz=TZ)


def test_should_notify_interval():
    policy = {"kind": "interval", "minutes": 60, "window_end": None}
    last = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)
    before = datetime(2026, 11, 20, 7, 59, tzinfo=TZ)
    at = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)
    assert not should_notify(policy, last, before, tz=TZ)
    assert should_notify(policy, last, at, tz=TZ)
