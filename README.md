# Naukri Profile Bot

Keeps your Naukri profile marked as "recently updated" by opening your profile at the times you
choose, clicking the pencil (edit) icon and clicking **Save** without changing anything.

## Setup

```
pip install -r requirements.txt
python -m playwright install chromium
```

Start the app with `run.bat` (or `python app.py`).

## Usage

1. **Naukri account**
   - **Google / OTP**: click **Log in with browser** and sign in once. The session is saved.
   - **Email & Password**: enter your details and click **Save credentials** (stored in Windows
     Credential Manager).
2. **Schedule**: add the times, pick **Run until**, then click **Activate schedule**.
3. **Status → Wake from sleep**: click **Enable** if it says *Disabled*, so Windows is allowed to
   wake the laptop for scheduled updates.

Use **Update now** any time to test.

## How scheduled runs work

**Activate schedule** registers a Windows Task Scheduler task called `NaukriProfileBot`, which runs
`run_task.py` with no window. Because of that:

- **The app can stay closed.** Opening it is only needed to change settings.
- **Locked screen:** updates still run.
- **Sleep / hibernate:** Windows wakes the laptop for each update, if wake timers are enabled.
  If the laptop couldn't wake (for example wake timers are off, or it was shut down), the missed
  update runs as soon as the laptop is on again.
- After waking, the bot waits up to 3 minutes for Wi-Fi to reconnect and retries up to 3 times.
- **Session expired?** The bot opens the Naukri login page in a browser window and shows a
  pop-up asking you to log in. It waits up to 30 minutes; once you log in, the update continues
  automatically. If you don't, it tries again at the next scheduled time.
- Requirement: you must be **signed in to Windows**. A locked screen is fine; signed out or shut
  down is not.

## Files

Data lives in `%APPDATA%\NaukriProfileBot`: settings, saved browser session, `bot.log`,
`status.json`, and `last_error.png` (a screenshot taken when an update fails).

If Naukri changes its page layout and the pencil or Save button can't be found, check
`last_error.png`, then put a working CSS selector in `custom_edit_selector` /
`custom_save_selector` in `config.json`.
