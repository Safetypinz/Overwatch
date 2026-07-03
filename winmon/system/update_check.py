"""Anonymous update check against vortenia.com.

Once a day, fetch a static JSON file and compare its `latest` version against
the running version. Nothing is sent beyond the HTTP request itself (the
User-Agent carries the running version so release adoption is visible in
server-side analytics). No machine ID, no config data, no payload.

Disabled with config: updates.enabled = false.
"""

import json
import logging
import threading
import urllib.request

from winmon import __version__

log = logging.getLogger("winmon.updates")

DEFAULT_CHECK_URL = "https://vortenia.com/version/overwatch.json"
CHECK_INTERVAL = 24 * 3600     # once a day
FIRST_CHECK_DELAY = 90         # let monitors settle before the first check


def _parse_version(text):
    """'2.0.1' -> (2, 0, 1). Returns None on anything malformed."""
    try:
        parts = tuple(int(p) for p in str(text).strip().split("."))
        return parts if parts else None
    except (ValueError, AttributeError):
        return None


class UpdateChecker:
    """Daily background version check. Never raises; failures are logged and retried next cycle."""

    def __init__(self, config):
        self._config = config
        self._stop = threading.Event()
        self._thread = None
        self.latest_version = None
        self.update_available = False
        self.release_url = None

    def start(self):
        self._thread = threading.Thread(
            target=self._loop, name="overwatch-update-check", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop.set()

    def status(self):
        return {
            "current": __version__,
            "latest": self.latest_version,
            "available": self.update_available,
            "url": self.release_url,
        }

    # ---- internals ---------------------------------------------------------

    def _enabled(self):
        val = self._config.get("updates", "enabled")
        return True if val is None else bool(val)

    def _loop(self):
        if self._stop.wait(FIRST_CHECK_DELAY):
            return
        while not self._stop.is_set():
            if self._enabled():
                self._check_once()
            else:
                log.debug("Update check disabled in config")
            if self._stop.wait(CHECK_INTERVAL):
                return

    def _check_once(self):
        url = self._config.get("updates", "check_url") or DEFAULT_CHECK_URL
        req = urllib.request.Request(
            url, headers={"User-Agent": f"Overwatch/{__version__}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                info = json.loads(resp.read())
        except Exception as e:
            log.debug("Update check failed (will retry tomorrow): %s", e)
            return

        latest = info.get("latest")
        remote = _parse_version(latest)
        local = _parse_version(__version__)
        if remote is None or local is None:
            log.debug("Update check: unparseable version %r", latest)
            return

        self.latest_version = str(latest)
        self.release_url = info.get("url") or "https://vortenia.com/overwatch/"
        newer = remote > local
        if newer and not self.update_available:
            log.info("Update available: %s (running %s)", latest, __version__)
        self.update_available = newer
