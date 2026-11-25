#!/usr/bin/env python3
"""Launcher used from source and as the PyInstaller entry point."""
import sys

from apod_wallpaper.cli import main

if __name__ == "__main__":
    sys.exit(main())
