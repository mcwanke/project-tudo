import json
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from tudo_ntfy import habits_client
from tudo_ntfy.config import Config


def make_config() -> Config:
    return Config(
        tududi_url="https://tududi.example",
        tududi_token="tt_secret",
        ntfy_url="http://ntfy.example",
        ntfy_topic="tudo",
        ntfy_auth="",
        timezone=ZoneInfo("UTC"),
    )


def _response(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    return resp


def test_list_habits_returns_habits_array():
    config = make_config()
    resp = _response(json_body={"habits": [{"uid": "h1"}]})
    with patch("tudo_ntfy.habits_client.requests.get", return_value=resp):
        habits = habits_client.list_habits(config)
    assert habits == [{"uid": "h1"}]


def test_complete_without_value_sends_empty_body():
    config = make_config()
    resp = _response()
    with patch("tudo_ntfy.habits_client.requests.post", return_value=resp) as post:
        habits_client.complete(config, "h1")
    assert json.loads(post.call_args.kwargs["data"]) == {}
    assert post.call_args.args[0].endswith("/api/habits/h1/complete")


def test_complete_with_value_sends_value_body():
    config = make_config()
    resp = _response()
    with patch("tudo_ntfy.habits_client.requests.post", return_value=resp) as post:
        habits_client.complete(config, "h1", value=1)
    assert json.loads(post.call_args.kwargs["data"]) == {"value": 1}


def test_skip_sends_empty_body_to_skip_endpoint():
    config = make_config()
    resp = _response()
    with patch("tudo_ntfy.habits_client.requests.post", return_value=resp) as post:
        habits_client.skip(config, "h1")
    assert post.call_args.args[0].endswith("/api/habits/h1/skip")
    assert json.loads(post.call_args.kwargs["data"]) == {}
