"""Windows Task Scheduler integration.

Registering a real Windows task (instead of a timer inside the app) means updates run even when
the app is closed, the screen is locked, or the laptop is asleep (the task wakes the PC).
"""
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

TASK_NAME = "NaukriProfileBot"
RUN_SCRIPT = Path(__file__).resolve().with_name("run_task.py")
NO_WINDOW = subprocess.CREATE_NO_WINDOW


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, creationflags=NO_WINDOW)


def parse_times(times: list[str]):
    return sorted(datetime.strptime(t, "%H:%M").time() for t in times)


def parse_end_date(end_date: str) -> date | None:
    return datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None


def next_run(times: list[str], end_date: str, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now()
    end = parse_end_date(end_date)
    for day_offset in range(2):
        day = now.date() + timedelta(days=day_offset)
        if end and day > end:
            return None
        for t in parse_times(times):
            candidate = datetime.combine(day, t)
            if candidate > now:
                return candidate
    return None


def _task_xml(times: list[str], end_date: str) -> str:
    now = datetime.now()
    end = f"{end_date}T23:59:59"
    triggers = []
    for t in parse_times(times):
        start = datetime.combine(now.date(), t)
        if start <= now:  # don't let "run missed tasks" fire for a slot that passed before activation
            start += timedelta(days=1)
        triggers.append(f"""
    <CalendarTrigger>
      <StartBoundary>{start:%Y-%m-%dT%H:%M:%S}</StartBoundary>
      <EndBoundary>{end}</EndBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>""")

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    user = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Naukri Profile Bot: refreshes your Naukri profile so it stays on top of recruiter searches.</Description>
  </RegistrationInfo>
  <Triggers>{''.join(triggers)}
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT20M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(str(exe))}</Command>
      <Arguments>"{escape(str(RUN_SCRIPT))}"</Arguments>
      <WorkingDirectory>{escape(str(RUN_SCRIPT.parent))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def register(times: list[str], end_date: str) -> None:
    xml_path = Path(tempfile.gettempdir()) / f"{TASK_NAME}.xml"
    xml_path.write_text(_task_xml(times, end_date), encoding="utf-16")
    try:
        res = _run("schtasks", "/create", "/tn", TASK_NAME, "/xml", str(xml_path), "/f")
    finally:
        xml_path.unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip())


def unregister() -> None:
    if is_registered():
        res = _run("schtasks", "/delete", "/tn", TASK_NAME, "/f")
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or res.stdout.strip())


def is_registered() -> bool:
    return _run("schtasks", "/query", "/tn", TASK_NAME).returncode == 0


# ---------- wake timers (power plan setting "Allow wake timers") ----------
def wake_timers_enabled() -> bool | None:
    """True if wake timers are fully enabled on both AC and battery, None if unknown."""
    out = _run("powercfg", "/q", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE").stdout
    values = re.findall(r"Index:\s*0x([0-9a-fA-F]+)\s*$", out, re.M)
    if len(values) < 2:
        return None
    return all(int(v, 16) == 1 for v in values[-2:])


def enable_wake_timers() -> None:
    for flag in ("/setacvalueindex", "/setdcvalueindex"):
        res = _run("powercfg", flag, "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE", "1")
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or res.stdout.strip())
    _run("powercfg", "/setactive", "SCHEME_CURRENT")
