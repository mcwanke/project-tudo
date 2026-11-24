from __future__ import annotations

import html
import logging
import threading
from collections import deque
from datetime import datetime

from .config import Config

_LOG_BUFFER_MAXLEN = 500
_log_buffer: deque[str] = deque(maxlen=_LOG_BUFFER_MAXLEN)
_last_poll: dict = {}
_lock = threading.Lock()
_installed = False


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        with _lock:
            _log_buffer.append(self.format(record))


def install_log_buffer() -> None:
    """Attach an in-memory log buffer to the root logger, once.

    Lets the status page show recent activity without needing file-based
    logging or access to `docker logs` -- useful since this container often
    runs somewhere that isn't convenient to tail directly.
    """
    global _installed
    if _installed:
        return
    handler = _BufferHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)
    _installed = True


def recent_logs() -> list[str]:
    with _lock:
        return list(_log_buffer)


def record_poll_result(**fields) -> None:
    fields["at"] = datetime.now().isoformat()
    with _lock:
        _last_poll.clear()
        _last_poll.update(fields)


def last_poll_result() -> dict:
    with _lock:
        return dict(_last_poll)


def _rows(data: dict) -> str:
    return "\n".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in data.items()
    )


def render_status_html(config: Config) -> str:
    poll = last_poll_result()
    logs = recent_logs()[-200:]
    log_text = "\n".join(html.escape(line) for line in logs)

    config_summary = {
        "tududi_url": config.tududi_url,
        "tududi_internal_url": config.tududi_internal_url,
        "ntfy_url": config.ntfy_url,
        "ntfy_topic": config.ntfy_topic,
        "relay_url": config.relay_url,
        "timezone": str(config.timezone),
        "poll_interval": config.poll_interval,
        "skip_tags": ", ".join(sorted(config.skip_tags)) or "(none)",
    }

    poll_table = _rows(poll) if poll else "<tr><td colspan=2>no poll recorded yet</td></tr>"

    return f"""<!doctype html>
<html>
<head>
<title>tudo-ntfy status</title>
<meta http-equiv="refresh" content="30">
<style>
body {{ font-family: monospace; margin: 2rem; background: #1e1e1e; color: #ddd; }}
h1, h2 {{ color: #fff; }}
table {{ border-collapse: collapse; margin-bottom: 1.5rem; }}
td {{ border: 1px solid #444; padding: 4px 10px; }}
pre {{ background: #111; color: #0f0; padding: 1rem; overflow-x: auto; max-height: 500px; white-space: pre-wrap; }}
</style>
</head>
<body>
<h1>tudo-ntfy status</h1>
<p>Auto-refreshes every 30s.</p>
<h2>Last poll</h2>
<table>{poll_table}</table>
<h2>Config (secrets redacted)</h2>
<table>{_rows(config_summary)}</table>
<h2>Recent logs (last {len(logs)})</h2>
<pre>{log_text}</pre>
</body>
</html>
"""


def handle_status(method: str, path: str, config: Config) -> tuple[int, str, bytes]:
    """Pure request handler: returns (status_code, content_type, body)."""
    if method != "GET":
        return 405, "text/plain; charset=utf-8", b"Method Not Allowed"
    if path not in ("/status", "/status/"):
        return 404, "text/plain; charset=utf-8", b"Not Found"
    return 200, "text/html; charset=utf-8", render_status_html(config).encode("utf-8")
