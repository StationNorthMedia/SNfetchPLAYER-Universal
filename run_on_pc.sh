#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV="/tmp/snfetch_pc_venv"
if [ ! -d "$VENV" ]; then
    echo "📦 Erstelle PC-Umgebung..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install pygame numpy yt-dlp
fi

echo "🚀 Starte Station North SNfetchPLAYER im PC-Fenstermodus..."
export SN_WINDOWED=1
cd "$DIR"
exec "$VENV/bin/python3" ui_dashboard.py "$@"
