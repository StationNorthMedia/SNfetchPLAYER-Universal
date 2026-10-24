#!/bin/bash
set -e

REPO_NAME="${1:-SNfetchPLAYER-Universal}"
ORG="StationNorthMedia"
TARGET_URL="https://github.com/${ORG}/${REPO_NAME}.git"

echo "=========================================================="
echo "🚀 GitHub Publisher: Station North SNfetchPLAYER"
echo "Ziel: $TARGET_URL"
echo "=========================================================="

# 1. Prüfen, ob ~/.env existiert und GITHUB_TOKEN laden
if [ -f "$HOME/.env" ]; then
    eval $(grep '^GITHUB_TOKEN=' "$HOME/.env")
fi

# 2. Prüfen, ob Remote bereits existiert
if git remote | grep -q "^origin$"; then
    git remote set-url origin "$TARGET_URL"
else
    git remote add origin "$TARGET_URL"
fi

# 2. Release-ZIP aktualisieren
./build_portmaster_package.sh

echo ""
echo "----------------------------------------------------------"
if [ -z "$GITHUB_TOKEN" ]; then
    read -s -p "Bitte GitHub Personal Access Token eingeben (Eingabe bleibt unsichtbar): " GITHUB_TOKEN
    echo ""
fi

echo "Übertrage Branch 'main' und Tag 'v4.0.0' nach GitHub..."
git push -u "https://${GITHUB_TOKEN}@github.com/${ORG}/${REPO_NAME}.git" main --tags

echo ""
echo "=========================================================="
echo "✅ Quellcode & Tags erfolgreich auf GitHub übertragen!"
echo "Du kannst jetzt das Release-Paket anhängen:"
echo "👉 https://github.com/${ORG}/${REPO_NAME}/releases/new"
echo "Lade dort die Datei hoch:"
echo "📁 $(pwd)/dist/snfetchplayer.zip"
echo "=========================================================="
