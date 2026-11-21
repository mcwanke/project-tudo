import json
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from tudo_ntfy import tududi_client
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


def test_list_open_tasks_paginates_until_exhausted():
    config = make_config()
    page1 = _response(json_body={
        "tasks": [{"uid": "a"}],
        "pagination": {"hasMore": True},
    })
    page2 = _response(json_body={
        "tasks": [{"uid": "b"}],
        "pagination": {"hasMore": False},
    })
    with patch("tudo_ntfy.tududi_client.requests.get", side_effect=[page1, page2]) as get:
        tasks = tududi_client.list_open_tasks(config)

    assert [t["uid"] for t in tasks] == ["a", "b"]
    assert get.call_count == 2
    first_call_params = get.call_args_list[0].kwargs["params"]
    second_call_params = get.call_args_list[1].kwargs["params"]
    assert first_call_params["offset"] == 0
    assert second_call_params["offset"] == tududi_client.PAGE_LIMIT


def test_list_open_tasks_stops_on_error():
    config = make_config()
    error_response = _response(status_code=500)
    with patch(
        "tudo_ntfy.tududi_client.requests.get", return_value=error_response
    ), patch("tudo_ntfy.retry.time_module.sleep"):
        tasks = tududi_client.list_open_tasks(config)
    assert tasks == []


def test_list_projects_handles_envelope_shape():
    config = make_config()
    resp = _response(json_body={"projects": [{"uid": "p1"}]})
    with patch("tudo_ntfy.tududi_client.requests.get", return_value=resp):
        projects = tududi_client.list_projects(config)
    assert projects == [{"uid": "p1"}]


def test_complete_sends_done_status():
    config = make_config()
    resp = _response(status_code=200)
    with patch("tudo_ntfy.tududi_client.requests.patch", return_value=resp) as patch_call:
        ok = tududi_client.complete(config, "abc")
    assert ok is True
    kwargs = patch_call.call_args.kwargs
    assert json.loads(kwargs["data"]) == {"status": "done"}
    assert kwargs["headers"]["Authorization"] == "Bearer tt_secret"


def test_cancel_sends_cancelled_status():
    config = make_config()
    resp = _response(status_code=200)
    with patch("tudo_ntfy.tududi_client.requests.patch", return_value=resp) as patch_call:
        tududi_client.cancel(config, "abc")
    assert json.loads(patch_call.call_args.kwargs["data"]) == {"status": "cancelled"}
