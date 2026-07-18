"""Filesystem path helpers anchored to Overwatch's per-user data dir.

All writable Overwatch state (config.json, logs, events DB) lives under
%APPDATA%\\Overwatch\\ so it works regardless of where the exe is installed or
what the process CWD happens to be.
"""

import os
from pathlib import Path


def app_data_dir():
    """The per-user Overwatch data dir (%APPDATA%\\Overwatch), no mkdir."""
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    return Path(app_data) / "Overwatch"


def resolve_db_path(configured):
    """Resolve the events DB to an absolute, writable location.

    The shipped default is a bare filename ("winmon_events.db"), which sqlite
    resolves against the process CWD. When Overwatch is launched from its
    Startup-folder shortcut (or as a packaged exe under Program Files), the CWD
    is a read-only system dir (C:\\Windows\\System32), so sqlite3.connect()
    crashes with "unable to open database file" before the app can start.
    Anchor any relative path under %APPDATA%\\Overwatch\\ — the same dir that
    holds config.json and logs — so the DB always lands somewhere writable.
    Absolute paths (e.g. a user override, or the demo server) pass through.
    """
    p = Path(configured or "winmon_events.db")
    if not p.is_absolute():
        p = app_data_dir() / p
    return str(p)
