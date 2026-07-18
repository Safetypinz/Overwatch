"""Regression tests for the startup crash where a packaged Overwatch launched
from its Startup-folder shortcut died with:

    sqlite3.OperationalError: unable to open database file

Root cause: the events DB path was a bare relative filename resolved against
the process CWD (System32 for a shell-launched shortcut), and EventDB never
created a parent dir. Run: python -m tests.test_db_path
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from winmon.database import EventDB
from winmon.paths import resolve_db_path


def test_eventdb_creates_missing_parent_dir():
    """EventDB must open even when the parent dir doesn't exist yet."""
    d = tempfile.mkdtemp()
    db_path = os.path.join(d, "does", "not", "exist", "winmon_events.db")
    db = EventDB(db_path)  # pre-fix: raises OperationalError here
    db.log_event("test", "hello")
    assert os.path.exists(db_path)
    db.close()
    print("PASS test_eventdb_creates_missing_parent_dir")


def test_resolve_db_path_anchors_relative_under_appdata():
    """A bare/relative configured path resolves to an absolute APPDATA path,
    NOT the (possibly read-only) CWD."""
    fake_appdata = tempfile.mkdtemp()
    os.environ["APPDATA"] = fake_appdata
    resolved = resolve_db_path("winmon_events.db")
    assert os.path.isabs(resolved), resolved
    assert Path(fake_appdata) in Path(resolved).parents, resolved
    assert resolved.endswith("winmon_events.db")
    print("PASS test_resolve_db_path_anchors_relative_under_appdata")


def test_resolve_db_path_leaves_absolute_untouched():
    abs_path = os.path.join(tempfile.mkdtemp(), "custom.db")
    assert resolve_db_path(abs_path) == abs_path
    print("PASS test_resolve_db_path_leaves_absolute_untouched")


def test_startup_from_readonly_cwd():
    """Simulate the real crash: launched with a read-only CWD (System32).
    Resolving + opening the DB must still succeed."""
    fake_appdata = tempfile.mkdtemp()
    os.environ["APPDATA"] = fake_appdata
    ro = tempfile.mkdtemp()
    os.chmod(ro, 0o500)
    prev = os.getcwd()
    try:
        os.chdir(ro)
        db = EventDB(resolve_db_path("winmon_events.db"))
        db.log_event("test", "startup ok")
        db.close()
    finally:
        os.chdir(prev)
        os.chmod(ro, 0o700)
    print("PASS test_startup_from_readonly_cwd")


if __name__ == "__main__":
    test_eventdb_creates_missing_parent_dir()
    test_resolve_db_path_anchors_relative_under_appdata()
    test_resolve_db_path_leaves_absolute_untouched()
    test_startup_from_readonly_cwd()
    print("\nALL TESTS PASSED")
