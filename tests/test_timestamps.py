"""Regression tests for issue #5 (timestamp tz regression) and #7 (DB path).

Issue #5: v1.1.0 wrote UTC timestamps, v2.0.1 wrote LOCAL time into the same
marker-less TEXT column. A string ORDER BY timestamp then sorted old UTC rows
(e.g. '19:xx') above newer local rows ('15:xx'), so the dashboard looked frozen
on old events after upgrade. Fix: (a) write UTC consistently, (b) order the feed
by insertion id — robust against the mixed-tz rows already in the DB.

Issue #7: a bare relative db_path lands in the process CWD. EventDB must anchor
it under %APPDATA%\\Overwatch itself, so ANY caller is safe, while passing
absolute paths and :memory: through untouched.

Run: python -m tests.test_timestamps
"""

import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from winmon.database import EventDB
from winmon.paths import resolve_db_path


def _fresh_db():
    d = tempfile.mkdtemp()
    return EventDB(os.path.join(d, "t.db"))


def test_writes_are_utc_marked():
    """New events store a UTC ISO timestamp (offset marker present)."""
    db = _fresh_db()
    db.log_event("test", "hello")
    row = db.get_events(limit=1)[0]
    ts = row["timestamp"]
    # Parseable as an aware datetime, and it is UTC.
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None, f"timestamp not tz-aware: {ts!r}"
    assert parsed.utcoffset() == timedelta(0), f"timestamp not UTC: {ts!r}"
    # Close to now (within 5s) — proves it's not local-shifted.
    delta = abs((datetime.now(timezone.utc) - parsed).total_seconds())
    assert delta < 5, f"timestamp off by {delta}s: {ts!r}"
    db.close()
    print("PASS test_writes_are_utc_marked")


def test_feed_ordered_by_insertion_not_timestamp_string():
    """The exact #5 scenario: an OLD row whose timestamp STRING sorts high must
    NOT appear above a row inserted later. Insertion order wins."""
    db = _fresh_db()
    # Simulate a v1.1.0 UTC row with a high hour, inserted FIRST.
    db._conn.execute(
        "INSERT INTO events (timestamp, category, severity, summary) "
        "VALUES (?,?,?,?)",
        ("2026-07-19T19:51:20.336365", "process", "info", "OLD v1.1.0 utc row"),
    )
    db._conn.commit()
    # Then a real, newer event (goes through the UTC write path).
    db.log_event("process", "NEW row inserted later")
    feed = db.get_events(limit=10)
    assert feed[0]["summary"] == "NEW row inserted later", (
        "newest-inserted row must be first; got: "
        + ", ".join(e["summary"] for e in feed)
    )
    db.close()
    print("PASS test_feed_ordered_by_insertion_not_timestamp_string")


def test_dedup_still_collapses_repeats():
    """UTC change must not break the dedup window."""
    db = _fresh_db()
    id1, _ = db.log_event("usb", "same", dedup_key="k1")
    id2, upd2 = db.log_event("usb", "same", dedup_key="k1")
    assert id1 == id2 and upd2 is True, "second identical event should dedup"
    rows = db.get_events(limit=10)
    assert len(rows) == 1 and rows[0]["dedup_count"] == 2
    db.close()
    print("PASS test_dedup_still_collapses_repeats")


def test_stats_today_counts_recent_event():
    """A just-written event lands in the 'today' bucket (boundary is UTC-correct)."""
    db = _fresh_db()
    db.log_event("login", "someone logged in")
    stats = db.get_stats()
    assert stats["today"].get("login", 0) >= 1, f"today stats missing event: {stats}"
    db.close()
    print("PASS test_stats_today_counts_recent_event")


def test_resolve_db_path_passes_memory_through():
    """:memory: must never be anchored under %APPDATA% (would break in-mem DBs)."""
    assert resolve_db_path(":memory:") == ":memory:"
    print("PASS test_resolve_db_path_passes_memory_through")


def test_eventdb_anchors_bare_filename_under_appdata():
    """#7: a bare filename resolves under %APPDATA%\\Overwatch, not the CWD."""
    fake_appdata = tempfile.mkdtemp()
    os.environ["APPDATA"] = fake_appdata
    prev = os.getcwd()
    work = tempfile.mkdtemp()
    try:
        os.chdir(work)
        db = EventDB("winmon_events.db")   # bare filename, no resolve_db_path()
        db.log_event("test", "ok")
        db.close()
        anchored = Path(fake_appdata) / "Overwatch" / "winmon_events.db"
        assert anchored.exists(), f"DB not anchored under APPDATA: looked for {anchored}"
        assert not (Path(work) / "winmon_events.db").exists(), "DB leaked into CWD"
    finally:
        os.chdir(prev)
    print("PASS test_eventdb_anchors_bare_filename_under_appdata")


if __name__ == "__main__":
    test_writes_are_utc_marked()
    test_feed_ordered_by_insertion_not_timestamp_string()
    test_dedup_still_collapses_repeats()
    test_stats_today_counts_recent_event()
    test_resolve_db_path_passes_memory_through()
    test_eventdb_anchors_bare_filename_under_appdata()
    print("\nALL TESTS PASSED")
