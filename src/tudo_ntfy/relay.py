from __future__ import annotations

import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import status, tududi_client
from .config import Config

logger = logging.getLogger(__name__)

_PATH_RE = re.compile(r"^/relay/task/([^/]+)/(complete|cancel)$")


def parse_relay_path(path: str) -> tuple[str, str] | None:
    match = _PATH_RE.match(path)
    if not match:
        return None
    return match.group(1), match.group(2)


def is_authorized(auth_header: str | None, config: Config) -> bool:
    if not auth_header:
        return False
    return auth_header == f"Bearer {config.relay_secret}"


def handle_relay(
    method: str, path: str, auth_header: str | None, config: Config
) -> int:
    """Pure request handler: returns the HTTP status to send back.

    Kept separate from the socket-level server so it's trivially testable
    without opening real connections.
    """
    if method != "POST":
        return 405
    if not is_authorized(auth_header, config):
        logger.warning("relay: unauthorized request to %s", path)
        return 401

    parsed = parse_relay_path(path)
    if not parsed:
        logger.warning("relay: no route for %s", path)
        return 404

    uid, action = parsed
    logger.info("relay: %s task %s", action, uid)
    ok = (
        tududi_client.complete(config, uid)
        if action == "complete"
        else tududi_client.cancel(config, uid)
    )
    if not ok:
        logger.warning("relay: %s failed for task %s", action, uid)
        return 502
    logger.info("relay: %s succeeded for task %s", action, uid)
    return 200


def _make_handler(config: Config) -> type[BaseHTTPRequestHandler]:
    class RelayHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (stdlib naming convention)
            code = handle_relay(
                "POST", self.path, self.headers.get("Authorization"), config
            )
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802 (stdlib naming convention)
            # Status page is deliberately unauthenticated at this layer --
            # protect it at the reverse proxy (e.g. put it behind Authelia,
            # unlike /relay/* which can't be since ntfy can't complete an
            # interactive login).
            code, content_type, body = status.handle_status(
                "GET", self.path, config
            )
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            logger.info("relay: %s - %s", self.address_string(), format % args)

    return RelayHandler


def start_relay_server(config: Config) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(
        (config.relay_bind_host, config.relay_port), _make_handler(config)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(
        "relay server listening on %s:%d", config.relay_bind_host, config.relay_port
    )
    return server
