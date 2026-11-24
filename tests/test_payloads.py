import json
from zoneinfo import ZoneInfo

from tudo_ntfy.config import Config
from tudo_ntfy.payloads import build_habit_payload, build_task_payload

TZ = ZoneInfo("America/New_York")


def make_config(**overrides) -> Config:
    defaults = dict(
        tududi_url="https://tududi.example",
        tududi_internal_url="http://tududi-internal.example",
        tududi_token="tt_secret",
        ntfy_url="http://ntfy.example",
        ntfy_topic="tudo",
        ntfy_auth="",
        relay_url="http://relay.example:8787",
        relay_secret="relay_secret",
        timezone=TZ,
    )
    defaults.update(overrides)
    return Config(**defaults)


CONFIG = make_config()


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
    payload = build_task_payload(task, CONFIG)

    assert payload["topic"] == "tudo"
    assert payload["title"] == "Pay rent"
    assert "Bills" in payload["message"]
    assert "High" in payload["message"]
    assert "Due: 2026-11-20" in payload["message"]

    actions = {a["label"]: a for a in payload["actions"]}
    assert set(actions) == {"Complete", "Cancel"}
    # Tasks route through the relay (POST), not directly to Tududi (PATCH) --
    # ntfy's Android app cannot fire a PATCH action.
    assert actions["Complete"]["url"] == "http://relay.example:8787/relay/task/abc123/complete"
    assert actions["Cancel"]["url"] == "http://relay.example:8787/relay/task/abc123/cancel"
    for action in actions.values():
        assert action["method"] == "POST"
        assert action["headers"]["Authorization"] == "Bearer relay_secret"
        assert action["clear"] is True
        assert isinstance(action["body"], str)  # pre-serialized JSON string


def test_build_task_payload_falls_back_to_name_and_omits_missing_fields():
    task = {"uid": "abc123", "name": "Buy milk", "due_date": "2026-11-20"}
    payload = build_task_payload(task, CONFIG)
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
