from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .config import Config
from .habit_logic import is_habit_measurable

_PRIORITY_LABELS = {0: "Low", 1: "Medium", 2: "High"}


def _auth_headers(config: Config) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.tududi_token}"}


def _task_message(task: dict) -> str:
    parts = []
    project = task.get("Project")
    if project and project.get("name"):
        parts.append(project["name"])
    priority = task.get("priority")
    if priority is not None:
        parts.append(f"Priority: {_PRIORITY_LABELS.get(priority, priority)}")
    due_date = task.get("due_date")
    if due_date:
        due_bit = due_date
        if task.get("due_has_time") and task.get("due_time"):
            due_bit = f"{due_date} {task['due_time']}"
        parts.append(f"Due: {due_bit}")
    return " · ".join(parts) if parts else "Due now"


def build_task_payload(task: dict, config: Config, now: datetime) -> dict:
    uid = task["uid"]
    task_url = f"{config.tududi_url}/api/task/{uid}"
    title = task.get("original_name") or task.get("name") or "Task"
    headers = _auth_headers(config)

    snooze_due = now + timedelta(hours=1)
    snooze_body = {
        "due_date": snooze_due.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        ),
        "due_has_time": True,
    }

    actions = [
        {
            "action": "http",
            "label": "Complete",
            "url": task_url,
            "method": "PATCH",
            "headers": headers,
            "body": json.dumps({"status": "done"}),
            "clear": True,
        },
        {
            "action": "http",
            "label": "Cancel",
            "url": task_url,
            "method": "PATCH",
            "headers": headers,
            "body": json.dumps({"status": "cancelled"}),
            "clear": True,
        },
        {
            "action": "http",
            "label": "Snooze +1h",
            "url": task_url,
            "method": "PATCH",
            "headers": headers,
            "body": json.dumps(snooze_body),
            "clear": True,
        },
    ]

    return {
        "topic": config.ntfy_topic,
        "title": title,
        "message": _task_message(task),
        "actions": actions,
    }


def _habit_message(habit: dict, measurable: bool) -> str:
    progress = habit.get("habit_progress") or {}
    if measurable:
        goal = progress.get("goal")
        check_ins = progress.get("today_check_ins", 0)
        if goal:
            return f"{check_ins}/{goal} today"
    return "Habit check-in"


def build_habit_payload(habit: dict, config: Config) -> dict:
    uid = habit["uid"]
    title = habit.get("original_name") or habit.get("name") or "Habit"
    measurable = is_habit_measurable(habit)
    headers = _auth_headers(config)
    complete_body = {"value": 1} if measurable else {}

    actions = [
        {
            "action": "http",
            "label": "Complete",
            "url": f"{config.tududi_url}/api/habits/{uid}/complete",
            "method": "POST",
            "headers": headers,
            "body": json.dumps(complete_body),
            "clear": True,
        },
        {
            "action": "http",
            "label": "Skip",
            "url": f"{config.tududi_url}/api/habits/{uid}/skip",
            "method": "POST",
            "headers": headers,
            "body": json.dumps({}),
            "clear": True,
        },
    ]

    return {
        "topic": config.ntfy_topic,
        "title": title,
        "message": _habit_message(habit, measurable),
        "actions": actions,
    }
