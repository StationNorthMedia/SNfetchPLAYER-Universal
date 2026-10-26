#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prüfen, ob System-Python bereits pygame & numpy hat
if python3 -c "import pygame, numpy, yt_dlp" 2>/dev/null; then
    PYTHON_CMD="python3"
else
    VENV="/tmp/snfetch_pc_venv"
    if [ ! -d "$VENV" ]; then
        echo "📦 Erstelle PC-Umgebung..."
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install pygame numpy yt-dlp
    fi
    PYTHON_CMD="$VENV/bin/python3"
fi

echo "🚀 Starte Station North SNfetchPLAYER im PC-Fenstermodus..."
export SN_WINDOWED=1
export SDL_VIDEODRIVER=x11
cd "$DIR"
exec "$PYTHON_CMD" -W ignore player.py "$@"
