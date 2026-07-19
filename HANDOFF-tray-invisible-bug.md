# HANDOFF — tray icon invisible on Windows (2026-07-19)

> For the next Claude session (likely running ON the affected PC via CC Sidekick).
> This is a live, reproduced diagnosis handed off from a remote (Jumper) session
> that could not see the interactive desktop. Read this, then debug from source.

## Symptom (user-reported, reproduced)

On **PC-33C8W33** (Dell Latitude 9520, **Windows 11 Pro build 26200** — a very new
insider-track build), Overwatch v2.0.1:
- Launches, engine starts fine (`overwatch.log`: "engine running with 5 monitors").
- **No system-tray icon appears.**
- Re-launching says **"Overwatch is already running — check your system tray"**
  (the single-instance mutex is held) — but there is nothing in the tray.
- So: the process is alive and healthy, just with **no visible UI**.

A reboot will NOT fix it — this is structural, not stale state.

## Root-cause hypothesis (high confidence, not yet fixed)

`run_winmon.py` → `main()`: when the PyWebView dashboard window creates
successfully (it does on Win 11 + WebView2), the tray is started on a **daemon
background thread** while PyWebView owns the main thread:

```python
threading.Thread(target=tray.run, name="overwatch-tray", daemon=True).start()
window.run_blocking()   # PyWebView owns the MAIN thread
```

On Windows, **pystray's `Icon.run()` frequently fails to register the taskbar
icon when called off the main thread** — the message pump that owns the tray icon
needs to be on the thread Windows expects. Result matches the symptom exactly:
engine + threads alive, mutex held, PyWebView window starts hidden, tray icon
never renders → user sees nothing.

Both pystray and PyWebView want the Windows main thread; the current code gives it
to PyWebView and demotes the tray — that's the conflict.

## How to confirm (from source, on the box via Sidekick)

1. `Setup.bat` (once) → `Overwatch.bat` to run from source with live tracebacks.
2. Launch, then `Get-Process Overwatch` — alive with no tray icon = confirmed.
3. Force the browser-fallback path so the tray runs on the MAIN thread (make
   `DashboardWindow.create()` raise, or temporarily set `window = None`). If the
   tray icon now **appears**, the daemon-thread tray is definitively the cause.

## Fixes to try, smallest first

1. **`icon.run_detached()`** instead of `icon.run()` in `winmon/gui/tray.py:run()`
   — pystray's mode built to coexist with another GUI framework's loop. Then keep
   pystray on the main thread and drive PyWebView's window on demand. (Cleanest if
   it works on build 26200.)
2. **Invert thread ownership** — tray on the main thread; only spin up the
   PyWebView window when the user opens the dashboard, rather than owning main at
   startup.
3. **Show the PyWebView window at startup** (not hidden) so there's at least one
   visible surface even if the tray icon is flaky — a fallback, not a real fix.

## Notes

- Config/DB persist at `%APPDATA%\Overwatch\`; logs at `%APPDATA%\Overwatch\logs\`.
- Existing config.json (from March) is intact and forward-compatible.
- The v2.0.1 exe is installed at `%USERPROFILE%\Overwatch\Overwatch.exe` with a
  Desktop shortcut. Debug from **source**, not that frozen exe.
- Deploy history: the exe was staged over Jumper (download + byte-verify + MOTW
  strip + shortcut — all fine). Launching it over the SSH session failed because a
  tray app needs the interactive desktop — which is why this is a Sidekick job.
