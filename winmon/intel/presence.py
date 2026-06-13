"""Presence detection — is the user actively at the keyboard?

When the user is present (recent mouse/keyboard activity), routine info-severity
events skip the Telegram channel — the dashboard + event DB still capture them.
Warning and critical events always pass through, so genuine intrusion signals
(RDP, USB connect, failed logon, suspicious file drop, watchlist process) are
never silenced.

Three modes (config: presence.mode):
- "auto"          — detect via input activity (default)
- "force_present" — manual override: always quiet for routine events
- "force_away"    — manual override: alert everything (e.g. leaving the house)
"""

import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger("winmon.presence")


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_seconds():
    """Seconds since last mouse/keyboard input, or None if the API fails."""
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        tick = ctypes.windll.kernel32.GetTickCount()
        # GetTickCount wraps every ~49 days; mask to unsigned 32-bit delta.
        delta_ms = (tick - lii.dwTime) & 0xFFFFFFFF
        return delta_ms / 1000.0
    except Exception:
        return None


def is_user_present(config):
    """True if the user counts as 'at the computer' right now.

    Returns False when the feature is off — meaning every alert passes through
    untouched (the existing behavior). This is the safer failure mode: if
    presence detection is broken or disabled, the user keeps getting pings.
    """
    if not config or not config.get("presence", "enabled", default=True):
        return False

    mode = config.get("presence", "mode") or "auto"
    if mode == "force_present":
        return True
    if mode == "force_away":
        return False

    threshold = config.get("presence", "idle_threshold_seconds") or 300
    idle = get_idle_seconds()
    if idle is None:
        return False  # API failed; default to loud (better to ping than miss)
    return idle < threshold


def snapshot(config):
    """JSON-serialisable presence state for /api/status and the dashboard."""
    if not config:
        return {"enabled": False, "mode": "auto", "present": False,
                "idle_seconds": None, "threshold_seconds": 300}
    return {
        "enabled": bool(config.get("presence", "enabled", default=True)),
        "mode": config.get("presence", "mode") or "auto",
        "present": is_user_present(config),
        "idle_seconds": get_idle_seconds(),
        "threshold_seconds": config.get("presence", "idle_threshold_seconds") or 300,
    }
