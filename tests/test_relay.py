from unittest.mock import patch
from zoneinfo import ZoneInfo

from tudo_ntfy.config import Config
from tudo_ntfy.relay import handle_relay, is_authorized, parse_relay_path


def make_config(**overrides) -> Config:
    defaults = dict(
        tududi_url="https://tududi.example",
        tududi_internal_url="http://tududi-internal.example",
        tududi_token="tt_secret",
        ntfy_url="http://ntfy.example",
        ntfy_topic="tudo",
        ntfy_auth="",
        relay_url="http://relay.example:8787",
        relay_secret="correct-secret",
        timezone=ZoneInfo("UTC"),
    )
    defaults.update(overrides)
    return Config(**defaults)


CONFIG = make_config()


def test_parse_relay_path_complete():
    assert parse_relay_path("/relay/task/abc123/complete") == ("abc123", "complete")


def test_parse_relay_path_cancel():
    assert parse_relay_path("/relay/task/abc123/cancel") == ("abc123", "cancel")


def test_parse_relay_path_rejects_unknown_action():
    assert parse_relay_path("/relay/task/abc123/snooze") is None


def test_parse_relay_path_rejects_unrelated_path():
    assert parse_relay_path("/something/else") is None


def test_is_authorized_correct_secret():
    assert is_authorized("Bearer correct-secret", CONFIG)


def test_is_authorized_wrong_secret():
    assert not is_authorized("Bearer wrong-secret", CONFIG)


def test_is_authorized_missing_header():
    assert not is_authorized(None, CONFIG)


def test_handle_relay_rejects_non_post():
    assert handle_relay("GET", "/relay/task/abc/complete", "Bearer correct-secret", CONFIG) == 405


def test_handle_relay_rejects_bad_auth():
    assert handle_relay("POST", "/relay/task/abc/complete", "Bearer nope", CONFIG) == 401


def test_handle_relay_rejects_unknown_path():
    assert handle_relay("POST", "/relay/task/abc/snooze", "Bearer correct-secret", CONFIG) == 404


def test_handle_relay_complete_calls_tududi_client():
    with patch("tudo_ntfy.relay.tududi_client.complete", return_value=True) as complete:
        status = handle_relay(
            "POST", "/relay/task/abc123/complete", "Bearer correct-secret", CONFIG
        )
    complete.assert_called_once_with(CONFIG, "abc123")
    assert status == 200


def test_handle_relay_cancel_calls_tududi_client():
    with patch("tudo_ntfy.relay.tududi_client.cancel", return_value=True) as cancel:
        status = handle_relay(
            "POST", "/relay/task/abc123/cancel", "Bearer correct-secret", CONFIG
        )
    cancel.assert_called_once_with(CONFIG, "abc123")
    assert status == 200


def test_handle_relay_returns_502_when_tududi_call_fails():
    with patch("tudo_ntfy.relay.tududi_client.complete", return_value=False):
        status = handle_relay(
            "POST", "/relay/task/abc123/complete", "Bearer correct-secret", CONFIG
        )
    assert status == 502
