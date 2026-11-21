from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime

from . import dedup_store, due_logic, habit_logic, ntfy_client, payloads, remind_policy
from .config import Config
from .filters import should_skip

logger = logging.getLogger(__name__)


def _print_payload(kind: str, uid: str | None, payload: dict) -> None:
    print(f"--- dry-run {kind} {uid} ---")
    print(json.dumps(payload, indent=2))


def process_task(
    task: dict,
    config: Config,
    now: datetime,
    conn: sqlite3.Connection,
    skipped_project_uids: frozenset[str],
    dry_run: bool,
) -> None:
    if should_skip(task, config.skip_tags, skipped_project_uids):
        return
    if not due_logic.is_task_due(
        task,
        now,
        lead_minutes=config.notify_lead_minutes,
        notify_time=config.notify_time,
        tz=config.timezone,
    ):
        return

    policy = remind_policy.resolve_task_policy(task, config)
    occurrence_key = remind_policy.occurrence_key_for_task(task)
    last_notified_at = dedup_store.get_last_notified(
        conn, "task", task["uid"], occurrence_key
    )
    if not remind_policy.should_notify(
        policy, last_notified_at, now, tz=config.timezone
    ):
        return

    payload = payloads.build_task_payload(task, config)
    if dry_run:
        _print_payload("task", task.get("uid"), payload)
        return  # never consumes the real dedup window
    if not ntfy_client.publish(payload, config):
        logger.warning("failed to publish task %s, will retry next cycle", task.get("uid"))
        return
    dedup_store.mark_notified(conn, "task", task["uid"], occurrence_key, now)


def process_habit(
    habit: dict,
    config: Config,
    now: datetime,
    conn: sqlite3.Connection,
    skipped_project_uids: frozenset[str],
    dry_run: bool,
) -> None:
    if should_skip(habit, config.skip_tags, skipped_project_uids):
        return
    if not habit_logic.habit_reminder_due(
        habit, now, notify_time=config.notify_time, tz=config.timezone
    ):
        return

    policy = remind_policy.resolve_habit_policy(habit, config)
    occurrence_key = remind_policy.occurrence_key_for_habit(habit)
    last_notified_at = dedup_store.get_last_notified(
        conn, "habit", habit["uid"], occurrence_key
    )
    if not remind_policy.should_notify(
        policy, last_notified_at, now, tz=config.timezone
    ):
        return

    payload = payloads.build_habit_payload(habit, config)
    if dry_run:
        _print_payload("habit", habit.get("uid"), payload)
        return  # never consumes the real dedup window
    if not ntfy_client.publish(payload, config):
        logger.warning(
            "failed to publish habit %s, will retry next cycle", habit.get("uid")
        )
        return
    dedup_store.mark_notified(conn, "habit", habit["uid"], occurrence_key, now)
