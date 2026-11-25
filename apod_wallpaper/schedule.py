"""Install/remove the daily run: Task Scheduler (Windows), launchd (macOS), systemd user timer (Linux).

No admin/root rights needed on any platform. Missed runs (computer off or asleep)
catch up at the next opportunity; the app skips the run if today's APOD was
already applied, so catch-ups never duplicate.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = "nasa-apod-wallpaper"
WIN_TASK = "NASA APOD Wallpaper"
MAC_LABEL = "io.github.rafabez.nasa-apod-wallpaper"
LAUNCHER = Path(__file__).resolve().parent.parent / "nasa_apod_wallpaper.py"


class ScheduleError(Exception):
    pass


def command() -> list[str]:
    """The command the scheduler runs: the binary itself, or python + launcher from source."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--scheduled"]
    return [sys.executable, str(LAUNCHER), "--scheduled"]


def _parse_time(hhmm: str) -> tuple[int, int]:
    try:
        h, m = (int(x) for x in hhmm.split(":"))
        if 0 <= h < 24 and 0 <= m < 60:
            return h, m
    except ValueError:
        pass
    raise ScheduleError(f"invalid time {hhmm!r}, use HH:MM (24h)")


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise ScheduleError(f"{' '.join(cmd[:3])} failed: {(r.stderr or r.stdout).strip()}")
    return r


# ---------------------------------------------------------------- Windows

def _win_xml(h: int, m: int) -> str:
    from xml.sax.saxutils import escape

    cmd = command()
    args = " ".join(f'"{a}"' if " " in a else a for a in cmd[1:])
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Sets the NASA Astronomy Picture of the Day as wallpaper.</Description></RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2025-01-01T{h:02d}:{m:02d}:00</StartBoundary>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <StartWhenAvailable>true</StartWhenAvailable>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT23H</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{escape(cmd[0])}</Command><Arguments>{escape(args)}</Arguments></Exec>
  </Actions>
</Task>
"""


def _win_install(h: int, m: int) -> str:
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        Path(path).write_text(_win_xml(h, m), encoding="utf-16")
        _run(["schtasks", "/Create", "/TN", WIN_TASK, "/XML", path, "/F"])
    finally:
        os.unlink(path)
    return f'Task Scheduler task "{WIN_TASK}"'


def _win_uninstall() -> None:
    _run(["schtasks", "/Delete", "/TN", WIN_TASK, "/F"], check=False)


def _win_installed() -> bool:
    return _run(["schtasks", "/Query", "/TN", WIN_TASK], check=False).returncode == 0


# ---------------------------------------------------------------- macOS

def _mac_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def _mac_install(h: int, m: int) -> str:
    import plistlib

    plist = _mac_plist()
    plist.parent.mkdir(parents=True, exist_ok=True)
    _mac_uninstall()
    with open(plist, "wb") as f:
        plistlib.dump({
            "Label": MAC_LABEL,
            "ProgramArguments": command(),
            "StartCalendarInterval": {"Hour": h, "Minute": m},
            "RunAtLoad": True,  # catch up at login; skipped if today's APOD is already set
        }, f)
    domain = f"gui/{os.getuid()}"
    if _run(["launchctl", "bootstrap", domain, str(plist)], check=False).returncode != 0:
        _run(["launchctl", "load", "-w", str(plist)])
    return f"launchd agent {plist}"


def _mac_uninstall() -> None:
    plist = _mac_plist()
    if plist.exists():
        _run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], check=False)
        plist.unlink()


def _mac_installed() -> bool:
    return _mac_plist().exists()


# ---------------------------------------------------------------- Linux

def _units_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd" / "user"


def _systemd_quote(arg: str) -> str:
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def _linux_install(h: int, m: int) -> str:
    d = _units_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{NAME}.service").write_text(f"""[Unit]
Description=NASA APOD wallpaper
After=graphical-session.target network-online.target
Wants=network-online.target

[Service]
Type=simple
# Wait up to ~60s for the network after login/resume.
ExecStartPre=/bin/sh -c 'for i in $(seq 30); do getent hosts science.nasa.gov >/dev/null && exit 0; sleep 2; done; exit 0'
ExecStart={" ".join(_systemd_quote(a) for a in command())}
""")
    (d / f"{NAME}.timer").write_text(f"""[Unit]
Description=Daily NASA APOD wallpaper

[Timer]
OnCalendar=*-*-* {h:02d}:{m:02d}:00
Persistent=true

[Install]
WantedBy=timers.target
""")
    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", f"{NAME}.timer"])
    return f"systemd user timer {NAME}.timer"


def _linux_uninstall() -> None:
    _run(["systemctl", "--user", "disable", "--now", f"{NAME}.timer"], check=False)
    for ext in ("timer", "service"):
        (_units_dir() / f"{NAME}.{ext}").unlink(missing_ok=True)
    _run(["systemctl", "--user", "daemon-reload"], check=False)


def _linux_installed() -> bool:
    return (_units_dir() / f"{NAME}.timer").exists()


# ---------------------------------------------------------------- public API

def install(hhmm: str) -> str:
    h, m = _parse_time(hhmm)
    if sys.platform == "win32":
        return _win_install(h, m)
    if sys.platform == "darwin":
        return _mac_install(h, m)
    return _linux_install(h, m)


def uninstall() -> None:
    if sys.platform == "win32":
        _win_uninstall()
    elif sys.platform == "darwin":
        _mac_uninstall()
    else:
        _linux_uninstall()


def is_installed() -> bool:
    if sys.platform == "win32":
        return _win_installed()
    if sys.platform == "darwin":
        return _mac_installed()
    return _linux_installed()
