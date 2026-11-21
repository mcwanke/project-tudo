from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import Config
from .retry import request_with_retry

logger = logging.getLogger(__name__)


def _headers(config: Config) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.tududi_token}"}


def list_habits(config: Config) -> list[dict[str, Any]]:
    response = request_with_retry(
        lambda: requests.get(
            f"{config.tududi_url}/api/habits",
            headers=_headers(config),
            timeout=10,
        )
    )
    if response.status_code >= 400:
        logger.warning("list_habits: HTTP %d", response.status_code)
        return []
    data = response.json()
    return data.get("habits", [])


def _post(config: Config, path: str, body: dict) -> bool:
    response = request_with_retry(
        lambda: requests.post(
            f"{config.tududi_url}{path}",
            headers={**_headers(config), "Content-Type": "application/json"},
            data=json.dumps(body),
            timeout=10,
        )
    )
    if response.status_code >= 400:
        logger.warning("POST %s failed: HTTP %d", path, response.status_code)
        return False
    return True


def complete(config: Config, uid: str, value: float | None = None) -> bool:
    body = {} if value is None else {"value": value}
    return _post(config, f"/api/habits/{uid}/complete", body)


def skip(config: Config, uid: str) -> bool:
    return _post(config, f"/api/habits/{uid}/skip", {})
