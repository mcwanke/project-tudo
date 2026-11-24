from zoneinfo import ZoneInfo

from tudo_ntfy import status
from tudo_ntfy.config import Config


def make_config(**overrides) -> Config:
    defaults = dict(
        tududi_url="https://tududi.example",
        tududi_internal_url="http://tududi-internal.example",
        tududi_token="tt_very_secret",
        ntfy_url="http://ntfy.example",
        ntfy_topic="tudo",
        ntfy_auth="token:super-secret-ntfy-token",
        relay_url="http://relay.example:8787",
        relay_secret="super-secret-relay-value",
        timezone=ZoneInfo("UTC"),
    )
    defaults.update(overrides)
    return Config(**defaults)


def test_record_and_last_poll_result_round_trip():
    status.record_poll_result(tasks_seen=3, habits_seen=2, errors=0)
    result = status.last_poll_result()
    assert result["tasks_seen"] == 3
    assert result["habits_seen"] == 2
    assert result["errors"] == 0
    assert "at" in result


def test_record_poll_result_replaces_previous():
    status.record_poll_result(tasks_seen=1)
    status.record_poll_result(tasks_seen=2)
    result = status.last_poll_result()
    assert result["tasks_seen"] == 2


def test_render_status_html_never_includes_secrets():
    config = make_config()
    status.record_poll_result(tasks_seen=1, habits_seen=1, errors=0)
    html_out = status.render_status_html(config)
    assert "tt_very_secret" not in html_out
    assert "super-secret-ntfy-token" not in html_out
    assert "super-secret-relay-value" not in html_out
    # non-secret config is expected to show up, to make it useful for debugging
    assert "tududi.example" in html_out


def test_render_status_html_shows_recent_logs():
    import logging

    status.install_log_buffer()
    logger = logging.getLogger("tudo_ntfy.test_marker")
    logger.warning("a distinctive marker line for the status page test")
    html_out = status.render_status_html(make_config())
    assert "a distinctive marker line for the status page test" in html_out


def test_handle_status_rejects_non_get():
    code, _, _ = status.handle_status("POST", "/status", make_config())
    assert code == 405


def test_handle_status_rejects_unknown_path():
    code, _, _ = status.handle_status("GET", "/nope", make_config())
    assert code == 404


def test_handle_status_serves_html():
    code, content_type, body = status.handle_status("GET", "/status", make_config())
    assert code == 200
    assert content_type.startswith("text/html")
    assert b"tudo-ntfy status" in body
