from __future__ import annotations

import json

from .config import Config
from .habit_logic import is_habit_measurable

_PRIORITY_LABELS = {0: "Low", 1: "Medium", 2: "High"}


def _tududi_auth_headers(config: Config) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.tududi_token}"}


def _relay_auth_headers(config: Config) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.relay_secret}"}


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


def build_task_payload(task: dict, config: Config) -> dict:
    uid = task["uid"]
    title = task.get("original_name") or task.get("name") or "Task"
    # Tasks are completed/cancelled via PATCH, which the ntfy Android app's
    # action buttons cannot fire (confirmed: a bare PATCH action silently
    # never reaches the server). Routed through our own relay instead,
    # which accepts the POST the app *can* send and re-issues it as a
    # server-to-server PATCH. Bonus: the real Tududi token never has to sit
    # inside the notification for tasks.
    headers = _relay_auth_headers(config)

    actions = [
        {
            "action": "http",
            "label": "Complete",
            "url": f"{config.relay_url}/relay/task/{uid}/complete",
            "method": "POST",
            "headers": headers,
            "body": "{}",
            "clear": True,
        },
        {
            "action": "http",
            "label": "Cancel",
            "url": f"{config.relay_url}/relay/task/{uid}/cancel",
            "method": "POST",
            "headers": headers,
            "body": "{}",
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
    headers = _tududi_auth_headers(config)
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
