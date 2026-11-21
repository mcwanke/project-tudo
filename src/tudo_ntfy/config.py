from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from zoneinfo import ZoneInfo


def _parse_time(value: str) -> time:
    hour, minute = value.strip().split(":")
    return time(int(hour), int(minute))


def _parse_times(value: str) -> list[time]:
    return [_parse_time(v) for v in value.split(",") if v.strip()]


def _parse_tags(value: str) -> set[str]:
    return {v.strip().lower() for v in value.split(",") if v.strip()}


@dataclass(frozen=True)
class Config:
    tududi_url: str
    tududi_token: str
    ntfy_url: str
    ntfy_topic: str
    ntfy_auth: str
    timezone: ZoneInfo
    poll_interval: int = 60
    notify_lead_minutes: int = 0
    notify_time: time = time(7, 0)
    medium_priority_slots: list[time] = field(
        default_factory=lambda: [time(7, 0), time(19, 0)]
    )
    high_priority_interval_minutes: int = 60
    habit_unit_remind_interval_minutes: int = 120
    skip_tags: frozenset[str] = field(default_factory=frozenset)
    state_path: str = "/data/state.db"

    def __repr__(self) -> str:  # never leak the token in logs/exceptions
        return (
            f"Config(tududi_url={self.tududi_url!r}, tududi_token='***', "
            f"ntfy_url={self.ntfy_url!r}, ntfy_topic={self.ntfy_topic!r}, "
            f"ntfy_auth={'***' if self.ntfy_auth else ''!r}, "
            f"timezone={str(self.timezone)!r}, poll_interval={self.poll_interval!r}, "
            f"notify_lead_minutes={self.notify_lead_minutes!r}, "
            f"notify_time={self.notify_time!r}, "
            f"medium_priority_slots={self.medium_priority_slots!r}, "
            f"high_priority_interval_minutes={self.high_priority_interval_minutes!r}, "
            f"habit_unit_remind_interval_minutes={self.habit_unit_remind_interval_minutes!r}, "
            f"skip_tags={self.skip_tags!r}, state_path={self.state_path!r})"
        )


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def from_env() -> Config:
    return Config(
        tududi_url=_require("TUDUDI_URL").rstrip("/"),
        tududi_token=_require("TUDUDI_TOKEN"),
        ntfy_url=_require("NTFY_URL").rstrip("/"),
        ntfy_topic=_require("NTFY_TOPIC"),
        ntfy_auth=os.environ.get("NTFY_AUTH", ""),
        timezone=ZoneInfo(_require("TIMEZONE")),
        poll_interval=int(os.environ.get("POLL_INTERVAL", "60")),
        notify_lead_minutes=int(os.environ.get("NOTIFY_LEAD_MINUTES", "0")),
        notify_time=_parse_time(os.environ.get("NOTIFY_TIME", "07:00")),
        medium_priority_slots=_parse_times(
            os.environ.get("MEDIUM_PRIORITY_TIMES", "07:00,19:00")
        ),
        high_priority_interval_minutes=int(
            os.environ.get("HIGH_PRIORITY_INTERVAL_MINUTES", "60")
        ),
        habit_unit_remind_interval_minutes=int(
            os.environ.get("HABIT_UNIT_REMIND_INTERVAL_MINUTES", "120")
        ),
        skip_tags=frozenset(_parse_tags(os.environ.get("SKIP_TAGS", ""))),
        state_path=os.environ.get("STATE_PATH", "/data/state.db"),
    )
