#!/usr/bin/env python3
"""
Overwatch - Windows Security Monitor
Native dashboard window + system tray. Everything else is controlled from the tray.
"""

import os
import sys
import logging
import logging.handlers
import threading
import ctypes


# pythonw.exe sets sys.stdout/sys.stderr to None. Any library that writes
# (uvicorn, pywebview, pip-installed package banners) then crashes the
# entire process with AttributeError before our logging is set up. Redirect
# to a file so the process survives and the cause is captured.
#
# This runs before the logging module is configured, so we can't use a
# RotatingFileHandler. Cap manually: if the file is over 1 MB, rotate it
# to .1 (keeping one backup) so the file can never grow unbounded.
if sys.stdout is None or sys.stderr is None:
    _app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    _stdio_log = os.path.join(_app_data, "Overwatch", "logs", "pythonw_stdio.log")
    os.makedirs(os.path.dirname(_stdio_log), exist_ok=True)
    try:
        if os.path.exists(_stdio_log) and os.path.getsize(_stdio_log) > 1_000_000:
            _backup = _stdio_log + ".1"
            if os.path.exists(_backup):
                os.remove(_backup)
            os.replace(_stdio_log, _backup)
    except OSError:
        pass
    _f = open(_stdio_log, "a", buffering=1, encoding="utf-8", errors="replace")
    if sys.stdout is None:
        sys.stdout = _f
    if sys.stderr is None:
        sys.stderr = _f


log = logging.getLogger("winmon.main")


def setup_logging():
    """Configure rotating file log + console output."""
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(app_data, "Overwatch", "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "overwatch.log")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)

    if sys.stdout and sys.stdout.isatty():
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)


def single_instance():
    """Use a Windows named mutex to prevent multiple instances."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "OverwatchSecurityMonitor")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(
            0,
            "Overwatch is already running.\nCheck your system tray.",
            "Overwatch",
            0x40,
        )
        sys.exit(0)
    return mutex


def main():
    _mutex = single_instance()
    setup_logging()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    from winmon.config import Config
    from winmon.engine import MonitorEngine
    from winmon.gui.tray import TrayApp

    config = Config()
    engine = MonitorEngine(config)
    engine.start()

    # Try to build a native dashboard window; fall back to default browser on failure.
    window = None
    try:
        from winmon.gui.window import DashboardWindow
        window = DashboardWindow(engine.api.url)
        window.create()
    except Exception as e:
        log.warning("Native dashboard window unavailable, will use browser: %s", e)
        window = None

    tray = TrayApp(engine, dashboard_window=window)

    if window is not None:
        # PyWebView must own the main thread on Windows.
        # Tray runs on a background thread; close-from-tray exits the process via os._exit.
        threading.Thread(target=tray.run, name="overwatch-tray", daemon=True).start()
        try:
            window.run_blocking()
        except KeyboardInterrupt:
            pass
        finally:
            engine.stop()
    else:
        # No native window — tray on main thread, browser handles dashboard.
        try:
            tray.run()
        except KeyboardInterrupt:
            engine.stop()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        logging.getLogger("winmon.main").exception("Unhandled exception in main()")
        raise
