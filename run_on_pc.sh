#!/usr/bin/env bash
# ==============================================================================
# 👑 Station North SNfetchPLAYER • PC Suite Launcher & Environment Doctor
# Compatible with Ubuntu, Debian, Pop!_OS, Mint, Arch Linux, Manjaro, Fedora & openSUSE
# ==============================================================================

set -e

# Terminal colors (Nord-inspired palette)
BOLD='\033[1m'
NC='\033[0m'
NORD8='\033[38;2;136;192;208m'   # Cyan
NORD9='\033[38;2;129;161;193m'   # Glacial Blue
NORD14='\033[38;2;163;190;140m'  # Aurora Green
NORD13='\033[38;2;235;203;139m'  # Aurora Yellow
NORD11='\033[38;2;191;97;106m'   # Aurora Red

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${NORD8}${BOLD}========================================================================${NC}"
echo -e "${NORD8}${BOLD}   👑 STATION NORTH • SNfetchPLAYER PC SUITE LAUNCHER v7.0            ${NC}"
echo -e "${NORD9}      The Sovereign Cyberdeck & Retro Media Suite (PC Mode)            ${NC}"
echo -e "${NORD8}${BOLD}========================================================================${NC}"

# 1. Detect Operating System & Package Manager
DISTRO_NAME="Unknown Linux"
PKG_MGR=""
INSTALL_CMD=""

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_NAME="${NAME:-Linux}"
fi
echo -e "${NORD9}✦ Host System: ${BOLD}${DISTRO_NAME}${NC} ($(uname -m))"

if command -v apt-get >/dev/null 2>&1; then
    PKG_MGR="apt"
    INSTALL_CMD="sudo apt update && sudo apt install -y"
    SYS_PKG_DEPS="python3 python3-venv python3-pip mpv libmpv-dev ffmpeg curl alsa-utils"
elif command -v pacman >/dev/null 2>&1; then
    PKG_MGR="pacman"
    INSTALL_CMD="sudo pacman -S --needed --noconfirm"
    SYS_PKG_DEPS="python python-pip mpv ffmpeg curl alsa-utils"
elif command -v dnf >/dev/null 2>&1; then
    PKG_MGR="dnf"
    INSTALL_CMD="sudo dnf install -y"
    SYS_PKG_DEPS="python3 python3-pip mpv mpv-libs ffmpeg curl alsa-utils"
elif command -v zypper >/dev/null 2>&1; then
    PKG_MGR="zypper"
    INSTALL_CMD="sudo zypper install -y"
    SYS_PKG_DEPS="python3 python3-pip mpv libmpv-devel ffmpeg curl alsa-utils"
fi

# 2. Check System Tools & Libraries
MISSING_SYS_TOOLS=()

check_cmd() {
    local cmd="$1"
    local desc="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        echo -e "  [${NORD14}✓${NC}] System tool: ${BOLD}$cmd${NC} (${desc})"
    else
        echo -e "  [${NORD11}✗${NC}] System tool: ${BOLD}$cmd${NC} (${desc}) - ${NORD11}MISSING${NC}"
        MISSING_SYS_TOOLS+=("$cmd")
    fi
}

echo ""
echo -e "${NORD9}✦ Checking system prerequisites...${NC}"
check_cmd "python3" "Python 3 Runtime"
check_cmd "ffmpeg" "Audio/Video Stream Processing"
check_cmd "curl" "InnerTube TLS Stream Resolver"

# Check for mpv and libmpv library
if command -v mpv >/dev/null 2>&1; then
    echo -e "  [${NORD14}✓${NC}] Video engine: ${BOLD}mpv${NC} (Standalone player)"
else
    echo -e "  [${NORD11}✗${NC}] Video engine: ${BOLD}mpv${NC} - ${NORD11}MISSING${NC}"
    MISSING_SYS_TOOLS+=("mpv")
fi

# Check for libmpv shared library
HAS_LIBMPV=false
for lib_path in /usr/lib /usr/lib64 /usr/lib/*-linux-gnu /usr/local/lib; do
    if ls "$lib_path"/libmpv.so* >/dev/null 2>&1; then
        HAS_LIBMPV=true
        break
    fi
done

if [ "$HAS_LIBMPV" = true ]; then
    echo -e "  [${NORD14}✓${NC}] Native library: ${BOLD}libmpv${NC} (Hardware OpenGL Video Engine)"
else
    echo -e "  [${NORD13}!${NC}] Native library: ${BOLD}libmpv-dev${NC} (Optional: required for PyQt6 TV Companion)"
fi

# Prompt or install missing system tools
if [ ${#MISSING_SYS_TOOLS[@]} -gt 0 ]; then
    echo ""
    echo -e "${NORD13}${BOLD}⚠️  Missing system tools detected:${NC} ${MISSING_SYS_TOOLS[*]}"
    if [ -n "$PKG_MGR" ]; then
        echo -e "${NORD9}To install missing dependencies, run:${NC}"
        echo -e "  ${BOLD}${INSTALL_CMD} ${SYS_PKG_DEPS}${NC}"
        echo ""
        if [ -t 0 ]; then
            read -r -p "Would you like to install missing system packages now? [y/N] " response
            if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
                echo -e "${NORD8}Installing dependencies...${NC}"
                $INSTALL_CMD $SYS_PKG_DEPS
            fi
        fi
    fi
fi

# 3. Virtual Environment & Python Modules
VENV_DIR="$SCRIPT_DIR/.venv_pc"
if [ ! -d "$VENV_DIR" ]; then
    VENV_DIR="/tmp/snfetch_pc_venv"
fi

echo ""
echo -e "${NORD9}✦ Verifying Python runtime environment...${NC}"

# Check if current Python or venv has all needed packages
NEED_INSTALL=false
PYTHON_EXEC="python3"

check_py_modules() {
    "$1" -c "import pygame, numpy, yt_dlp, PIL" >/dev/null 2>&1
}

if check_py_modules "python3" 2>/dev/null; then
    PYTHON_EXEC="python3"
    echo -e "  [${NORD14}✓${NC}] Using system Python with pre-installed gaming packages."
else
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "  [${NORD13}📦${NC}] Creating dedicated virtual environment at ${VENV_DIR}..."
        python3 -m venv "$VENV_DIR" || {
            echo -e "${NORD11}Failed to create venv. Please run: sudo apt install python3-venv${NC}"
            exit 1
        }
        NEED_INSTALL=true
    fi
    PYTHON_EXEC="$VENV_DIR/bin/python3"
    
    if ! check_py_modules "$PYTHON_EXEC" 2>/dev/null; then
        NEED_INSTALL=true
    fi
fi

if [ "$NEED_INSTALL" = true ]; then
    echo -e "${NORD8}✦ Installing required Python libraries (pygame, numpy, yt-dlp, PyQt6, python-mpv, Pillow)...${NC}"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install pygame numpy yt-dlp Pillow requests
    # Try installing companion video engine packages (graceful fallback)
    "$VENV_DIR/bin/pip" install PyQt6 python-mpv 2>/dev/null || true
fi

echo -e "  [${NORD14}✓${NC}] Python packages verified and ready."

# 4. Display & Windowed Environment Variables
export SN_WINDOWED=1
if [ -z "$DISPLAY" ] && [ -n "$WAYLAND_DISPLAY" ]; then
    export SDL_VIDEODRIVER=wayland
else
    export SDL_VIDEODRIVER=x11
fi

echo ""
echo -e "${NORD14}${BOLD}🚀 Starting Station North SNfetchPLAYER PC Suite...${NC}"
echo -e "${NORD9}   Controls: Arrow Keys / D-Pad, [A]=Select, [B]=Back, [0]=Fullscreen TV, [ESC]=Deck${NC}"
echo -e "${NORD8}========================================================================${NC}"
echo ""

exec "$PYTHON_EXEC" -W ignore player.py "$@"
