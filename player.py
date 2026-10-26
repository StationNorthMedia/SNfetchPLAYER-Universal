#!/usr/bin/env python3
"""
Station North SNfetchPLAYER - dArkOS Handheld Edition
Haupteinstiegspunkt:
Startet das interaktive Songo 5-Dashboard im Vollbild (1024x768 KMSDRM).
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
pylib_dir = str(APP_DIR / "pylib")
if pylib_dir not in sys.path:
    sys.path.insert(0, pylib_dir)

from ui_dashboard import SNfetchDashboard

def main():
    dashboard = SNfetchDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()
