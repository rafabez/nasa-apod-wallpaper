"""Set the desktop wallpaper on Windows, macOS and common Linux desktops."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class WallpaperError(Exception):
    pass


def set_wallpaper(image: Path) -> str:
    """Set `image` as wallpaper on every monitor. Returns the method used."""
    image = Path(image).resolve()
    if sys.platform == "win32":
        return _windows(image)
    if sys.platform == "darwin":
        return _macos(image)
    return _linux(image)


def _windows(image: Path) -> str:
    import ctypes

    SPI_SETDESKWALLPAPER, SPIF_UPDATEINIFILE, SPIF_SENDCHANGE = 20, 0x01, 0x02
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, str(image), SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)
    if not ok:
        raise WallpaperError("SystemParametersInfoW failed")
    return "windows"


def _macos(image: Path) -> str:
    # Needs a one-time "control System Events" permission prompt.
    script = ('tell application "System Events" to tell every desktop to set picture to '
              f"POSIX file {json.dumps(str(image))}")
    _run(["osascript", "-e", script])
    return "macos"


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise WallpaperError(f"{cmd[0]} failed: {(r.stderr or r.stdout).strip()}")


def _linux(image: Path) -> str:
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP", "") + ":"
               + os.environ.get("DESKTOP_SESSION", "")).lower()
    uri = image.as_uri()

    if "cosmic" in desktop:
        _cosmic(image)
        return "cosmic"
    if "kde" in desktop or "plasma" in desktop:
        _run(["plasma-apply-wallpaperimage", str(image)])
        return "kde"
    if "xfce" in desktop:
        _xfce(image)
        return "xfce"
    if "cinnamon" in desktop:
        _run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri])
        return "cinnamon"
    if "mate" in desktop:
        _run(["gsettings", "set", "org.mate.background", "picture-filename", str(image)])
        return "mate"
    if any(d in desktop for d in ("gnome", "unity", "budgie", "pantheon", "ubuntu")):
        _run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri])
        # GNOME 42+ uses a separate image in dark mode; older versions lack the key.
        subprocess.run(["gsettings", "set", "org.gnome.desktop.background",
                        "picture-uri-dark", uri], capture_output=True)
        _run(["gsettings", "set", "org.gnome.desktop.background", "picture-options", "zoom"])
        return "gnome"
    if shutil.which("feh") and os.environ.get("DISPLAY"):
        _run(["feh", "--bg-fill", str(image)])
        return "feh"
    raise WallpaperError(f"unsupported desktop: {desktop.strip(':') or 'unknown'}")


def _cosmic(image: Path) -> None:
    """cosmic-bg reloads its config files live.

    cosmic-bg 1.11+ keeps one wallpaper per theme mode and only watches the
    .Dark/.Light dirs; older versions read the unsuffixed dir. Write all three.
    """
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cosmic"
    ron = (
        "(\n"
        '    output: "all",\n'
        f"    source: Path({json.dumps(str(image))}),\n"
        "    filter_by_theme: false,\n"
        "    rotation_frequency: 3600,\n"
        "    transition_duration: 500,\n"
        "    filter_method: Lanczos,\n"
        "    scaling_mode: Zoom,\n"
        "    sampling_method: Alphanumeric,\n"
        ")"
    )
    for suffix in (".Dark", ".Light", ""):
        target = base / f"com.system76.CosmicBackground{suffix}" / "v1" / "all"
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".all.")
        with os.fdopen(fd, "w") as f:
            f.write(ron)
        os.replace(tmp, target)


def _xfce(image: Path) -> None:
    r = subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-l"],
                       capture_output=True, text=True)
    props = [p for p in r.stdout.split() if p.endswith("/last-image")]
    if not props:
        raise WallpaperError("no XFCE monitors found in xfconf")
    for prop in props:
        _run(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", str(image)])
