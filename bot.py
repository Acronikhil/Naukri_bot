"""Browser automation: log in to Naukri, open the profile, click the pencil, click Save."""
import msvcrt
import random
import re
import shutil
import time
from typing import Callable

from playwright.sync_api import BrowserContext, Locator, Page, sync_playwright

from config import BROWSER_PROFILE_DIR, ERROR_SCREENSHOT, LOCK_FILE, Settings, get_password

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"

USERNAME_SELECTORS = [
    "#usernameField",
    "input[placeholder*='Email ID']",
    "input[type='email']",
]
PASSWORD_SELECTORS = [
    "#passwordField",
    "input[placeholder*='password' i]",
    "input[type='password']",
]
LOGIN_BUTTON_SELECTORS = [
    "button[type='submit']:has-text('Login')",
    "button.loginButton",
    "button:has-text('Login')",
]
# Pencil icon next to the name in the profile header.
EDIT_SELECTORS = [
    ".hdn em.edit",
    "em.icon.edit",
    "span.edit.icon",
    "xpath=//*[contains(normalize-space(text()),'Profile last updated')]"
    "/preceding::*[contains(@class,'edit')][1]",
]
SAVE_SELECTORS = [
    "#saveBasicDetailsBtn",
    "button[type='submit']:has-text('Save')",
    "button:has-text('Save')",
]

Log = Callable[[str], None]


class LoginRequired(Exception):
    pass


class BotBusy(Exception):
    pass


class ProfileLock:
    """Cross-process lock: only one browser may use the persistent profile at a time
    (the UI and a scheduled run are separate processes)."""

    def __enter__(self):
        self._f = open(LOCK_FILE, "a+")
        self._f.seek(0)
        try:
            msvcrt.locking(self._f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self._f.close()
            raise BotBusy("Another browser task is already running.")
        return self

    def __exit__(self, *exc):
        self._f.seek(0)
        msvcrt.locking(self._f.fileno(), msvcrt.LK_UNLCK, 1)
        self._f.close()


def _launch(p, hidden: bool) -> BrowserContext:
    """Launch a real (headed) browser on the persistent profile.

    Naukri answers true headless browsers with "Access Denied", so "hidden" mode runs a normal
    window positioned off-screen instead.
    """
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = ["--disable-blink-features=AutomationControlled"]
    if hidden:
        args += ["--window-position=-32000,-32000", "--start-minimized"]
    kwargs = dict(
        user_data_dir=str(BROWSER_PROFILE_DIR),
        headless=False,
        viewport={"width": 1366, "height": 850},
        args=args,
        ignore_default_args=["--enable-automation"],
    )
    # Prefer a real installed browser: Google sign-in rejects Playwright's bundled Chromium.
    for channel in ("chrome", "msedge"):
        try:
            return p.chromium.launch_persistent_context(channel=channel, **kwargs)
        except Exception:
            continue
    return p.chromium.launch_persistent_context(**kwargs)


def _first_visible(page: Page, selectors: list[str], timeout: float = 15) -> Locator:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for sel in selectors:
            if not sel:
                continue
            loc = page.locator(sel).first
            try:
                if loc.is_visible():
                    return loc
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise RuntimeError(f"None of these elements appeared: {selectors}")


def _pause(lo: float = 0.6, hi: float = 1.6) -> None:
    time.sleep(random.uniform(lo, hi))


def _human_scroll(page: Page) -> None:
    for _ in range(random.randint(4, 7)):
        page.mouse.wheel(0, random.randint(300, 650))
        _pause(0.4, 1.0)
    for _ in range(3):
        page.mouse.wheel(0, -random.randint(600, 900))
        _pause(0.3, 0.7)
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    _pause()


def _is_logged_out(page: Page) -> bool:
    return "nlogin" in page.url or "login" in page.url.split("?")[0].rsplit("/", 1)[-1]


def _settle(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


def _last_updated_text(page: Page) -> str:
    try:
        loc = page.get_by_text(re.compile(r"Profile last updated", re.I)).first
        return " ".join(loc.locator("xpath=..").inner_text(timeout=5000).split())
    except Exception:
        return ""


def _login_with_password(page: Page, username: str, password: str, log: Log) -> None:
    log("Logging in with saved email/password...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    _first_visible(page, USERNAME_SELECTORS).fill(username)
    _pause()
    _first_visible(page, PASSWORD_SELECTORS).fill(password)
    _pause()
    _first_visible(page, LOGIN_BUTTON_SELECTORS).click()
    try:
        page.wait_for_url(lambda url: "nlogin" not in url, timeout=30000)
    except Exception:
        raise LoginRequired(
            "Login did not complete (wrong password, OTP or captcha?). "
            "Use 'Log in with browser' in the app once."
        )
    log("Login successful.")


def update_profile(settings: Settings, log: Log) -> None:
    """Open profile -> click pencil -> click Save, so Naukri marks the profile as updated."""
    with ProfileLock(), sync_playwright() as p:
        ctx = _launch(p, hidden=settings.headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            log("Opening profile page...")
            page.goto(PROFILE_URL, wait_until="domcontentloaded")
            _settle(page)

            if _is_logged_out(page):
                password = get_password(settings.username)
                if settings.login_method == "password" and settings.username and password:
                    _login_with_password(page, settings.username, password, log)
                    page.goto(PROFILE_URL, wait_until="domcontentloaded")
                    _settle(page)
                else:
                    raise LoginRequired(
                        "Not logged in. Click 'Log in with browser' in the app and sign in once."
                    )

            before = _last_updated_text(page)
            if before:
                log(f"Before: {before}")

            log("Scrolling through profile...")
            _human_scroll(page)

            log("Clicking the edit (pencil) button...")
            _first_visible(page, [settings.custom_edit_selector, *EDIT_SELECTORS]).click()
            _pause(1.0, 2.0)

            log("Clicking Save...")
            save = _first_visible(page, [settings.custom_save_selector, *SAVE_SELECTORS])
            save.click()
            try:
                save.wait_for(state="hidden", timeout=15000)
            except Exception:
                pass
            _pause(1.5, 2.5)

            page.reload(wait_until="domcontentloaded")
            _settle(page)
            after = _last_updated_text(page)
            log(f"Profile updated. {after}" if after else "Profile updated.")
        except Exception:
            try:
                page.screenshot(path=str(ERROR_SCREENSHOT), full_page=True)
                log(f"Saved screenshot of the failure to {ERROR_SCREENSHOT}")
            except Exception:
                pass
            raise
        finally:
            ctx.close()


def manual_login(log: Log, timeout_minutes: int = 10) -> bool:
    """Open a visible browser so the user can log in with Google / OTP / password.

    The session cookies are saved in the persistent profile and reused by scheduled runs.
    """
    with ProfileLock(), sync_playwright() as p:
        ctx = _launch(p, hidden=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        log("Browser opened. Log in to Naukri (Google, OTP or password) in that window.")
        deadline = time.time() + timeout_minutes * 60
        logged_in = False
        while time.time() < deadline:
            try:
                if not ctx.pages:
                    break
                if any("/mnjuser/" in pg.url for pg in ctx.pages):
                    logged_in = True
                    log("Login detected. Session saved.")
                    time.sleep(3)
                    break
                ctx.pages[0].wait_for_timeout(1500)
            except Exception:
                break  # window was closed
        try:
            ctx.close()
        except Exception:
            pass
        if not logged_in:
            log("Browser closed without a detected login.")
        return logged_in


def clear_session() -> None:
    with ProfileLock():
        shutil.rmtree(BROWSER_PROFILE_DIR, ignore_errors=True)
