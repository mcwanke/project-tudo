from __future__ import annotations

import logging

import requests

from .config import Config
from .retry import request_with_retry

logger = logging.getLogger(__name__)


def _auth(config: Config) -> tuple[dict[str, str], tuple[str, str] | None]:
    """Returns (headers, requests-auth-tuple) for the configured NTFY_AUTH.

    Empty -> no auth (today's default). "token:<value>" -> bearer header.
    "user:pass" -> HTTP basic auth.
    """
    if not config.ntfy_auth:
        return {}, None
    if config.ntfy_auth.startswith("token:"):
        token = config.ntfy_auth[len("token:") :]
        return {"Authorization": f"Bearer {token}"}, None
    if ":" in config.ntfy_auth:
        user, _, password = config.ntfy_auth.partition(":")
        return {}, (user, password)
    return {}, None


def publish(payload: dict, config: Config) -> bool:
    headers, auth = _auth(config)
    response = request_with_retry(
        lambda: requests.post(
            config.ntfy_url, json=payload, headers=headers, auth=auth, timeout=10
        )
    )
    if response.status_code >= 400:
        logger.warning("ntfy publish failed: HTTP %d", response.status_code)
        return False
    return True
