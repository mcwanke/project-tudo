from __future__ import annotations

import os
import sqlite3
from datetime import datetime


def init_db(path: str) -> sqlite3.Connection:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notified (
            item_type TEXT NOT NULL,
            uid TEXT NOT NULL,
            occurrence_key TEXT NOT NULL,
            last_notified_at TEXT NOT NULL,
            PRIMARY KEY (item_type, uid, occurrence_key)
        )
        """
    )
    conn.commit()
    return conn


def get_last_notified(
    conn: sqlite3.Connection, item_type: str, uid: str, occurrence_key: str
) -> datetime | None:
    row = conn.execute(
        "SELECT last_notified_at FROM notified "
        "WHERE item_type = ? AND uid = ? AND occurrence_key = ?",
        (item_type, uid, occurrence_key),
    ).fetchone()
    if row is None:
        return None
    return datetime.fromisoformat(row[0])


def mark_notified(
    conn: sqlite3.Connection,
    item_type: str,
    uid: str,
    occurrence_key: str,
    now: datetime,
) -> None:
    conn.execute(
        """
        INSERT INTO notified (item_type, uid, occurrence_key, last_notified_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(item_type, uid, occurrence_key)
        DO UPDATE SET last_notified_at = excluded.last_notified_at
        """,
        (item_type, uid, occurrence_key, now.isoformat()),
    )
    conn.commit()
