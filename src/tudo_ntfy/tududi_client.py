from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import Config
from .retry import request_with_retry

logger = logging.getLogger(__name__)

PAGE_LIMIT = 100


def _headers(config: Config) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.tududi_token}"}


def list_open_tasks(config: Config) -> list[dict[str, Any]]:
    """All tasks with status=active (not_started/in_progress/waiting/planned),
    paginated to completion."""
    tasks: list[dict] = []
    offset = 0
    while True:
        response = request_with_retry(
            lambda offset=offset: requests.get(
                f"{config.tududi_internal_url}/api/tasks",
                params={"status": "active", "limit": PAGE_LIMIT, "offset": offset},
                headers=_headers(config),
                timeout=10,
            )
        )
        if response.status_code >= 400:
            logger.warning(
                "list_open_tasks: HTTP %d at offset %d, stopping pagination",
                response.status_code,
                offset,
            )
            break
        data = response.json()
        page = data.get("tasks", [])
        tasks.extend(page)
        pagination = data.get("pagination") or {}
        if not pagination.get("hasMore"):
            break
        offset += PAGE_LIMIT
    return tasks


def list_projects(config: Config) -> list[dict[str, Any]]:
    response = request_with_retry(
        lambda: requests.get(
            f"{config.tududi_internal_url}/api/projects",
            headers=_headers(config),
            timeout=10,
        )
    )
    if response.status_code >= 400:
        logger.warning("list_projects: HTTP %d", response.status_code)
        return []
    data = response.json()
    if isinstance(data, list):
        return data
    return data.get("projects", [])


def _patch_task(config: Config, uid: str, body: dict) -> bool:
    response = request_with_retry(
        lambda: requests.patch(
            f"{config.tududi_internal_url}/api/task/{uid}",
            headers={**_headers(config), "Content-Type": "application/json"},
            data=json.dumps(body),
            timeout=10,
        )
    )
    if response.status_code >= 400:
        logger.warning("patch task %s failed: HTTP %d", uid, response.status_code)
        return False
    return True


def complete(config: Config, uid: str) -> bool:
    return _patch_task(config, uid, {"status": "done"})


def cancel(config: Config, uid: str) -> bool:
    return _patch_task(config, uid, {"status": "cancelled"})
