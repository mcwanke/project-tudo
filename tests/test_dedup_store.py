from datetime import datetime
from zoneinfo import ZoneInfo

from tudo_ntfy import dedup_store

TZ = ZoneInfo("America/New_York")


def test_get_last_notified_none_when_absent(tmp_path):
    conn = dedup_store.init_db(str(tmp_path / "state.db"))
    assert dedup_store.get_last_notified(conn, "task", "u1", "2026-11-20|") is None


def test_mark_and_get_round_trip(tmp_path):
    conn = dedup_store.init_db(str(tmp_path / "state.db"))
    now = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)
    dedup_store.mark_notified(conn, "task", "u1", "2026-11-20|", now)
    assert dedup_store.get_last_notified(conn, "task", "u1", "2026-11-20|") == now


def test_mark_notified_upserts_latest_timestamp(tmp_path):
    conn = dedup_store.init_db(str(tmp_path / "state.db"))
    first = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)
    second = datetime(2026, 11, 20, 19, 0, tzinfo=TZ)
    dedup_store.mark_notified(conn, "task", "u1", "2026-11-20|", first)
    dedup_store.mark_notified(conn, "task", "u1", "2026-11-20|", second)
    assert dedup_store.get_last_notified(conn, "task", "u1", "2026-11-20|") == second


def test_different_occurrence_key_is_independent(tmp_path):
    conn = dedup_store.init_db(str(tmp_path / "state.db"))
    now = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)
    dedup_store.mark_notified(conn, "task", "u1", "2026-11-20|", now)
    assert dedup_store.get_last_notified(conn, "task", "u1", "2026-11-21|") is None


def test_different_item_type_is_independent(tmp_path):
    conn = dedup_store.init_db(str(tmp_path / "state.db"))
    now = datetime(2026, 11, 20, 7, 0, tzinfo=TZ)
    dedup_store.mark_notified(conn, "task", "u1", "key", now)
    assert dedup_store.get_last_notified(conn, "habit", "u1", "key") is None


def test_init_db_creates_parent_directory(tmp_path):
    nested = tmp_path / "nested" / "dir" / "state.db"
    conn = dedup_store.init_db(str(nested))
    assert nested.parent.exists()
    conn.close()
