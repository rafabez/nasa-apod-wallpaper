"""Command line entry point.

    nasa-apod-wallpaper                 set today's APOD, show the info window and
                                        (re)install the daily schedule
    nasa-apod-wallpaper --install --time 07:30
    nasa-apod-wallpaper --uninstall
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests

from . import __version__, schedule, source, wallpaper, window

APP = "nasa-apod-wallpaper"
KEEP_IMAGES = 7
DEFAULTS = {"time": "09:00", "show_window": True, "nasa_api_key": ""}


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / APP
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_config(path: Path) -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        logging.getLogger(APP).warning("Ignoring unreadable %s: %s", path, e)
    return cfg


def save_config(path: Path, cfg: dict) -> None:
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def setup_logging(d: Path) -> logging.Logger:
    handlers = [RotatingFileHandler(d / "app.log", maxBytes=256_000, backupCount=1, encoding="utf-8")]
    if sys.stderr and sys.stderr.name != os.devnull:  # windowed binaries have no console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(message)s")
    return logging.getLogger(APP)


def download(url: str, day: str, d: Path) -> Path:
    r = requests.get(url, stream=True, timeout=source.TIMEOUT,
                     headers={"User-Agent": source.USER_AGENT})
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if not ctype.startswith("image/"):
        raise ValueError(f"not an image: {ctype or 'unknown type'}")
    ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
           "image/bmp": ".bmp"}.get(ctype, ".jpg")
    images = d / "images"
    images.mkdir(exist_ok=True)
    path = images / f"apod_{day}{ext}"  # unique per day: macOS caches wallpapers by path
    tmp = path.with_name(path.name + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(65536):
            f.write(chunk)
    os.replace(tmp, path)
    old = sorted(images.glob("apod_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in old[KEEP_IMAGES:]:
        p.unlink(missing_ok=True)
    return path


def apply_wallpaper(apod: dict, d: Path, log: logging.Logger) -> None:
    """Video days use the video's thumbnail when there is one."""
    if apod.get("media_type") == "image":
        candidates = [apod.get("hdurl"), apod.get("url")]
    else:
        candidates = [apod.get("thumbnail_url")]
    for url in filter(None, dict.fromkeys(candidates)):
        try:
            image = download(url, apod.get("date") or "today", d)
            method = wallpaper.set_wallpaper(image)
            log.info("Wallpaper set (%s): %s", method, image)
            return
        except Exception as e:  # noqa: BLE001 - try the next candidate
            log.warning("Could not use %s: %s", url, e)
    log.warning("Wallpaper unchanged (%s day, no usable image)", apod.get("media_type"))


def main(argv: list[str] | None = None) -> int:
    # Windowed binaries (Windows/macOS) start with no stdout/stderr; argparse and print need one.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    p = argparse.ArgumentParser(prog=APP, description="Set NASA's Astronomy Picture of the Day as your wallpaper.")
    p.add_argument("--date", help="use the APOD of this day (YYYY-MM-DD) instead of today")
    p.add_argument("--no-window", action="store_true", help="don't show the info window")
    p.add_argument("--install", action="store_true", help="install the daily run and exit")
    p.add_argument("--time", help="time of the daily run, HH:MM 24h (default 09:00)")
    p.add_argument("--uninstall", action="store_true", help="remove the daily run and exit")
    p.add_argument("--no-schedule", action="store_true", help="don't install the daily run")
    p.add_argument("--quiet", action="store_true", help="no dialogs for --install/--uninstall (for scripts)")
    p.add_argument("--scheduled", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)

    d = data_dir()
    log = setup_logging(d)
    cfg_path = d / "config.json"
    cfg = load_config(cfg_path)
    if args.time:
        cfg["time"] = args.time
        save_config(cfg_path, cfg)
    elif not cfg_path.exists():
        save_config(cfg_path, cfg)

    if args.uninstall:
        schedule.uninstall()
        window.message("NASA APOD Wallpaper", "Daily wallpaper update removed.", args.quiet)
        return 0
    if args.install:
        try:
            where = schedule.install(cfg["time"])
        except schedule.ScheduleError as e:
            window.message("NASA APOD Wallpaper", f"Could not install the daily run:\n{e}", args.quiet)
            return 1
        window.message("NASA APOD Wallpaper", f"Wallpaper will update daily at {cfg['time']}.\n({where})",
                       args.quiet)
        return 0

    api_key = os.environ.get("NASA_API_KEY") or cfg.get("nasa_api_key") or "DEMO_KEY"
    try:
        apod = source.fetch_apod(api_key, args.date, log)
    except Exception as e:  # noqa: BLE001
        log.error("Could not fetch the APOD: %s", e)
        return 1
    log.info("APOD %s: %s (%s)", apod.get("date"), apod.get("title"), apod.get("media_type"))

    stamp = d / "last_applied"
    last = stamp.read_text().strip() if stamp.exists() else ""
    if args.scheduled and apod.get("date") == last:
        log.info("APOD %s already applied today; nothing to do", last)
        return 0

    apply_wallpaper(apod, d, log)
    if apod.get("date") and not args.date:
        stamp.write_text(apod["date"])

    # A manual run (re)installs the schedule, so it follows the binary if it was moved.
    if not args.scheduled and not args.no_schedule:
        try:
            log.info("Daily run: %s at %s", schedule.install(cfg["time"]), cfg["time"])
        except Exception as e:  # noqa: BLE001
            log.warning("Could not install the daily run: %s", e)

    if not args.no_window and cfg.get("show_window", True):
        footer = f"Updates daily at {cfg['time']}" if schedule.is_installed() else ""
        window.show(apod, footer, log)
    return 0
