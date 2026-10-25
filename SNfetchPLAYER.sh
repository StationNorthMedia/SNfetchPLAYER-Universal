#!/bin/bash
# PORTMASTER: SNfetchPLAYER.sh

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
else
  controlfolder="/roms/ports/PortMaster"
fi

source "$controlfolder/control.txt" 2>/dev/null || true
[ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt"
get_controls 2>/dev/null || true

GAMEDIR="/$directory/ports/snfetchplayer"
[ ! -d "$GAMEDIR" ] && GAMEDIR="/roms/ports/snfetchplayer"

cd "$GAMEDIR"

# -----------------------------------------------------------------------------
# 1. Auto-Registrierung in EmulationStation gamelist.xml (Cover & Beschreibung)
# -----------------------------------------------------------------------------
GAMELIST_XML="$(dirname "$GAMEDIR")/gamelist.xml"
NEEDS_RESTART_FILE="$GAMEDIR/.needs_es_restart"
rm -f "$NEEDS_RESTART_FILE"

if [ -f "$GAMELIST_XML" ] && [ -f "$GAMEDIR/gameinfo.xml" ]; then
  python3 -c "
import xml.etree.ElementTree as ET
try:
    g_tree = ET.parse('$GAMELIST_XML')
    g_root = g_tree.getroot()
    i_tree = ET.parse('$GAMEDIR/gameinfo.xml')
    i_game = i_tree.getroot().find('game')
    if i_game is not None:
        target = None
        for g in g_root.findall('game'):
            p = g.find('path')
            if p is not None and p.text and p.text.strip() in ('./SNfetchPLAYER.sh', 'SNfetchPLAYER.sh'):
                target = g
                break
        needs_reload = False
        if target is None:
            g_root.append(i_game)
            needs_reload = True
        else:
            for child in i_game:
                existing = target.find(child.tag)
                if existing is None or not existing.text:
                    if existing is None:
                        target.append(child)
                    else:
                        existing.text = child.text
                    needs_reload = True
        if needs_reload:
            g_tree.write('$GAMELIST_XML', encoding='utf-8', xml_declaration=True)
            open('$NEEDS_RESTART_FILE', 'w').close()
except Exception:
    pass
" 2>/dev/null || true
fi

# Logging aktivieren
> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1

# -----------------------------------------------------------------------------
# 2. Performance-Governor für volle Hardware-Power (CPU / GPU / Memory)
# -----------------------------------------------------------------------------
ORIG_CPU_GOV=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor 2>/dev/null)
ORIG_GPU_GOV=$(cat /sys/devices/platform/*gpu*/devfreq/*gpu*/governor 2>/dev/null)
ORIG_DMC_GOV=$(cat /sys/devices/platform/dmc/devfreq/dmc/governor 2>/dev/null)

for gov in /sys/devices/system/cpu/cpufreq/policy0/scaling_governor /sys/devices/platform/*gpu*/devfreq/*gpu*/governor /sys/devices/platform/dmc/devfreq/dmc/governor; do
  [ -f "$gov" ] && echo performance > "$gov" 2>/dev/null || true
done

# Sway Display Routing: MPV & Windows verlässlich auf DSI-1 (MIPI Panel) erzwingen
if [ -f "/storage/.config/sway/config" ]; then
  if ! grep -q 'app_id="mpv"' /storage/.config/sway/config 2>/dev/null; then
    sed -i 's/output DP-1 DSI-1/output DSI-1 DP-1/g' /storage/.config/sway/config 2>/dev/null || true
    cat << 'EOF' >> /storage/.config/sway/config
workspace 1 output DSI-1
for_window [app_id="mpv"] move to output DSI-1
for_window [app_id="mpv"] fullscreen enable
for_window [class="mpv"] move to output DSI-1
for_window [class="mpv"] fullscreen enable
EOF
    swaymsg reload 2>/dev/null || true
  fi
fi

# WLAN Power-Save & USB Autosuspend deaktivieren (verhindert Dongle-Abstürze)
if command -v iw >/dev/null 2>&1; then
  iw dev wlan0 set power_save off 2>/dev/null || true
fi
for p in /sys/bus/usb/devices/*/power/autosuspend; do
  echo -1 > "$p" 2>/dev/null || true
done
for c in /sys/bus/usb/devices/*/power/control; do
  echo on > "$c" 2>/dev/null || true
done

export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/var/run/0-runtime-dir}"
export SWAYSOCK="${SWAYSOCK:-/var/run/0-runtime-dir/sway-ipc.0.sock}"

# -----------------------------------------------------------------------------
# 3. Python-Interpreter ermitteln (Fast-Path: Natives System-Python bevorzugen)
# -----------------------------------------------------------------------------
PYTHON_EXE=""
IS_MOUNTED=0
runtime="python_3.11"
export python_dir="$HOME/python_3.11"

# A) Zuerst prüfen, ob System-Python bereits voll funktionsfähig mit Pygame & Hardware-Display ist
if command -v python3 >/dev/null 2>&1; then
  if python3 -c "import pygame; pygame.display.init(); pygame.font.init(); assert pygame.display.get_driver() != 'offscreen'" >/dev/null 2>&1; then
    PYTHON_EXE="$(command -v python3)"
    echo "Verwende natives System-Python mit Hardware-Display: $PYTHON_EXE"
  fi
fi

# B) Falls System-Python nicht verfügbar/kompatibel: PortMaster Runtime mounten
if [ -z "$PYTHON_EXE" ]; then
  mkdir -p "$python_dir"

  # Prüfen und automatischer Download via Harbourmaster (muOS, ROCKNIX, etc.)
  if [ -f "$controlfolder/harbourmaster" ]; then
    if [ ! -f "$controlfolder/libs/${runtime}.squashfs" ]; then
      $ESUDO "$controlfolder/harbourmaster" --quiet --no-check runtime_check "${runtime}.squashfs"
    fi
  fi

  if [ -f "$controlfolder/libs/${runtime}.squashfs" ] && [[ "$PM_CAN_MOUNT" != "N" ]]; then
    $ESUDO umount "$python_dir" 2>/dev/null || true
    if $ESUDO mount "$controlfolder/libs/${runtime}.squashfs" "$python_dir"; then
      IS_MOUNTED=1
    fi
  fi

  if [ "$IS_MOUNTED" -eq 1 ] && [ -f "$python_dir/bin/python3" ]; then
    source "$python_dir/bin/activate" 2>/dev/null || true
    export PYTHONHOME="$python_dir"
    export PYTHONPATH="$GAMEDIR/pylib"
    export LD_LIBRARY_PATH="/usr/lib:/usr/lib/aarch64-linux-gnu:$python_dir/libs:$LD_LIBRARY_PATH"

    if "$python_dir/bin/python3" -c "import pygame; pygame.display.init(); pygame.font.init(); assert pygame.display.get_driver() != 'offscreen'" >/dev/null 2>&1; then
      PYTHON_EXE="$python_dir/bin/python3"
      echo "Verwende PortMaster Python 3.11 Runtime: $PYTHON_EXE"
      pm_platform_helper "$PYTHON_EXE" 2>/dev/null || true
    else
      echo "Warnung: python_3.11 Runtime konnte Pygame/Display nicht initialisieren."
      if [[ "$PM_CAN_MOUNT" != "N" ]]; then
        $ESUDO umount "$python_dir" 2>/dev/null || true
        IS_MOUNTED=0
      fi
      unset PYTHONHOME
      unset PYTHONPATH
    fi
  fi
fi

# D) Fehlerbehandlung, falls keine lauffähige Umgebung existiert
if [ -z "$PYTHON_EXE" ]; then
  echo "FEHLER: Kein funktionsfähiger Python-Interpreter mit Pygame/Hardware-Display gefunden!"
  if type pm_message >/dev/null 2>&1; then
    pm_message "Fehler: Pygame-Laufzeitumgebung fehlt. Bitte PortMaster aktualisieren."
  fi
  sleep 5
  exit 1
fi

export HOME="$GAMEDIR"
export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"
export PYTHONPYCACHEPREFIX="$GAMEDIR/${runtime}.cache"

# -----------------------------------------------------------------------------
# 4. Gamepad-to-Keyboard Mapping starten
# -----------------------------------------------------------------------------
if [ -n "$GPTOKEYB" ]; then
  $GPTOKEYB "python3" -c "$GAMEDIR/snfetchplayer.gptk" &
fi

# Cursor ausblenden
printf "\033[?25l" > /dev/tty0 2>/dev/null || true

# -----------------------------------------------------------------------------
# 5. SNfetchPLAYER Applikation starten
# -----------------------------------------------------------------------------
"$PYTHON_EXE" "$GAMEDIR/player.py" "$@"

# -----------------------------------------------------------------------------
# 6. Aufräumen & sauber zurück zu EmulationStation
# -----------------------------------------------------------------------------
if [ -n "$ESUDOKILL" ]; then
  $ESUDOKILL $(pidof gptokeyb) 2>/dev/null || true
fi
printf "\033[?25h" > /dev/tty0 2>/dev/null || true

# Energiespar-Profile wiederherstellen
if [ -n "$ESUDO" ]; then
  [ -n "$ORIG_CPU_GOV" ] && echo "$ORIG_CPU_GOV" | $ESUDO tee /sys/devices/system/cpu/cpufreq/policy0/scaling_governor >/dev/null 2>&1 || true
  [ -n "$ORIG_GPU_GOV" ] && echo "$ORIG_GPU_GOV" | $ESUDO tee /sys/devices/platform/*gpu*/devfreq/*gpu*/governor >/dev/null 2>&1 || true
  [ -n "$ORIG_DMC_GOV" ] && echo "$ORIG_DMC_GOV" | $ESUDO tee /sys/devices/platform/dmc/devfreq/dmc/governor >/dev/null 2>&1 || true
fi

if [ "$IS_MOUNTED" -eq 1 ] && [[ "$PM_CAN_MOUNT" != "N" ]]; then
  $ESUDO umount "$python_dir" 2>/dev/null || true
fi

# Falls Metadaten neu in gamelist.xml registriert wurden, ES sanft neu starten
if [ -f "$NEEDS_RESTART_FILE" ]; then
  rm -f "$NEEDS_RESTART_FILE"
  touch /tmp/es-restart
  killall -9 emulationstation 2>/dev/null || true
  exit 0
fi

if type pm_finish >/dev/null 2>&1; then
  pm_finish
fi
