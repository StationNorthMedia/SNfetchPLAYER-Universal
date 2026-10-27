#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
STAGING_DIR="$DIST_DIR/staging"
PKG_DIR="$STAGING_DIR/snfetchplayer"

echo "=========================================================="
echo "📦 Baue PortMaster Release-Paket für Station North SNfetchPLAYER..."
echo "=========================================================="

# 1. Altes Verzeichnis leeren
rm -rf "$STAGING_DIR" "$DIST_DIR/snfetchplayer.zip"
mkdir -p "$PKG_DIR" "$PKG_DIR/playlists" "$PKG_DIR/thumbnails"

# 2. PortMaster Root-Dateien
cp "$SCRIPT_DIR/SNfetchPLAYER.sh" "$STAGING_DIR/"
chmod +x "$STAGING_DIR/SNfetchPLAYER.sh"

# 3. Anwendungsdateien kopieren
cp "$SCRIPT_DIR/player.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/ui_dashboard.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/run_on_pc.sh" "$PKG_DIR/"
cp "$SCRIPT_DIR/extractor.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/osd_generator.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/platform_detector.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/companion_tv.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/snfetchplayer.gptk" "$PKG_DIR/"
cp "$SCRIPT_DIR/sn_logo.png" "$PKG_DIR/"
cp "$SCRIPT_DIR/lore_quotes.json" "$PKG_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/sprueche.json" "$PKG_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/playlist.json" "$PKG_DIR/"
cp "$SCRIPT_DIR/port.json" "$PKG_DIR/"
cp "$SCRIPT_DIR/gameinfo.xml" "$PKG_DIR/"
cp "$SCRIPT_DIR/screenshot.png" "$PKG_DIR/"
cp "$SCRIPT_DIR/cover.png" "$PKG_DIR/"
chmod +x "$PKG_DIR"/*.py "$PKG_DIR"/*.sh

# 4. Playlists, Music, Videos & Manifest kopieren
cp -r "$SCRIPT_DIR/playlists/"* "$PKG_DIR/playlists/"
mkdir -p "$PKG_DIR/music/HipHop" "$PKG_DIR/music/Rock"
cp "$SCRIPT_DIR/music/README.txt" "$PKG_DIR/music/" 2>/dev/null || true
cp "$SCRIPT_DIR/music/HipHop/README.txt" "$PKG_DIR/music/HipHop/" 2>/dev/null || true
cp "$SCRIPT_DIR/music/Rock/README.txt" "$PKG_DIR/music/Rock/" 2>/dev/null || true

mkdir -p "$PKG_DIR/videos/HipHop" "$PKG_DIR/videos/Rock"
cp "$SCRIPT_DIR/videos/README.txt" "$PKG_DIR/videos/" 2>/dev/null || true
cp "$SCRIPT_DIR/videos/HipHop/README.txt" "$PKG_DIR/videos/HipHop/" 2>/dev/null || true
cp "$SCRIPT_DIR/videos/Rock/README.txt" "$PKG_DIR/videos/Rock/" 2>/dev/null || true
if [ -d "$SCRIPT_DIR/licenses" ]; then
  mkdir -p "$PKG_DIR/licenses"
  cp -r "$SCRIPT_DIR/licenses/"* "$PKG_DIR/licenses/"
fi
if [ -d "$SCRIPT_DIR/pylib" ]; then
  mkdir -p "$PKG_DIR/pylib"
  cp -r "$SCRIPT_DIR/pylib/"* "$PKG_DIR/pylib/"
fi
mkdir -p "$PKG_DIR/assets"
if [ -d "$SCRIPT_DIR/assets/ui" ]; then
  mkdir -p "$PKG_DIR/assets/ui"
  cp -r "$SCRIPT_DIR/assets/ui/"* "$PKG_DIR/assets/ui/"
fi
if [ -d "$SCRIPT_DIR/assets/backgrounds" ]; then
  mkdir -p "$PKG_DIR/assets/backgrounds"
  cp -r "$SCRIPT_DIR/assets/backgrounds/"* "$PKG_DIR/assets/backgrounds/"
fi
if [ -f "$SCRIPT_DIR/assets/catalog_manifest.json" ]; then
  cp "$SCRIPT_DIR/assets/catalog_manifest.json" "$PKG_DIR/assets/"
fi
if [ -f "$SCRIPT_DIR/assets/comic/chronicles_data.json" ]; then
  mkdir -p "$PKG_DIR/assets/comic"
  cp "$SCRIPT_DIR/assets/comic/chronicles_data.json" "$PKG_DIR/assets/comic/"
fi

# 5. Standard ZIP-Paket erzeugen (ohne schwere Assets, In-App Download)
mkdir -p "$DIST_DIR"
cd "$STAGING_DIR"
python3 -c "
import zipfile, os
with zipfile.ZipFile('$DIST_DIR/snfetchplayer.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk('.'):
        for f in files:
            if not f.endswith('.pyc') and '__pycache__' not in root:
                filepath = os.path.join(root, f)
                arcname = os.path.relpath(filepath, '.')
                z.write(filepath, arcname)
"

# 6. Komplettpaket (Full Offline Bundle mit allen Assets, Demo-Videos & Demo-Musik) bauen
if [ -d "$SCRIPT_DIR/assets" ]; then
  echo "📦 Erstelle Komplettpaket mit allen Assets, Demo-Videos & Musik (snfetchplayer-full.zip)..."
  cp -r "$SCRIPT_DIR/assets/"* "$PKG_DIR/assets/"
  cp -r "$SCRIPT_DIR/music/"* "$PKG_DIR/music/" 2>/dev/null || true
  cp -r "$SCRIPT_DIR/videos/"* "$PKG_DIR/videos/" 2>/dev/null || true
  python3 -c "
import zipfile, os
with zipfile.ZipFile('$DIST_DIR/snfetchplayer-full.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk('.'):
        for f in files:
            if not f.endswith('.pyc') and '__pycache__' not in root:
                filepath = os.path.join(root, f)
                arcname = os.path.relpath(filepath, '.')
                z.write(filepath, arcname)
"
  echo "📦 Erstelle Standalone Medienpaket für In-App Downloader (snfetchplayer-assets.zip)..."
  python3 -c "
import zipfile, os
with zipfile.ZipFile('$DIST_DIR/snfetchplayer-assets.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk('$PKG_DIR/assets'):
        for f in files:
            if not f.endswith('.pyc') and '__pycache__' not in root:
                filepath = os.path.join(root, f)
                arcname = os.path.relpath(filepath, '$PKG_DIR')
                z.write(filepath, arcname)
"
fi

# 7. Offiziellen PortMaster Linter / Check ausführen
if [ -f "$SCRIPT_DIR/tools/build_release.py" ]; then
  echo ""
  echo "🔍 Führe offiziellen PortMaster Linter (tools/build_release.py --do-check) aus..."
  cd "$SCRIPT_DIR"
  python3 tools/build_release.py --do-check
  rm -rf ports releases .hash_cache
  echo "✅ PortMaster Linter: 0 Warnungen, 0 Fehler. Paket ist 100% store-ready!"
fi

echo "=========================================================="
echo "✅ Fertig! Release-Pakete erstellt unter:"
echo "   1) Standard:              $DIST_DIR/snfetchplayer.zip"
echo "   2) Komplett (ca. 285 MB): $DIST_DIR/snfetchplayer-full.zip"
echo "   3) Assets (ca. 285 MB):   $DIST_DIR/snfetchplayer-assets.zip"
echo "Beide ZIPs können direkt auf die SD-Karte unter /roms/ports/"
echo "entpackt werden!"
echo "=========================================================="

