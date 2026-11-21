from __future__ import annotations

import logging
import signal
import threading
from datetime import datetime

from . import dedup_store, habits_client, notifier, relay, tududi_client
from .config import Config
from .filters import has_skip_tag

logger = logging.getLogger(__name__)


def run_once(config: Config, conn, dry_run: bool = False) -> None:
    now = datetime.now(config.timezone)

    projects = tududi_client.list_projects(config)
    skipped_project_uids = frozenset(
        p["uid"] for p in projects if has_skip_tag(p, config.skip_tags)
    )

    tasks = [
        t for t in tududi_client.list_open_tasks(config) if not t.get("habit_mode")
    ]
    for task in tasks:
        try:
            notifier.process_task(
                task, config, now, conn, skipped_project_uids, dry_run
            )
        except Exception:
            logger.exception("error processing task %s", task.get("uid"))

    habits = habits_client.list_habits(config)
    for habit in habits:
        try:
            notifier.process_habit(
                habit, config, now, conn, skipped_project_uids, dry_run
            )
        except Exception:
            logger.exception("error processing habit %s", habit.get("uid"))


def run(config: Config, once: bool = False, dry_run: bool = False) -> None:
    conn = dedup_store.init_db(config.state_path)
    stop_event = threading.Event()

    def _handle_signal(signum, _frame) -> None:
        logger.info("received signal %s, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    relay_server = relay.start_relay_server(config)

    try:
        while True:
            try:
                run_once(config, conn, dry_run=dry_run)
            except Exception:
                logger.exception("poll cycle failed, continuing")

            if once or stop_event.is_set():
                break
            stop_event.wait(config.poll_interval)
            if stop_event.is_set():
                break
    finally:
        relay_server.shutdown()
        relay_server.server_close()
        conn.close()
