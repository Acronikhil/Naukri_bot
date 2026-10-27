"""Entry point used by Windows Task Scheduler for each scheduled profile update.

Runs without any window: waits for the network (Wi-Fi reconnects after waking from sleep),
keeps the PC awake while working, and retries a few times on transient failures.
"""
import ctypes
import socket
import sys
import time
from datetime import datetime

import bot
from config import Settings, append_log, update_status

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def wait_for_network(timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            socket.create_connection(("www.naukri.com", 443), timeout=5).close()
            return True
        except OSError:
            time.sleep(5)
    return False


def perform(settings: Settings, attempts: int = 1, log=append_log) -> bool:
    """Run the profile update with retries and record the outcome in status.json."""
    update_status(running=True)
    try:
        for attempt in range(1, attempts + 1):
            try:
                bot.update_profile(settings, log)
                update_status(last_run=datetime.now().isoformat(), last_ok=True,
                              last_message="Profile updated", logged_in=True)
                return True
            except bot.LoginRequired as e:
                log(f"ERROR: {e}")
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
