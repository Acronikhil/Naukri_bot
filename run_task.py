"""Entry point used by Windows Task Scheduler for each scheduled profile update.

Runs without any window: waits for the network (Wi-Fi reconnects after waking from sleep),
keeps the PC awake while working, and retries a few times on transient failures. If the Naukri
session has expired it opens a browser and asks the user to log in again.
"""
import ctypes
import socket
import sys
import threading
import time
from datetime import datetime

import bot
from config import Settings, append_log, update_status

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
RELOGIN_TIMEOUT_MIN = 30


def wait_for_network(timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            socket.create_connection(("www.naukri.com", 443), timeout=5).close()
            return True
        except OSError:
            time.sleep(5)
    return False


def notify(title: str, text: str) -> None:
    """Show a non-blocking, always-on-top Windows message box."""
    flags = 0x40 | 0x40000 | 0x1000  # MB_ICONINFORMATION | MB_TOPMOST | MB_SYSTEMMODAL
    threading.Thread(
        target=ctypes.windll.user32.MessageBoxW, args=(None, text, title, flags), daemon=True
    ).start()


def relogin(log=append_log) -> bool:
    """Session expired: open a visible browser and wait for the user to log in again."""
    update_status(logged_in=False)
    log(f"Session expired. Opening the browser so you can log in again "
        f"(waiting up to {RELOGIN_TIMEOUT_MIN} minutes)...")
    notify("Naukri Profile Bot",
           "Your Naukri session has expired.\n\n"
           "Please log in again in the browser window that just opened. "
           "The profile update will continue automatically after you log in.")
    if bot.manual_login(log, timeout_minutes=RELOGIN_TIMEOUT_MIN):
        update_status(logged_in=True)
        return True
    return False


def perform(settings: Settings, attempts: int = 1, log=append_log) -> bool:
    """Run the profile update with retries and record the outcome in status.json.

    If the session has expired, the user is asked to log in again (once per run).
    """
    update_status(running=True)
    relogin_tried = False
    try:
        attempt = 0
        while attempt < attempts:
            attempt += 1
            try:
                bot.update_profile(settings, log)
                update_status(last_run=datetime.now().isoformat(), last_ok=True,
                              last_message="Profile updated", logged_in=True)
                return True
            except bot.LoginRequired as e:
                log(f"ERROR: {e}")
                if not relogin_tried:
                    relogin_tried = True
                    if relogin(log):
                        attempt -= 1  # the login prompt doesn't use up a retry
                        continue
                update_status(last_run=datetime.now().isoformat(), last_ok=False,
                              last_message="Login required", logged_in=False)
                return False
            except Exception as e:
                log(f"ERROR (attempt {attempt}/{attempts}): {e}")
                if attempt < attempts:
                    time.sleep(60)
        update_status(last_run=datetime.now().isoformat(), last_ok=False,
                      last_message="Failed - see activity log")
        return False
    finally:
        update_status(running=False)


def main() -> int:
    # Stop Windows from going back to sleep while the update runs.
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        append_log("Scheduled update started.")
        if not wait_for_network():
            append_log("ERROR: No internet connection; skipping this run.")
            update_status(last_run=datetime.now().isoformat(), last_ok=False,
                          last_message="No internet connection")
            return 1
        return 0 if perform(Settings.load(), attempts=3) else 1
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


if __name__ == "__main__":
    sys.exit(main())
