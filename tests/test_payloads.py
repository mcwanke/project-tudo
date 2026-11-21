import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

from tudo_ntfy.config import Config
from tudo_ntfy.payloads import build_habit_payload, build_task_payload

TZ = ZoneInfo("America/New_York")


def make_config(**overrides) -> Config:
    defaults = dict(
        tududi_url="https://tududi.example",
        tududi_token="tt_secret",
        ntfy_url="http://ntfy.example",
        ntfy_topic="tudo",
        ntfy_auth="",
        timezone=TZ,
    )
    defaults.update(overrides)
    return Config(**defaults)


CONFIG = make_config()
NOW = datetime(2026, 11, 20, 14, 0, tzinfo=TZ)


def test_build_task_payload_shape():
    task = {
        "uid": "abc123",
        "original_name": "Pay rent",
        "name": "Pay rent",
        "due_date": "2026-11-20",
        "due_has_time": False,
        "due_time": None,
        "priority": 2,
        "Project": {"name": "Bills"},
    }
    payload = build_task_payload(task, CONFIG, NOW)

    assert payload["topic"] == "tudo"
    assert payload["title"] == "Pay rent"
    assert "Bills" in payload["message"]
    assert "High" in payload["message"]
    assert "Due: 2026-11-20" in payload["message"]

    actions = {a["label"]: a for a in payload["actions"]}
    assert set(actions) == {"Complete", "Cancel", "Snooze +1h"}
    for action in actions.values():
        assert action["method"] == "PATCH"
        assert action["url"] == "https://tududi.example/api/task/abc123"
        assert action["headers"]["Authorization"] == "Bearer tt_secret"
        assert action["clear"] is True
        assert isinstance(action["body"], str)  # pre-serialized JSON string

    assert json.loads(actions["Complete"]["body"]) == {"status": "done"}
    assert json.loads(actions["Cancel"]["body"]) == {"status": "cancelled"}
    snooze_body = json.loads(actions["Snooze +1h"]["body"])
    assert snooze_body["due_has_time"] is True
    assert snooze_body["due_date"].endswith("Z")


def test_build_task_payload_falls_back_to_name_and_omits_missing_fields():
    task = {"uid": "abc123", "name": "Buy milk", "due_date": "2026-11-20"}
    payload = build_task_payload(task, CONFIG, NOW)
    assert payload["title"] == "Buy milk"
    assert "Priority" not in payload["message"]


def test_build_habit_payload_non_measurable_sends_empty_complete_body():
    habit = {
        "uid": "h1",
        "original_name": "Meditate",
        "habit_polarity": "build",
        "habit_target_value": None,
    }
    payload = build_habit_payload(habit, CONFIG)
    actions = {a["label"]: a for a in payload["actions"]}
    assert set(actions) == {"Complete", "Skip"}
    assert json.loads(actions["Complete"]["body"]) == {}
    assert actions["Complete"]["url"].endswith("/api/habits/h1/complete")
    assert actions["Skip"]["url"].endswith("/api/habits/h1/skip")
    for action in actions.values():
        assert action["method"] == "POST"


def test_build_habit_payload_measurable_sends_value_one():
    habit = {
        "uid": "h2",
        "original_name": "Drink water",
        "habit_polarity": "build",
        "habit_target_value": 4,
        "habit_progress": {"goal": 4, "today_check_ins": 1},
    }
    payload = build_habit_payload(habit, CONFIG)
    actions = {a["label"]: a for a in payload["actions"]}
    assert json.loads(actions["Complete"]["body"]) == {"value": 1}
    assert "1/4" in payload["message"]
