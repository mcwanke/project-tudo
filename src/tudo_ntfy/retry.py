from __future__ import annotations

import logging
import time as time_module
from typing import Callable

import requests

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = (1, 2, 4)


def request_with_retry(fn: Callable[[], "requests.Response"]) -> "requests.Response":
    """Retries a request callable on transient failures (timeouts, 5xx).

    4xx responses are returned as-is on the first attempt -- a bad token or
    bad uid won't fix itself by trying again, and retrying would just mask a
    misconfiguration.
    """
    attempts = len(BACKOFF_SECONDS) + 1
    last_exc: Exception | None = None
    last_response: "requests.Response | None" = None

    for attempt, delay in enumerate((0, *BACKOFF_SECONDS)):
        if delay:
            time_module.sleep(delay)
        try:
            response = fn()
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            logger.warning(
                "request failed (attempt %d/%d): %s", attempt + 1, attempts, exc
            )
            continue
        if response.status_code >= 500:
            last_response = response
            logger.warning(
                "request returned %d (attempt %d/%d)",
                response.status_code,
                attempt + 1,
                attempts,
            )
            continue
        return response

    if last_response is not None:
        return last_response
    assert last_exc is not None
    raise last_exc
