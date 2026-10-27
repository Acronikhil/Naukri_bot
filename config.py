"""Settings persistence, shared log/status files and secure credential storage."""
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import keyring

APP_NAME = "NaukriProfileBot"
APP_VERSION = "1.0.0"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
BROWSER_PROFILE_DIR = APP_DIR / "browser_profile"
CONFIG_FILE = APP_DIR / "config.json"
STATUS_FILE = APP_DIR / "status.json"
LOCK_FILE = APP_DIR / "browser.lock"
LOG_FILE = APP_DIR / "bot.log"
ERROR_SCREENSHOT = APP_DIR / "last_error.png"

APP_DIR.mkdir(parents=True, exist_ok=True)


def resource_path(relative: str) -> Path:
    """Path to a bundled file, both from source and inside the PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


@dataclass
class Settings:
    login_method: str = "manual"  # "password" or "manual" (Google / OTP)
    username: str = ""
    times: list[str] = field(default_factory=lambda: ["10:00", "12:30", "14:00"])  # 24h "HH:MM"
    end_date: str = ""  # "YYYY-MM-DD"
    headless: bool = True  # run the browser hidden (off-screen)
    # Optional overrides if Naukri changes its page layout (CSS / XPath selectors).
    custom_edit_selector: str = ""
    custom_save_selector: str = ""

    def save(self) -> None:
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        if not CONFIG_FILE.exists():
            return cls()
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def append_log(msg: str) -> None:
    """Shared log written by both the UI and scheduled runs; the UI tails this file."""
    line = f"[{datetime.now():%d-%b %I:%M:%S %p}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_status() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def update_status(**values) -> None:
    status = load_status()
    status.update(values)
    tmp = STATUS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    tmp.replace(STATUS_FILE)


def get_password(username: str) -> str | None:
    if not username:
        return None
    return keyring.get_password(APP_NAME, username)


def set_password(username: str, password: str) -> None:
    keyring.set_password(APP_NAME, username, password)


def delete_password(username: str) -> None:
    try:
        keyring.delete_password(APP_NAME, username)
    except keyring.errors.PasswordDeleteError:
        pass
