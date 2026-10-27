#!/usr/bin/env python3
"""
Station North SNfetchPLAYER - Platform & Hardware Detection Switch
===================================================================
Erkennt präzise:
1. Wo bin ich? (Handheld: ROCKNIX / dArkOS, ArkOS, EmuELEC vs. PC: Manjaro/Arch, Debian/Ubuntu)
2. Welches Dateisystem-Modell? (Read-Only SquashFS vs. Writable Distro)
3. Woher kommen Abhängigkeiten? (Bundled ARM64 pylib vs. OS-Packages)
4. Welche Audio- & Visualizer-Pipeline?
   - ROCKNIX / dArkOS: mpv (--ao=pulse,alsa) + parec PipeWire/PulseAudio Tap (Stand 5caae4d)
   - ArkOS / EmuELEC: Direkter ALSA Stream / FFmpeg
   - PC: System-FFmpeg mit 2-Kanal-Split ([out1] Soundkarte, [out2] Visualizer)
"""

import os
import sys
import platform
import shutil
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional

import glob

class PlatformType(Enum):
    ROCKNIX         = "ROCKNIX (RK3326 / SquashFS ro / Wayland + PipeWire)"
    DARKOS          = "dArkOS (RK3326 / Debian trixie / Direct ALSA)"
    ARKOS           = "ArkOS (Ubuntu-base / ext4 rw / Direct ALSA)"
    EMUELEC         = "EmuELEC (Buildroot / ro)"
    PC_ARCH_MANJARO = "PC Desktop (Arch / Manjaro Linux)"
    PC_DEBIAN_UBUNTU= "PC Desktop (Debian / Ubuntu / Mint)"
    PC_GENERIC      = "PC Desktop (Generic Linux / Other)"

class AudioPipeline(Enum):
    MPV_PAREC_TAP       = "mpv_pulse_with_parec_tap"       # ROCKNIX (Wayland + PipeWire)
    ALSA_DIRECT         = "alsa_direct"                    # ArkOS / EmuELEC
    FFMPEG_STDOUT_SPLIT = "ffmpeg_stdout_split"            # dArkOS / Desktop PC (Direct ALSA/PCM)

class PlatformProfile:
    def __init__(self):
        self.arch: str = platform.machine().lower()
        self.os_release: Dict[str, str] = self._read_os_release()
        self.cfw_name: str = os.environ.get("CFW_NAME", "").upper()
        self.is_immutable_root: bool = self._check_immutable_root()
        
        # 1. Hardware & Platform Category
        self.platform_type: PlatformType = self._detect_platform_type()
        self.is_handheld: bool = self.platform_type in (
            PlatformType.ROCKNIX,
            PlatformType.DARKOS,
            PlatformType.ARKOS,
            PlatformType.EMUELEC
        )
        self.is_pc: bool = not self.is_handheld

        # 2. Audio Pipeline Strategy
        self.audio_pipeline: AudioPipeline = self._detect_audio_pipeline()

        # 3. Hardware Controls & Sensors
        self.has_saradc_volume: bool = os.path.exists("/sys/bus/iio/devices/iio:device0/in_voltage2_raw")
        self.has_battery: bool = os.path.exists("/sys/class/power_supply/battery") or os.path.exists("/sys/class/power_supply/axp20x-battery")
        self.has_wifi_sysfs: bool = os.path.exists("/sys/class/net/wlan0/operstate")

        # 4. Dependency Loading Strategy
        has_system_pygame = False
        try:
            import pygame
            has_system_pygame = True
        except Exception:
            pass

        is_py311 = sys.version_info[:2] == (3, 11)
        self.should_use_bundled_pylib: bool = (
            self.is_handheld and 
            (self.arch in ("aarch64", "arm64")) and 
            is_py311 and 
            not has_system_pygame
        )

        # 5. Display Mode
        force_windowed = os.environ.get("SN_WINDOWED", "0") == "1"
        self.is_windowed: bool = force_windowed or self.is_pc

    def _read_os_release(self) -> Dict[str, str]:
        data = {}
        for path in ["/etc/os-release", "/usr/lib/os-release"]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if "=" in line and not line.startswith("#"):
                                k, v = line.split("=", 1)
                                data[k.strip()] = v.strip().strip('"').strip("'")
                    break
                except Exception:
                    pass
        return data

    def _check_immutable_root(self) -> bool:
        try:
            with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4 and parts[1] == "/":
                        fstype = parts[2]
                        opts = parts[3].split(",")
                        if fstype in ("squashfs", "erofs") or "ro" in opts:
                            return True
        except Exception:
            pass
        return False

    def _detect_platform_type(self) -> PlatformType:
        # A) Desktop PC check based on CPU architecture
        if self.arch in ("x86_64", "amd64", "i386"):
            distro_id = self.os_release.get("ID", "").lower()
            id_like = self.os_release.get("ID_LIKE", "").lower()
            if distro_id in ("manjaro", "arch") or "arch" in id_like:
                return PlatformType.PC_ARCH_MANJARO
            elif distro_id in ("ubuntu", "debian", "linuxmint", "pop") or "debian" in id_like:
                return PlatformType.PC_DEBIAN_UBUNTU
            return PlatformType.PC_GENERIC

        os_name = self.os_release.get("OS_NAME", "").upper()
        pretty_name = self.os_release.get("PRETTY_NAME", "").upper()
        distro_id = self.os_release.get("ID", "").lower()
        id_like = self.os_release.get("ID_LIKE", "").lower()
        hw_device = self.os_release.get("HW_DEVICE", "").upper()

        # B) ROCKNIX: Buildroot SquashFS with Wayland/Weston/Sway & PipeWire
        is_sway = os.path.exists("/storage/.config/sway") or bool(os.environ.get("SWAYSOCK")) or bool(os.environ.get("WAYLAND_DISPLAY"))
        if self.cfw_name == "ROCKNIX" or "ROCKNIX" in os_name or "ROCKNIX" in pretty_name or distro_id == "rocknix":
            return PlatformType.ROCKNIX
        if self.is_immutable_root and is_sway:
            return PlatformType.ROCKNIX

        # C) dArkOS: RK3326 Debian Trixie (Python 3.13), direct KMSDRM ALSA
        if (any(x in self.cfw_name for x in ("DARKOS", "DARKOS4CLONE", "DARKOSRE")) or
            "DARKOS" in os_name or "DARKOS" in pretty_name or
            os.path.exists("/opt/system/Tools/PortMaster/mod_dArkOS.txt") or
            os.path.exists("/opt/system/Tools/PortMaster/mod_dArkOSRE.txt") or
            os.path.exists("/etc/device_info_darkos.env") or
            bool(glob.glob("/opt/system/Tools/PortMaster/device_info_darkos*.env"))):
            return PlatformType.DARKOS

        if self.arch in ("aarch64", "arm64") and distro_id == "debian" and not self.is_immutable_root:
            return PlatformType.DARKOS

        # D) ArkOS: Ubuntu 19.10/20.04
        if self.cfw_name == "ARKOS" or os.path.exists("/usr/share/plymouth/themes/text.plymouth"):
            try:
                with open("/usr/share/plymouth/themes/text.plymouth", "r") as pf:
                    if "arkos" in pf.read().lower():
                        return PlatformType.ARKOS
            except Exception:
                pass
        if self.arch in ("aarch64", "armhf") and distro_id == "ubuntu" and not self.is_immutable_root:
            return PlatformType.ARKOS

        # E) EmuELEC
        if self.cfw_name == "EMUELEC" or distro_id == "emuelec" or "emuelec" in os_name.lower():
            return PlatformType.EMUELEC

        # Fallback Handheld wenn Controller-Device existiert
        if os.path.exists("/dev/input/by-path/platform-joypad-event-joystick") or os.path.exists("/sys/devices/platform/joypad"):
            if is_sway or self.is_immutable_root:
                return PlatformType.ROCKNIX
            return PlatformType.DARKOS

        return PlatformType.PC_GENERIC

    def _detect_audio_pipeline(self) -> AudioPipeline:
        # ROCKNIX mit PipeWire: Strikt MPV_PAREC_TAP (kein direktes ALSA!)
        if self.platform_type == PlatformType.ROCKNIX:
            return AudioPipeline.MPV_PAREC_TAP

        # dArkOS, ArkOS & PC: Standard ist direkter FFMPEG Split (sauberer 16-Bit PCM Stream)
        if shutil.which("ffmpeg"):
            return AudioPipeline.FFMPEG_STDOUT_SPLIT

        # Fallback wenn kein ffmpeg vorhanden ist
        if self.platform_type in (PlatformType.ARKOS, PlatformType.DARKOS, PlatformType.EMUELEC):
            return AudioPipeline.ALSA_DIRECT

        if shutil.which("parec"):
            return AudioPipeline.MPV_PAREC_TAP

        return AudioPipeline.FFMPEG_STDOUT_SPLIT

    def get_audio_env(self) -> Dict[str, str]:
        """Gibt saubere Umgebungsvariablen für PulseAudio / PipeWire zurück"""
        env = dict(os.environ)
        xdg = env.get("XDG_RUNTIME_DIR")
        if not xdg or not os.path.exists(xdg):
            for cand in ["/var/run/0-runtime-dir", "/run/0-runtime-dir", "/run/user/0", f"/run/user/{os.getuid()}"]:
                if os.path.exists(cand):
                    env["XDG_RUNTIME_DIR"] = cand
                    break
        if "XDG_RUNTIME_DIR" in env:
            pulse_sock = os.path.join(env["XDG_RUNTIME_DIR"], "pulse", "native")
            if os.path.exists(pulse_sock):
                env["PULSE_SERVER"] = f"unix:{pulse_sock}"
        return env

    def print_diagnostics(self):
        logging.info("=" * 60)
        logging.info("STATION NORTH • PLATFORM & HARDWARE PROFIL")
        logging.info("=" * 60)
        logging.info(f"Plattform-Typ:      {self.platform_type.value}")
        logging.info(f"CPU-Architektur:    {self.arch}")
        logging.info(f"Dateisystem:        {'Read-Only SquashFS (ro)' if self.is_immutable_root else 'Beschreibbar (rw)'}")
        logging.info(f"Audio-Pipeline:     {self.audio_pipeline.value}")
        logging.info(f"Abhängigkeiten:     {'Bundled ARM64 pylib/ (NEON SIMD)' if self.should_use_bundled_pylib else 'Natives System / Venv'}")
        logging.info(f"Hardware-Volume:    {'SARADC Channel 2' if self.has_saradc_volume else 'Standard Software/Mixer'}")
        logging.info(f"Anzeige-Modus:      {'Fenster (1024x768)' if self.is_windowed else 'KMSDRM Vollbild'}")
        logging.info("=" * 60)

# Singleton-Instanz
_CURRENT_PLATFORM: Optional[PlatformProfile] = None

def get_platform() -> PlatformProfile:
    global _CURRENT_PLATFORM
    if _CURRENT_PLATFORM is None:
        _CURRENT_PLATFORM = PlatformProfile()
    return _CURRENT_PLATFORM

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    p = get_platform()
    p.print_diagnostics()
