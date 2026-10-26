#!/usr/bin/env python3
"""
Station North SNfetchPLAYER - dArkOS Handheld Edition
Haupteinstiegspunkt:
Startet das interaktive Songo 5-Dashboard im Vollbild (1024x768 KMSDRM).
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent

import logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")

from platform_detector import get_platform
platform_info = get_platform()
platform_info.print_diagnostics()

import os
if platform_info.is_pc:
    os.environ.setdefault("SDL_VIDEODRIVER", "x11")
if platform_info.is_handheld:
    os.environ.setdefault("SDL_RENDERER_DRIVER", "opengles2")

if platform_info.should_use_bundled_pylib:
    pylib_dir = str(APP_DIR / "pylib")
    if pylib_dir not in sys.path:
        sys.path.insert(0, pylib_dir)

from ui_dashboard import SNfetchDashboard

def main():
    dashboard = SNfetchDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()
