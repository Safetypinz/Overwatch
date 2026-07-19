"""Tests for issue #3 — crash/fatal-error alerting.

A security monitor that silently stops watching fails at its one job. These
cover TelegramNotifier.send_crash: it reports the error VERBATIM (no invented
description), includes machine + location, is a no-op when Telegram is off, and
never raises even if the underlying send fails.

Run: python -m tests.test_crash_alert
"""

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from winmon.notifier import TelegramNotifier


class FakeConfig:
    """Minimal stand-in for winmon.config.Config.get(*keys)."""

    def __init__(self, enabled=True):
        self._data = {
            "telegram": {"enabled": enabled, "bot_token": "t", "chat_id": "c"},
        }

    def get(self, *keys, default=None):
        node = self._data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node


def _notifier(enabled=True):
    n = TelegramNotifier(FakeConfig(enabled=enabled))
    sent = []
    n._send_telegram = lambda text: sent.append(text)   # capture, don't network
    return n, sent


def test_crash_alert_reports_error_verbatim():
    n, sent = _notifier()
    err = ValueError("unable to open database file")
    n.send_crash("main()", err)
    assert len(sent) == 1, "expected exactly one crash message"
    msg = sent[0]
    assert "unable to open database file" in msg, "verbatim error text missing"
    assert "ValueError" in msg, "error type missing"
    assert "main()" in msg, "location missing"
    assert socket.gethostname() in msg, "machine name missing"
    print("PASS test_crash_alert_reports_error_verbatim")


def test_crash_alert_noop_when_disabled():
    n, sent = _notifier(enabled=False)
    n.send_crash("main()", RuntimeError("boom"))
    assert sent == [], "must not send when Telegram disabled"
    print("PASS test_crash_alert_noop_when_disabled")


def test_crash_alert_never_raises():
    """Even if the underlying send blows up, the crash reporter must not crash."""
    n, _ = _notifier()

    def _boom(text):
        raise ConnectionError("telegram unreachable")

    n._send_telegram = _boom
    n.send_crash("main()", KeyError("x"))   # must swallow, not raise
    print("PASS test_crash_alert_never_raises")


def test_crash_alert_is_synchronous():
    """send_crash must NOT rely on the dispatch thread (process may be dying)."""
    n, sent = _notifier()
    # dispatch thread never started; send_crash must still deliver
    assert not n._running
    n.send_crash("monitor USBMonitor", OSError("device busy"))
    assert len(sent) == 1 and "device busy" in sent[0]
    print("PASS test_crash_alert_is_synchronous")


if __name__ == "__main__":
    test_crash_alert_reports_error_verbatim()
    test_crash_alert_noop_when_disabled()
    test_crash_alert_never_raises()
    test_crash_alert_is_synchronous()
    print("\nALL TESTS PASSED")
