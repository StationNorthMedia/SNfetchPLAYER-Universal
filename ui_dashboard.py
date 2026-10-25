#!/usr/bin/env python3
"""
Station North SNfetchPLAYER - dArkOS Handheld Edition v5.0 (Nord Master Edition)
Authentic 4-Pillar Multimedia & Broadcast Engine:
1. Splash Screen: Mode portal with live asset statistics and instant loading feedback.
2. Radio Mode: High-Fidelity Studio Dashboard with 340x340 Album Art, Live 32-Band FFT Visualizer,
   5-Button Pastel Cockpit, Up-Next Broadcast Preview, and Queen's Directive Lore.
3. TV Mode: 4:3 Display Fill for retro YouTube videos, 65% logo watermark, uninterrupted playback,
   and floating 5-button OSD appearing only on manual user interactions.
4. The Chronicles: Audiovisual Comic & Voice Narration (Comic panel on left, Narrative + Audio on right).
5. Settings & Extraction Engine: Playlist selection, ALSA / Backlight sliders, and system diagnostics.

Unified Controls (Front Buttons Only):
- [A] / [Start] = Confirm / Play / Pause
- [B]           = Back / Exit to Main Menu
- [X]           = Fullscreen TV Toggle (Mint nord7)
- [Y]           = Repeat / Loop Current Song Toggle (Gold nord13)
- [◄/►]         = Previous / Next Song Skip (Peach nord12 / Lavender nord15)
- [▲/▼]         = Navigation
- [Select]      = Settings Menu
"""

import sys
import os
import json
import time
import math
import random
import threading
import subprocess
import signal
import shutil
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Optional, Tuple

APP_DIR = Path(__file__).resolve().parent

# Initialize Pygame with CFW default audio driver
import pygame

pygame.display.init()
pygame.font.init()
# PortMaster uses gptokeyb to map gamepad buttons to keyboard keys.
# We block all raw joystick events in Pygame to prevent duplicate/conflicting inputs.
pygame.event.set_blocked([
    pygame.JOYAXISMOTION,
    pygame.JOYBALLMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBUTTONDOWN,
    pygame.JOYBUTTONUP,
])

DISPLAY_FLAGS = pygame.FULLSCREEN | getattr(pygame, "SCALED", 0)

from extractor import get_stream
from osd_generator import generate_osd_ass

# =============================================================================
# ARCTIC ICE & NORD DESIGN SYSTEM (OFFICIAL SPECIFICATION)
# =============================================================================
# Polar Night (Dark Base Surfaces)
NORD0 = (46, 52, 64)       # #2e3440 - Base App Background
NORD1 = (59, 66, 82)       # #3b4252 - Elevated Cards, Panels & Modals
NORD2 = (67, 76, 94)       # #434c5e - Card Borders, Outlines & Subtle Dividers
NORD3 = (76, 86, 106)      # #4c566a - Inconspicuous Elements & Guides

# Snow Storm (Text & Typography)
NORD4 = (216, 222, 233)    # #d8dee9 - Body Text & Secondary Labels
NORD5 = (229, 233, 240)    # #e5e9f0 - Elevated Body Text
NORD6 = (236, 239, 244)    # #eceff4 - Prominent Headlines, Titles & Snow White

# Frost (Arctic Water Accents)
NORD7 = (143, 188, 187)    # #8fbcbb - Frozen Polar Water / Mint (Button 1: Fullscreen [X])
NORD8 = (136, 192, 208)    # #88c0d0 - Station North Clear Ice Cyan (Primary Accent)
NORD9 = (129, 161, 193)    # #81a1c1 - Arctic Waters Blue (Button 3: Play/Pause [Start])
NORD10 = (94, 129, 172)    # #5e81ac - Deep Arctic Ocean Blue

# Aurora (Highlights & Status)
NORD11 = (191, 97, 106)    # #bf616a - Error / Offline / Low Battery Red
NORD12 = (208, 135, 112)   # #d08770 - Aurora Peach / Terracotta (Button 2: Prev Track [◄])
NORD13 = (235, 203, 139)   # #ebcb8b - Aurora Gold / Amber (Button 5: Repeat Track Toggle [Y])
NORD14 = (163, 190, 140)   # #a3be8c - Aurora Green / Live On Air / Battery Good
NORD15 = (180, 142, 173)   # #b48ead - Aurora Lavender / Purple (Button 4: Next Track [►])

# Aurora Randomized Color Palette & Quote Class Mapping
AURORA_PALETTE = [NORD11, NORD12, NORD13, NORD14, NORD15, NORD7, NORD8, NORD9]
SPRUECHE_CLASS_MAP = {
    "radio-red": NORD11,
    "radio-orange": NORD12,
    "radio-yellow": NORD13,
    "radio-green": NORD14,
    "radio-purple": NORD15,
}

# Aliases for compatibility
COLOR_BG            = NORD0
COLOR_BAR_BG        = (36, 41, 51)
COLOR_CARD_BG       = NORD0
COLOR_CARD_SURFACE  = NORD1
COLOR_CARD_BORDER   = NORD2
COLOR_SELECTION     = NORD1
COLOR_TEXT_SNOW     = NORD6
COLOR_TEXT_FROST    = NORD9
COLOR_TEXT_MUTED    = NORD4
COLOR_ACCENT_CYAN   = NORD8
COLOR_ACCENT_TEAL   = NORD7
COLOR_ACCENT_GOLD   = NORD13
COLOR_ACCENT_GREEN  = NORD14
COLOR_ACCENT_RED    = NORD11

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768

# Core States
STATE_SPLASH       = 0
STATE_RADIO        = 1
STATE_TV           = 2
STATE_CHRONICLES   = 3
STATE_SETTINGS     = 4

# =============================================================================
# PERSISTENT SHUFFLE & QUEUE MANAGER (TRUE RANDOMIZATION & REPEAT LOOP)
# =============================================================================
class ShuffleQueueManager:
    """Manages non-repeating shuffle queues across sessions and handles single-track repeat"""
    def __init__(self, state_file: str = "shuffle_state.json"):
        self.state_file = APP_DIR / state_file
        self.is_repeat_mode: bool = False
        self.shuffle_queue: List[int] = []
        self.history: List[int] = []
        self.total_playlist_len: int = 0
        self.current_playlist_id: str = "default"

    def init_playlist(self, playlist_len: int, playlist_id: str = "default"):
        self.total_playlist_len = playlist_len
        self.current_playlist_id = playlist_id
        saved = self._load_state()

        if saved and saved.get("playlist_id") == playlist_id and saved.get("queue"):
            self.shuffle_queue = [x for x in saved["queue"] if x < playlist_len]
            self.history = [x for x in saved.get("history", []) if x < playlist_len]
            self.is_repeat_mode = saved.get("repeat", False)
            if not self.shuffle_queue:
                self.reshuffle()
        else:
            self.reshuffle()

    def reshuffle(self):
        if self.total_playlist_len <= 0:
            self.shuffle_queue = [0]
            return
        deck = list(range(self.total_playlist_len))
        random.shuffle(deck)
        self.shuffle_queue = deck
        self.history = []
        self._save_state()

    def get_current_idx(self) -> int:
        if not self.shuffle_queue:
            self.reshuffle()
        return self.shuffle_queue[0] if self.shuffle_queue else 0

    def get_up_next_idx(self) -> Optional[int]:
        if self.is_repeat_mode:
            return self.get_current_idx()
        if len(self.shuffle_queue) > 1:
            return self.shuffle_queue[1]
        return None

    def advance_next(self) -> int:
        """Advances to next random track in queue, or stays on current track if repeat is on"""
        if self.is_repeat_mode:
            return self.get_current_idx()
        if self.shuffle_queue:
            played = self.shuffle_queue.pop(0)
            self.history.append(played)
        if not self.shuffle_queue:
            self.reshuffle()
        self._save_state()
        return self.get_current_idx()

    def step_prev(self) -> int:
        """Returns to previously played track from history"""
        if self.history:
            prev = self.history.pop()
            self.shuffle_queue.insert(0, prev)
            self._save_state()
            return prev
        return self.get_current_idx()

    def advance_previous(self) -> int:
        """Alias for step_prev to advance to previous track"""
        return self.step_prev()

    def toggle_repeat(self) -> bool:
        self.is_repeat_mode = not self.is_repeat_mode
        self._save_state()
        return self.is_repeat_mode

    def _save_state(self):
        try:
            data = {
                "playlist_id": self.current_playlist_id,
                "queue": self.shuffle_queue,
                "history": self.history[-50:],
                "repeat": self.is_repeat_mode
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _load_state(self) -> Optional[Dict]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

# =============================================================================
# SYSTEM TELEMETRY & HARDWARE MANAGER
# =============================================================================
class HardwareManager:
    @staticmethod
    def get_battery_info() -> Tuple[int, bool]:
        cap_file = Path("/sys/class/power_supply/battery/capacity")
        stat_file = Path("/sys/class/power_supply/battery/status")
        capacity = 85
        is_charging = False
        if cap_file.exists():
            try:
                capacity = int(cap_file.read_text().strip())
            except Exception:
                pass
        if stat_file.exists():
            try:
                is_charging = "charging" in stat_file.read_text().strip().lower()
            except Exception:
                pass
        return capacity, is_charging

    @staticmethod
    def get_wifi_status() -> bool:
        wlan_file = Path("/sys/class/net/wlan0/operstate")
        if wlan_file.exists():
            try:
                return "up" in wlan_file.read_text().strip().lower()
            except Exception:
                pass
        return True

    @staticmethod
    def get_time_str() -> str:
        return time.strftime("%H:%M")

    @staticmethod
    def get_master_volume() -> int:
        try:
            res = subprocess.run(["amixer", "sget", "Playback"], capture_output=True, text=True, timeout=1)
            for line in res.stdout.splitlines():
                if "[" in line and "%]" in line:
                    part = line.split("[")[1].split("%]")[0]
                    return int(part)
        except Exception:
            pass
        return 80

    @staticmethod
    def set_master_volume(pct: int):
        pct = max(0, min(100, pct))
        try:
            subprocess.run(["amixer", "sset", "Playback", f"{pct}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @staticmethod
    def get_brightness() -> int:
        b_file = Path("/sys/class/backlight/backlight/brightness")
        m_file = Path("/sys/class/backlight/backlight/max_brightness")
        if b_file.exists() and m_file.exists():
            try:
                curr = int(b_file.read_text().strip())
                max_b = int(m_file.read_text().strip())
                return int((curr / max_b) * 100)
            except Exception:
                pass
        return 75

    @staticmethod
    def set_brightness(pct: int):
        pct = max(10, min(100, pct))
        b_file = Path("/sys/class/backlight/backlight/brightness")
        m_file = Path("/sys/class/backlight/backlight/max_brightness")
        if b_file.exists() and m_file.exists():
            try:
                max_b = int(m_file.read_text().strip())
                val = int((pct / 100.0) * max_b)
                b_file.write_text(str(val))
            except Exception:
                pass

# =============================================================================
# INTEGRATED 32-BAND FFT VISUALIZER
# =============================================================================
try:
    import numpy as np
except ImportError:
    np = None

class IntegratedVisualizer:
    def __init__(self, num_bars: int = 40):
        self.num_bars = num_bars
        self.heights = [14.0] * num_bars
        self.target_heights = [14.0] * num_bars
        self.last_update = time.time()
        self.has_real_audio = False
        self.last_audio_feed = 0.0
        self.peak_energy = 15000.0  # Adaptiver Dynamik-Baseline-Wert (AGC)

    def feed_pcm(self, pcm_bytes: bytes):
        """Processes raw 16-bit PCM mono 22050Hz chunk and computes balanced 40-band spectrum"""
        if not pcm_bytes or len(pcm_bytes) < 256:
            return

        if np is not None:
            try:
                samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
                n = len(samples)
                window = np.hanning(n)
                fft_vals = np.abs(np.fft.rfft(samples * window))
                num_bins = len(fft_vals)
                if num_bins >= self.num_bars:
                    indices = np.logspace(0, np.log10(num_bins - 1), self.num_bars + 1).astype(int)
                    raw_bands = []
                    for i in range(self.num_bars):
                        start = indices[i]
                        end = max(start + 1, indices[i+1])
                        tilt = 1.0 + (i / float(self.num_bars)) * 3.5
                        raw_val = float(np.mean(fft_vals[start:end])) * tilt
                        raw_bands.append(raw_val)

                    max_in_frame = max(raw_bands) if raw_bands else 1.0
                    if max_in_frame > self.peak_energy:
                        self.peak_energy = self.peak_energy * 0.75 + max_in_frame * 0.25
                    else:
                        self.peak_energy = max(2000.0, self.peak_energy * 0.965 + max_in_frame * 0.035)

                    bands = []
                    for raw_val in raw_bands:
                        ratio = min(1.0, max(0.0, raw_val / max(1.0, self.peak_energy)))
                        curve = ratio ** 0.6
                        h = 14.0 + 185.0 * curve
                        bands.append(h)

                    self.target_heights = bands
                    self.has_real_audio = True
                    self.last_audio_feed = time.time()
                    return
            except Exception:
                pass

        # Zero-dependency Fallback (struct) when numpy is missing
        try:
            sample_count = len(pcm_bytes) // 2
            samples = struct.unpack(f"<{sample_count}h", pcm_bytes[:sample_count * 2])
            if not samples:
                return

            total_abs = sum(abs(s) for s in samples)
            avg_amp = total_abs / float(sample_count)
            if avg_amp < 10.0:
                return

            step = max(1, sample_count // self.num_bars)
            raw_bands = []
            for i in range(self.num_bars):
                chunk = samples[i * step : (i + 1) * step]
                if chunk:
                    chunk_amp = sum(abs(s) for s in chunk) / float(len(chunk))
                    tilt = 1.0 + (i / float(self.num_bars)) * 2.0
                    raw_bands.append(chunk_amp * tilt)
                else:
                    raw_bands.append(avg_amp)

            max_in_frame = max(raw_bands) if raw_bands else 1.0
            if max_in_frame > self.peak_energy:
                self.peak_energy = self.peak_energy * 0.75 + max_in_frame * 0.25
            else:
                self.peak_energy = max(1000.0, self.peak_energy * 0.965 + max_in_frame * 0.035)

            bands = []
            for raw_val in raw_bands:
                ratio = min(1.0, max(0.0, raw_val / max(1.0, self.peak_energy)))
                curve = ratio ** 0.6
                h = 14.0 + 185.0 * curve
                bands.append(h)

            self.target_heights = bands
            self.has_real_audio = True
            self.last_audio_feed = time.time()
        except Exception:
            pass

    def update(self, is_active: bool = True):
        now = time.time()
        dt = now - self.last_update
        self.last_update = now

        # 1. Real FFT spectrum (active when raw PCM chunk was fed within last 0.35s)
        if is_active and self.has_real_audio and (now - self.last_audio_feed) < 0.35:
            for i in range(self.num_bars):
                # Snappy attack, smooth decay
                if self.target_heights[i] > self.heights[i]:
                    self.heights[i] += (self.target_heights[i] - self.heights[i]) * min(1.0, dt * 26.0)
                else:
                    self.heights[i] += (self.target_heights[i] - self.heights[i]) * min(1.0, dt * 11.0)
        elif is_active:
            # 2. Dynamic Procedural Rhythmic Spectrum (when playing via mpv/native sink without PCM tap)
            self._update_procedural(now, dt)
        else:
            # 3. Idle gentle decay to baseline (14.0 px)
            for i in range(self.num_bars):
                self.heights[i] += (14.0 - self.heights[i]) * min(1.0, dt * 6.0)

    def _update_procedural(self, now: float, dt: float):
        # Base tempo: ~124 BPM (2.066 Hz)
        tempo = 2.066
        phase = now * tempo * 2.0 * math.pi
        
        # Beat pulses: primary kick on beat, snare on offbeat
        beat_kick = max(0.0, math.sin(phase)) ** 3.0
        beat_snare = max(0.0, math.sin(phase + math.pi * 0.5)) ** 4.0
        
        for i in range(self.num_bars):
            norm_i = i / float(self.num_bars)
            
            # Bass wave (bars 0-10)
            if norm_i < 0.25:
                # Strong punch on beat_kick + low bass oscillation
                wave = beat_kick * 0.85 + 0.15 * math.sin(now * 3.7 + i * 0.4)
                target = 25.0 + 175.0 * max(0.0, wave)
            # Low-mid wave (bars 10-20)
            elif norm_i < 0.50:
                wave = beat_snare * 0.65 + 0.35 * math.sin(now * 5.2 + i * 0.3)
                target = 20.0 + 150.0 * max(0.0, wave)
            # High-mid wave (bars 20-30)
            elif norm_i < 0.75:
                wave = 0.5 * math.sin(now * 7.1 + i * 0.5) + 0.3 * math.cos(now * 4.3 - i * 0.2) + 0.2 * beat_kick
                target = 18.0 + 130.0 * max(0.0, wave)
            # Treble wave (bars 30-39)
            else:
                # Fast hi-hat / cymbal shimmer
                wave = 0.45 * math.sin(now * 11.3 + i * 0.7) + 0.35 * math.sin(now * 17.1 + i * 0.9) + 0.2 * beat_snare
                target = 16.0 + 110.0 * max(0.0, wave)
            
            # Subtle pseudo-random micro-jitter based on bar index & time
            jitter = (math.sin(now * 19.7 + i * 13.3) * 0.5 + 0.5) * 15.0
            target = max(14.0, min(210.0, target + jitter))
            
            # Responsive attack / decay
            if target > self.heights[i]:
                self.heights[i] += (target - self.heights[i]) * min(1.0, dt * 22.0)
            else:
                self.heights[i] += (target - self.heights[i]) * min(1.0, dt * 10.0)


    def draw(self, surface: pygame.Surface, x: int, y: int, width: int, max_h: int = 220):
        bar_gap = 7
        total_gaps = (self.num_bars - 1) * bar_gap
        bar_w = max(6, int((width - total_gaps) / self.num_bars))
        scale = max_h / 220.0

        for i in range(self.num_bars):
            bx = x + i * (bar_w + bar_gap)
            bh = int(min(max_h, self.heights[i] * scale))
            by = y + max_h - bh

            # Pill bar body (Arctic slate-blue pill matching mockup)
            bar_col = (112, 146, 176)
            pygame.draw.rect(surface, bar_col, (bx, by, bar_w, bh), border_radius=bar_w // 2)

            # Cap / Bead color across spectrum (Green -> Gold -> Peach -> Red)
            ratio = i / float(self.num_bars)
            if ratio < 0.25:
                cap_col = NORD14 # Green (Bass)
            elif ratio < 0.50:
                cap_col = NORD13 # Gold/Amber (Mid-Low)
            elif ratio < 0.75:
                cap_col = NORD12 # Peach (Mid-High)
            else:
                cap_col = NORD11 # Red (Treble)

            # Bead circle right on top of pill
            cap_radius = bar_w // 2 + 1
            cap_cx = bx + bar_w // 2
            cap_cy = by
            pygame.draw.circle(surface, cap_col, (cap_cx, cap_cy), cap_radius)

# =============================================================================
# THUMBNAIL CACHE & GENERATOR
# =============================================================================
class ThumbnailManager:
    def __init__(self, default_size=(340, 340)):
        self.default_size = default_size
        self.cache: Dict[Tuple[str, int, int], pygame.Surface] = {}
        self.lock = threading.Lock()

    def get_thumbnail(self, youtube_id: str, title: str, size: Optional[Tuple[int, int]] = None) -> pygame.Surface:
        sz = size or self.default_size
        cache_key = (youtube_id, sz[0], sz[1])
        with self.lock:
            if cache_key in self.cache:
                return self.cache[cache_key]

        candidate_paths = [
            APP_DIR / f"thumbnails/{youtube_id}.jpg",
            Path(f"thumbnails/{youtube_id}.jpg"),
            Path(f"/tmp/sn_thumb_{youtube_id}.jpg")
        ]

        for p in candidate_paths:
            if p.exists():
                try:
                    raw = pygame.image.load(str(p))
                    surf = raw.convert() if pygame.display.get_surface() else raw
                    w, h = surf.get_size()
                    target_ratio = sz[0] / float(sz[1])
                    src_ratio = w / float(h)
                    if src_ratio > target_ratio:
                        new_w = int(h * target_ratio)
                        cx = (w - new_w) // 2
                        cropped = surf.subsurface((cx, 0, new_w, h))
                    else:
                        new_h = int(w / target_ratio)
                        cy = (h - new_h) // 2
                        cropped = surf.subsurface((0, cy, w, new_h))
                    scaled = pygame.transform.smoothscale(cropped, sz)
                    res = self._round_corners(scaled, radius=16, size=sz)
                    with self.lock:
                        self.cache[cache_key] = res
                    return res
                except Exception:
                    pass

        threading.Thread(target=self._fetch_thumb, args=(youtube_id,), daemon=True).start()
        return self._create_placeholder(title, size=sz)

    def _fetch_thumb(self, youtube_id: str):
        local_path = APP_DIR / f"thumbnails/{youtube_id}.jpg"
        if not local_path.parent.exists():
            local_path = Path(f"/tmp/sn_thumb_{youtube_id}.jpg")
        url = f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg"
        try:
            subprocess.run(["curl", "-s", "-L", url, "-o", str(local_path)], timeout=5)
        except Exception:
            pass

    def _round_corners(self, surf: pygame.Surface, radius: int, size: Tuple[int, int]) -> pygame.Surface:
        mask = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, *size), border_radius=radius)
        res = surf.copy().convert_alpha()
        res.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return res

    def _create_placeholder(self, title: str, size: Tuple[int, int]) -> pygame.Surface:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(surf, NORD1, (0, 0, *size), border_radius=14)
        pygame.draw.rect(surf, NORD2, (0, 0, *size), width=2, border_radius=14)

        cx, cy = size[0] // 2, size[1] // 2
        for r in range(25, min(size) // 2, 20):
            pygame.draw.circle(surf, NORD2, (cx, cy), r, width=1)

        pygame.draw.circle(surf, NORD0, (cx, cy), 32)
        pygame.draw.circle(surf, NORD8, (cx, cy), 32, width=2)
        return surf

# =============================================================================
# SENDER CONTENT MANAGER (RANDOM JINGLES & TV IDENT ROTATION)
# =============================================================================
class StationContentManager:
    """Manages randomized Radio Jingles and TV Station IDs with persistent 2:1 rotation"""
    def __init__(self):
        self.jingles: List[Path] = []
        self.tv_ids: List[Path] = []
        self.jingle_pool: List[Path] = []
        self.tv_id_pool: List[Path] = []
        self.tracks_since_last_station = 0
        self.rotation_interval = 2
        self._scan_station_assets()

    def _scan_station_assets(self):
        base_dirs = [APP_DIR / "assets", Path("assets"), Path(".")]
        for b in base_dirs:
            j_dir = b / "jingles"
            if j_dir.exists():
                self.jingles = sorted(list(j_dir.glob("*.mp3")) + list(j_dir.glob("*.m4a")))
            t_dir = b / "tv_ids"
            if t_dir.exists():
                self.tv_ids = sorted(list(t_dir.glob("*.mp4")) + list(t_dir.glob("*.mkv")))
            if self.jingles or self.tv_ids:
                break

    def should_play_station_content(self) -> bool:
        if self.rotation_interval <= 0:
            return False
        return self.tracks_since_last_station >= self.rotation_interval

    def get_next_jingle(self) -> Optional[Path]:
        if not self.jingles:
            self._scan_station_assets()
        if not self.jingles:
            return None
        if not self.jingle_pool:
            self.jingle_pool = list(self.jingles)
            random.shuffle(self.jingle_pool)
        return self.jingle_pool.pop(0)

    def get_next_tv_id(self) -> Optional[Path]:
        if not self.tv_ids:
            self._scan_station_assets()
        if not self.tv_ids:
            return None
        if not self.tv_id_pool:
            self.tv_id_pool = list(self.tv_ids)
            random.shuffle(self.tv_id_pool)
        return self.tv_id_pool.pop(0)

    def reset_counter(self):
        self.tracks_since_last_station = 0

    def increment_counter(self):
        self.tracks_since_last_station += 1

# =============================================================================
# ZERO-DEPENDENCY DIRECT LINUX GAMEPAD READER (NO EVDEV / PURE STANDARD LIB)
# =============================================================================
class LinuxGamepadReader:
    """Reads Linux input events directly from /dev/input/event* via struct and select.
    Zero external dependencies (works on all CFWs without evdev or pygame)."""
    def __init__(self):
        import glob
        import struct
        self.fds = {}
        self.pressed_keys = set()
        is_64bit = sys.maxsize > 2**32
        self.fmt = "qqHHi" if is_64bit else "iiHHi"
        self.event_size = struct.calcsize(self.fmt)
        self._open_devices()

    def _open_devices(self):
        import glob
        for dev_path in glob.glob("/dev/input/event*"):
            try:
                fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
                self.fds[fd] = dev_path
            except Exception:
                pass

    def close(self):
        for fd in list(self.fds.keys()):
            try:
                os.close(fd)
            except Exception:
                pass
        self.fds.clear()

    def read_events(self, timeout=0.04):
        """Returns list of (ev_type, ev_code, ev_val) tuples"""
        if not self.fds:
            return []
        import select
        import struct
        events = []
        try:
            r, _, _ = select.select(list(self.fds.keys()), [], [], timeout)
            for fd in r:
                try:
                    data = os.read(fd, self.event_size * 32)
                    for i in range(0, len(data), self.event_size):
                        chunk = data[i:i + self.event_size]
                        if len(chunk) == self.event_size:
                            _, _, ev_type, ev_code, ev_val = struct.unpack(self.fmt, chunk)
                            events.append((ev_type, ev_code, ev_val))
                            if ev_type == 1:  # EV_KEY
                                if ev_val == 1:
                                    self.pressed_keys.add(ev_code)
                                elif ev_val == 0:
                                    self.pressed_keys.discard(ev_code)
                except Exception:
                    pass
        except Exception:
            pass
        return events

# =============================================================================
# MAIN DASHBOARD APPLICATION
# =============================================================================
class SNfetchDashboard:
    def __init__(self):
        self.state = STATE_SPLASH
        self.previous_state = STATE_RADIO

        self.audio_sink_args = self._detect_ffmpeg_audio_sink()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DISPLAY_FLAGS)
        pygame.display.set_caption("Station North • SNfetchPLAYER")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        # Fonts (Elevated for high legibility on 3.5" handheld display)
        self.font_hero = self._load_font(36, bold=True)
        self.font_title = self._load_font(26, bold=True)
        self.font_body = self._load_font(21, bold=True)
        self.font_artist = self._load_font(20, bold=True)
        self.font_quote = self._load_font(18, italic=True)
        self.font_badge = self._load_font(17, bold=True)
        self.font_small = self._load_font(16, bold=True)

        # Subsystems
        self.hardware = HardwareManager()
        self.visualizer = IntegratedVisualizer(num_bars=40)
        self.thumb_mgr = ThumbnailManager(default_size=(984, 440))
        self.station_mgr = StationContentManager()
        self.shuffle_mgr = ShuffleQueueManager()
        self.logo_img = self._load_logo()
        self.logo_large = self._load_large_logo()

        # Playlists
        self.available_playlists: List[Dict[str, str]] = []
        self.radio_playlist_idx = 0
        self.tv_playlist_idx = 0
        self.playlist: List[Dict] = []
        self._discover_playlists()

        # Default Radio Playlist to 'US R&B Top 50' if present
        for i, pl in enumerate(self.available_playlists):
            if "r&b" in pl.get("title", "").lower() or "rnb" in pl.get("path", "").lower():
                self.radio_playlist_idx = i
                break

        # Default TV Playlist to 'Main Top 100' if present
        for i, pl in enumerate(self.available_playlists):
            if "top 100" in pl.get("title", "").lower() or "main_top100" in pl.get("path", "").lower():
                self.tv_playlist_idx = i
                break

        # Quotes / Lore & Aurora Styling
        self.quotes: List[Dict[str, Any]] = []
        self.current_quote: str = "The lights are low, the bass is heavy. Station North."
        self.current_quote_color: Tuple[int, int, int] = NORD8
        self._last_quote_time: float = time.time()
        self._cached_radial_glow: Optional[pygame.Surface] = None
        self._load_quotes()
        self._load_quote_backgrounds()

        # The Chronicles
        self.chronicles_data: List[Dict] = []
        self.chronicles_idx = 0
        self.chronicles_img_cache: Dict[str, pygame.Surface] = {}
        self.chronicles_proc: Optional[subprocess.Popen] = None
        self.chronicles_playing = False
        self._load_chronicles()

        # UI State & Focus Cursor (v6.0 3+2 Tile Matrix & 3D Intro Splash)
        self.splash_cursor = 0  # 0=Radio, 1=TV, 2=Chronicles, 3=Settings, 4=Exit
        self.intro_active = True
        self.intro_start_time = time.time()
        self.intro_angle = 0.0
        self.intro_transitioning = False
        self.intro_transition_start = 0.0
        self.cursor_rect_current = None
        self._cursor_fx: Optional[float] = None
        self._cursor_fy: Optional[float] = None
        self._cursor_fw: Optional[float] = None
        self._cursor_fh: Optional[float] = None
        self.splash_enter_time = time.time()

        self.cockpit_focus_idx = 2 # Default focused button: Play/Pause (idx 2)
        self.current_idx = 0
        self.cursor_idx = 0

        self.is_playing = False
        self.is_radio_zen_mode = False
        self.radio_osd_visible = True
        self.radio_osd_last_interaction = 0.0
        self.is_station_drop = False
        self.station_drop_title = ""
        self.playback_start_time = 0.0
        self.track_duration = 210.0
        self.audio_proc: Optional[subprocess.Popen] = None

        self.is_resolving = False
        self.resolve_target_idx = -1
        self.resolve_thread: Optional[threading.Thread] = None

        self.settings_cursor = 0
        self.settings_column = 0  # 0 = Left Settings, 1 = Right Handbook
        self.settings_guide_scroll_y = 0
        self.settings_guide_max_scroll = 220
        self.settings_feedback_msg = ""
        self.settings_feedback_time = 0.0


        self._last_action_time: Dict[int, float] = {}
        self._state_transition_time: float = time.time()
        self._audio_lock = threading.RLock()
        self._resolve_id: int = 0

        # In-App Background Asset Downloader
        self.sync_active = False
        self.sync_total_items = 0
        self.sync_downloaded_items = 0
        self.sync_current_file = ""
        self.sync_pct = 0.0
        self.sync_status_text = ""
        self.sync_error = ""
        self.sync_thread: Optional[threading.Thread] = None
        self.sync_completed_timestamp = 0.0

        # Crate Digging & Pre-Fetching Engine
        self._prefetched_cache: Dict[str, Tuple[str, float]] = {}
        self._crate_stripe_surf: Optional[pygame.Surface] = None
        self._cached_label_logo: Optional[pygame.Surface] = None

        self.splash_enter_time = time.time()

        # Load default Radio Playlist
        self._load_active_playlist(is_tv=False)

        # Start asset sync check in background
        self._start_background_asset_sync()

        # Check initial assets: if 100% complete, show prominent 5s celebration on startup before auto-dismissing
        _, _, _, _, init_pct = self.get_asset_stats()
        if init_pct >= 99.0:
            self.sync_completed_timestamp = time.time()

    def _detect_ffmpeg_audio_sink(self) -> List[str]:
        # Native direct ALSA audio output for dArkOS & ArkOS (RK3326)
        logging.info("Audio Sink: Native ALSA default configured.")
        return ["-f", "alsa", "default"]

    def _load_font(self, size: int, bold=False, italic=False) -> pygame.font.Font:
        try:
            for name in ["dejavusans", "freesans", "arial", "helvetica", "sans"]:
                f = pygame.font.SysFont(name, size, bold=bold, italic=italic)
                if f:
                    return f
        except Exception:
            pass
        return pygame.font.Font(None, size)

    def _load_logo(self) -> Optional[pygame.Surface]:
        paths = [APP_DIR / "sn_logo.png", Path("sn_logo.png")]
        for p in paths:
            if p.exists():
                try:
                    img = pygame.image.load(str(p))
                    if pygame.display.get_surface():
                        img = img.convert_alpha()
                    # Scale to 67x42 keeping 400:250 ratio for header
                    return pygame.transform.smoothscale(img, (67, 42))
                except Exception:
                    pass
        return None

    def _load_large_logo(self) -> Optional[pygame.Surface]:
        paths = [APP_DIR / "sn_logo.png", Path("sn_logo.png")]
        for p in paths:
            if p.exists():
                try:
                    img = pygame.image.load(str(p))
                    if pygame.display.get_surface():
                        img = img.convert_alpha()
                    return img
                except Exception:
                    pass
        return None

    def _discover_playlists(self):
        self.available_playlists = []
        dirs_to_check = [
            APP_DIR / "assets/playlists",
            APP_DIR / "playlists",
            Path("assets/playlists"),
            Path("playlists"),
            Path(".")
        ]
        found_paths = {}

        for d in dirs_to_check:
            if d.exists():
                for p in d.glob("*.json"):
                    name = p.stem.lower()
                    if name in ["sprueche", "settings", "chronicles_data", "extractor_rules", "shuffle_state", "catalog_manifest", "port"]:
                        continue
                    if name not in found_paths:
                        found_paths[name] = p

        labels = {
            "main_top100": "Station North • Main Top 100",
            "us_rnb_top50": "Station North • US R&B Top 50",
            "us_pop_top50": "Station North • US 90s Pop Top 50",
            "us_hiphop_top50": "Station North • US Hip-Hop Top 50",
            "us_softrock_top50": "Station North • US Soft Rock Top 50",
            "playlist": "Station North • Essential Selection"
        }

        for key in ["main_top100", "us_rnb_top50", "us_pop_top50", "us_hiphop_top50", "us_softrock_top50"]:
            if key in found_paths:
                self.available_playlists.append({"title": labels[key], "path": str(found_paths[key].resolve())})

        for key, p in found_paths.items():
            if key not in ["main_top100", "us_rnb_top50", "us_pop_top50", "us_hiphop_top50", "us_softrock_top50"]:
                title = labels.get(key, f"Playlist: {p.stem.upper()}")
                self.available_playlists.append({"title": title, "path": str(p.resolve())})

        # --- DISCOVER LOCAL MEDIA FILES & FOLDERS ---
        MEDIA_AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".opus", ".aac"}
        MEDIA_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
        ALL_MEDIA_EXTS = MEDIA_AUDIO_EXTS | MEDIA_VIDEO_EXTS

        local_bases = [
            APP_DIR / "music",
            APP_DIR / "videos",
            APP_DIR / "playlists",
            Path("music"),
            Path("videos"),
            Path("playlists"),
        ]
        seen_dirs = set()

        for b_dir in local_bases:
            if not b_dir.exists():
                continue
            try:
                resolved_b = b_dir.resolve()
            except Exception:
                resolved_b = b_dir
            if resolved_b in seen_dirs:
                continue
            seen_dirs.add(resolved_b)

            b_name = b_dir.name.lower()
            if "music" in b_name:
                category_tag = "🎵 Music"
            elif "video" in b_name:
                category_tag = "🎬 Video"
            else:
                category_tag = "📁 Local"

            # 1. Media files directly in base directory
            root_tracks = []
            try:
                for item in sorted(b_dir.iterdir()):
                    if item.is_file() and item.suffix.lower() in ALL_MEDIA_EXTS:
                        stem = item.stem
                        artist = "Local Media"
                        title = stem
                        if " - " in stem:
                            parts = stem.split(" - ", 1)
                            artist = parts[0].strip()
                            title = parts[1].strip()
                        root_tracks.append({
                            "title": title,
                            "artist": artist,
                            "path": str(item.resolve()),
                            "local": True,
                            "is_video": item.suffix.lower() in MEDIA_VIDEO_EXTS
                        })
            except Exception:
                pass

            if root_tracks:
                self.available_playlists.append({
                    "title": f"{category_tag} • All Tracks",
                    "path": str(b_dir.resolve()),
                    "items": root_tracks
                })

            # 2. Subdirectories inside base directory (e.g. music/HipHop, videos/Rock)
            try:
                for sub in sorted(b_dir.iterdir()):
                    if sub.is_dir() and not sub.name.startswith("."):
                        sub_tracks = []
                        for item in sorted(sub.iterdir()):
                            if item.is_file() and item.suffix.lower() in ALL_MEDIA_EXTS:
                                stem = item.stem
                                artist = "Local Media"
                                title = stem
                                if " - " in stem:
                                    parts = stem.split(" - ", 1)
                                    artist = parts[0].strip()
                                    title = parts[1].strip()
                                sub_tracks.append({
                                    "title": title,
                                    "artist": artist,
                                    "path": str(item.resolve()),
                                    "local": True,
                                    "is_video": item.suffix.lower() in MEDIA_VIDEO_EXTS
                                })
                        if sub_tracks:
                            label = sub.name.replace("_", " ").replace("-", " ")
                            self.available_playlists.append({
                                "title": f"{category_tag} • {label}",
                                "path": str(sub.resolve()),
                                "items": sub_tracks
                            })
            except Exception:
                pass

        if not self.available_playlists:
            self.available_playlists.append({"title": "Station North • Default", "path": "playlist.json"})

        # Default Radio Playlist to 'US R&B Top 50' if present
        for i, pl in enumerate(self.available_playlists):
            if "r&b" in pl.get("title", "").lower() or "rnb" in pl.get("path", "").lower():
                self.radio_playlist_idx = i
                break

    def _load_active_playlist(self, is_tv: bool = False):
        idx = self.tv_playlist_idx if is_tv else self.radio_playlist_idx
        if not self.available_playlists:
            self._discover_playlists()
        if idx >= len(self.available_playlists):
            idx = 0
        item = self.available_playlists[idx]
        if "items" in item:
            self.playlist = list(item["items"])
        else:
            try:
                with open(item["path"], "r", encoding="utf-8") as f:
                    self.playlist = json.load(f)
            except Exception:
                self.playlist = []

        self.shuffle_mgr.init_playlist(len(self.playlist), playlist_id=item["title"])
        self.current_idx = self.shuffle_mgr.get_current_idx()
        self.cursor_idx = self.current_idx

    def _load_quotes(self):
        self.quotes = []
        for q_path in [APP_DIR / "sprueche.json", Path("sprueche.json")]:
            if q_path.exists():
                try:
                    with open(q_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data:
                            if isinstance(item, dict) and "text" in item:
                                cls_name = item.get("class", item.get("color", ""))
                                default_col = SPRUECHE_CLASS_MAP.get(cls_name, None)
                                self.quotes.append({
                                    "text": item["text"].strip(),
                                    "color": default_col
                                })
                            elif isinstance(item, str) and item.strip():
                                self.quotes.append({"text": item.strip(), "color": None})
                    if self.quotes:
                        break
                except Exception:
                    pass
        self._update_quote()

    def _update_quote(self):
        if self.quotes:
            q = random.choice(self.quotes)
            self.current_quote = q["text"]
            self.current_quote_color = random.choice(AURORA_PALETTE)
            if hasattr(self, "quote_bg_surfaces") and self.quote_bg_surfaces:
                self.current_quote_bg_idx = (self.current_quote_bg_idx + 1) % len(self.quote_bg_surfaces)
        else:
            self.current_quote = "The lights are low, the bass is heavy. Station North."
            self.current_quote_color = random.choice(AURORA_PALETTE)
        self._last_quote_time = time.time()

    def _check_cycle_quote(self):
        now = time.time()
        # Calibrated 22.0s reading interval so user has plenty of time to enjoy quotes
        if now - self._last_quote_time > 22.0:
            self._update_quote()

    def _load_quote_backgrounds(self):
        """Loads and pre-processes subtle background artwork for the Queen Directives console"""
        self.quote_bg_surfaces = []
        self.current_quote_bg_idx = 0
        bg_dirs = [
            APP_DIR / "assets/backgrounds",
            Path("assets/backgrounds")
        ]
        found_imgs = []
        for bd in bg_dirs:
            if bd.exists():
                for p in sorted(bd.glob("*.*")):
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                        try:
                            rp = p.resolve()
                            if rp not in [f.resolve() for f in found_imgs]:
                                found_imgs.append(p)
                        except Exception:
                            if p not in found_imgs:
                                found_imgs.append(p)

        # Fallback to comic cover if no dedicated background image yet
        if not found_imgs:
            for cov in [APP_DIR / "assets/comic/Cover_Vol01.webp", Path("assets/comic/Cover_Vol01.webp")]:
                if cov.exists():
                    found_imgs.append(cov)
                    break

        box_w, box_h = 910, 286
        for img_path in found_imgs[:20]:
            try:
                raw_surf = pygame.image.load(str(img_path))
                iw, ih = raw_surf.get_size()
                if iw <= 0 or ih <= 0:
                    continue
                scale = max(box_w / iw, box_h / ih)
                nw, nh = max(box_w, int(iw * scale)), max(box_h, int(ih * scale))
                scaled = pygame.transform.smoothscale(raw_surf, (nw, nh))
                crop_x = max(0, (nw - box_w) // 2)
                crop_y = max(0, (nh - box_h) // 2)
                cropped = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
                cropped.blit(scaled, (-crop_x, -crop_y))
                # Apply 84% dark Nord0 tint so quote text is 100% crystal clear and high-contrast
                dark_tint = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
                dark_tint.fill((34, 39, 49, 215))
                cropped.blit(dark_tint, (0, 0))
                # Apply smooth rounded corner mask matching the container's border_radius=16
                mask = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
                pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, box_w, box_h), border_radius=16)
                cropped.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                self.quote_bg_surfaces.append(cropped)
            except Exception as e:
                logging.debug(f"Could not load quote bg {img_path}: {e}")

    def _render_wrapped_lines(self, text: str, font: pygame.font.Font, max_w: int) -> List[str]:
        words = text.split(" ")
        lines = []
        cur_line = []
        for w in words:
            test_line = " ".join(cur_line + [w])
            if font.size(test_line)[0] <= max_w:
                cur_line.append(w)
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                    cur_line = [w]
                else:
                    lines.append(w)
                    cur_line = []
        if cur_line:
            lines.append(" ".join(cur_line))
        return lines

    def _load_chronicles(self):
        paths = [
            APP_DIR / "assets/comic/chronicles_data.json",
            Path("assets/comic/chronicles_data.json")
        ]
        for p in paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        self.chronicles_data = json.load(f)
                    break
                except Exception:
                    pass

    def get_asset_stats(self) -> Tuple[int, int, int, int, float]:
        j_count = len(self.station_mgr.jingles)
        t_count = len(self.station_mgr.tv_ids)
        c_count = 0
        comic_dirs = [APP_DIR / "assets" / "comic", Path("assets/comic")]
        for cd in comic_dirs:
            if cd.exists():
                files = [f for f in cd.rglob("*.*") if f.suffix.lower() in {".webp", ".png", ".jpg", ".mp3", ".json"} and f.stat().st_size > 0]
                if files:
                    c_count = len(files)
                    break
        total = j_count + t_count + c_count
        expected = 174 + 42 + 131  # 347 total media assets (174 Jingles + 42 TV Idents + 131 Chronicles Pages & Audio)
        pct = min(100.0, (total / expected) * 100.0) if expected > 0 else 0.0
        return j_count, t_count, c_count, total, pct

    def _start_background_asset_sync(self):
        """Starts background daemon thread to check and download missing media assets"""
        if self.sync_thread and self.sync_thread.is_alive():
            return
        self.sync_thread = threading.Thread(target=self._run_asset_sync, daemon=True)
        self.sync_thread.start()

    def _run_asset_sync(self):
        """Asynchronously downloads missing 480p TV idents, Jingles and Comics from GitHub"""
        try:
            # 1. Base directory detection
            base_dir = APP_DIR / "assets"
            base_dir.mkdir(parents=True, exist_ok=True)
            app_dir = APP_DIR

            manifest_path = base_dir / "catalog_manifest.json"
            manifest = None

            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                except Exception:
                    manifest = None

            if not manifest:
                self.sync_status_text = "Fetching asset catalog from GitHub..."
                manifest_url = "https://raw.githubusercontent.com/StationNorthMedia/SNfetchPLAYER-PortMaster/main/assets/catalog_manifest.json"
                raw_data = None
                try:
                    c_res = subprocess.run(
                        ["curl", "-s", "-L", "-k", "--connect-timeout", "12", "--max-time", "25",
                         "-H", "User-Agent: SNfetchPLAYER-PortMaster/6.2", manifest_url],
                        capture_output=True,
                        timeout=30
                    )
                    if c_res.returncode == 0 and c_res.stdout:
                        raw_data = c_res.stdout.decode("utf-8", errors="replace")
                except Exception:
                    raw_data = None

                if not raw_data:
                    try:
                        req = urllib.request.Request(manifest_url, headers={"User-Agent": "SNfetchPLAYER-PortMaster/6.2"})
                        with urllib.request.urlopen(req, timeout=12) as resp:
                            raw_data = resp.read().decode("utf-8", errors="replace")
                    except Exception:
                        raw_data = None

                if raw_data:
                    try:
                        manifest = json.loads(raw_data)
                        with open(manifest_path, "w", encoding="utf-8") as f:
                            f.write(raw_data)
                    except Exception:
                        manifest = None

            if not manifest:
                return

            tv_list = manifest.get("tv_ids", [])
            jingle_list = manifest.get("jingles", [])
            comic_list = manifest.get("comic", [])

            tv_dir = base_dir / "tv_ids"
            jingle_dir = base_dir / "jingles"
            comic_dir = base_dir / "comic"
            tv_dir.mkdir(parents=True, exist_ok=True)
            jingle_dir.mkdir(parents=True, exist_ok=True)
            comic_dir.mkdir(parents=True, exist_ok=True)

            # Build list of missing download tasks
            tasks = []
            for item in tv_list:
                fname = item.get("name") or item.get("id")
                url = item.get("url")
                if fname and url:
                    target = tv_dir / fname
                    if not target.exists() or target.stat().st_size == 0:
                        tasks.append(("TV Ident", fname, url, target))

            for item in jingle_list:
                fname = item.get("name") or item.get("id")
                url = item.get("url")
                if fname and url:
                    target = jingle_dir / fname
                    if not target.exists() or target.stat().st_size == 0:
                        tasks.append(("Jingle", fname, url, target))

            for item in comic_list:
                cid = item.get("id")
                curl = item.get("url")
                if cid and curl:
                    target = comic_dir / cid
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists() or target.stat().st_size == 0:
                        tasks.append(("Chronicles Lore", cid, curl, target))

            total_needed = len(tasks)
            if total_needed == 0:
                self.sync_active = False
                self.sync_pct = 100.0
                self.sync_status_text = "All Station Assets Synchronized • 100% Ready"
                self.station_mgr._scan_station_assets()
                self._load_chronicles()
                if self.sync_completed_timestamp == 0.0:
                    self.sync_completed_timestamp = time.time()
                return

            self.sync_active = True
            self.sync_total_items = total_needed
            self.sync_downloaded_items = 0

            # --- STRATEGY 1: HIGH-SPEED BUNDLE ZIP DOWNLOAD (FOR FRESH INSTALLS / MASSIVE UPDATES) ---
            # If > 25 files are missing, download the full asset archive in one high-throughput stream
            if total_needed > 25:
                bundle_urls = [
                    "https://github.com/StationNorthMedia/SNfetchPLAYER-PortMaster/releases/download/v7.0.0/snfetchplayer-assets.zip",
                    "https://github.com/StationNorthMedia/SNfetchPLAYER-PortMaster/releases/download/v5.0.0/snfetchplayer-assets.zip",
                    "https://github.com/StationNorthMedia/SNfetchPLAYER-PortMaster/releases/download/v4.0.0/snfetchplayer-assets.zip"
                ]
                bundle_downloaded = False
                tmp_zip = app_dir / "snfetchplayer_assets_temp.zip"

                for b_url in bundle_urls:
                    try:
                        self.sync_status_text = "Connecting to High-Speed Asset Server..."
                        if tmp_zip.exists():
                            try:
                                tmp_zip.unlink()
                            except Exception:
                                pass

                        curl_success = False
                        total_bytes = 298013869

                        # Try native curl first (works across all CFWs without python _ssl / libssl.so.1.1)
                        try:
                            curl_cmd = [
                                "curl", "-L", "-k", "-f", "-s", "-S",
                                "--connect-timeout", "15",
                                "-H", "User-Agent: SNfetchPLAYER-PortMaster/6.2",
                                "-o", str(tmp_zip),
                                b_url
                            ]
                            proc = subprocess.Popen(curl_cmd)
                            while proc.poll() is None:
                                time.sleep(0.3)
                                if tmp_zip.exists():
                                    downloaded_bytes = tmp_zip.stat().st_size
                                    dl_mb = downloaded_bytes / (1024 * 1024)
                                    tot_mb = total_bytes / (1024 * 1024)
                                    pct = min(98.0, (downloaded_bytes / total_bytes) * 100.0)
                                    self.sync_pct = pct
                                    self.sync_status_text = f"Downloading Media Pack: {dl_mb:.1f} MB / {tot_mb:.1f} MB ({int(pct)}%)"
                            if proc.returncode == 0 and tmp_zip.exists() and tmp_zip.stat().st_size > 50 * 1024 * 1024:
                                curl_success = True
                        except Exception:
                            curl_success = False

                        # Fallback to urllib if curl was unavailable
                        if not curl_success and not (tmp_zip.exists() and tmp_zip.stat().st_size > 50 * 1024 * 1024):
                            req = urllib.request.Request(b_url, headers={"User-Agent": "SNfetchPLAYER-PortMaster/6.2"})
                            with urllib.request.urlopen(req, timeout=15) as resp:
                                content_len_hdr = resp.headers.get("Content-Length")
                                total_bytes = int(content_len_hdr) if content_len_hdr else 298013869
                                downloaded_bytes = 0
                                last_update_time = time.time()

                                with open(tmp_zip, "wb") as out_f:
                                    while True:
                                        chunk = resp.read(262144)  # 256KB chunks
                                        if not chunk:
                                            break
                                        out_f.write(chunk)
                                        downloaded_bytes += len(chunk)
                                        now = time.time()
                                        if now - last_update_time > 0.25 or downloaded_bytes >= total_bytes:
                                            last_update_time = now
                                            dl_mb = downloaded_bytes / (1024 * 1024)
                                            tot_mb = total_bytes / (1024 * 1024)
                                            pct = min(98.0, (downloaded_bytes / total_bytes) * 100.0)
                                            self.sync_pct = pct
                                            self.sync_status_text = f"Downloading Media Pack: {dl_mb:.1f} MB / {tot_mb:.1f} MB ({int(pct)}%)"

                        if tmp_zip.exists() and tmp_zip.stat().st_size > 50 * 1024 * 1024:
                            self.sync_status_text = "Extracting Media Pack (TV Idents, Jingles & Comics)..."
                            self.sync_pct = 99.0
                            import zipfile
                            with zipfile.ZipFile(tmp_zip, "r") as z:
                                z.extractall(app_dir)
                            try:
                                tmp_zip.unlink()
                            except Exception:
                                pass
                            bundle_downloaded = True
                            break
                    except Exception as b_err:
                        if tmp_zip.exists():
                            try:
                                tmp_zip.unlink()
                            except Exception:
                                pass

                if bundle_downloaded:
                    self.station_mgr._scan_station_assets()
                    self._load_chronicles()
                    # Re-check remaining tasks
                    remaining = [t for t in tasks if not t[3].exists() or t[3].stat().st_size == 0]
                    if not remaining:
                        self.sync_active = False
                        self.sync_pct = 100.0
                        self.sync_status_text = "All Station Assets Synchronized • 100% Ready"
                        self.sync_completed_timestamp = time.time()
                        return
                    tasks = remaining
                    total_needed = len(tasks)
                    self.sync_total_items = total_needed

            # --- STRATEGY 2: DELTA SYNC (INDIVIDUAL FILE DOWNLOADS FOR SMALL UPDATES / FALLBACK) ---
            for idx, (itype, fname, raw_url, target) in enumerate(tasks, 1):
                safe_url = urllib.parse.quote(raw_url, safe=":/?&=")
                self.sync_current_file = fname
                self.sync_downloaded_items = idx
                self.sync_pct = (idx / total_needed) * 100.0
                display_fname = fname if len(fname) <= 34 else fname[:31] + "..."
                self.sync_status_text = f"Syncing {itype} ({idx}/{total_needed}): {display_fname}"

                tmp_target = target.with_suffix(target.suffix + ".part")
                file_done = False

                # 1. Try native curl first (bypasses python _ssl / OpenSSL 1.1)
                try:
                    c_res = subprocess.run(
                        ["curl", "-L", "-k", "-f", "-s", "--connect-timeout", "10", "--max-time", "60",
                         "-H", "User-Agent: SNfetchPLAYER-PortMaster/6.2", "-o", str(tmp_target), safe_url],
                        timeout=65
                    )
                    if c_res.returncode == 0 and tmp_target.exists() and tmp_target.stat().st_size > 0:
                        tmp_target.rename(target)
                        file_done = True
                except Exception:
                    file_done = False

                # 2. Fallback to urllib if curl was not successful
                if not file_done:
                    try:
                        req = urllib.request.Request(safe_url, headers={"User-Agent": "SNfetchPLAYER-PortMaster/6.2"})
                        with urllib.request.urlopen(req, timeout=15) as resp, open(tmp_target, "wb") as out_f:
                            while True:
                                chunk = resp.read(65536)
                                if not chunk:
                                    break
                                out_f.write(chunk)
                        if tmp_target.exists() and tmp_target.stat().st_size > 0:
                            tmp_target.rename(target)
                            file_done = True
                    except Exception as dl_err:
                        if tmp_target.exists():
                            try:
                                tmp_target.unlink()
                            except Exception:
                                pass
                        time.sleep(0.3)

                # Periodically update asset pool so items can be played immediately
                if idx % 2 == 0 or idx == total_needed:
                    self.station_mgr._scan_station_assets()
                    self._load_chronicles()

            self.sync_active = False
            self.sync_pct = 100.0
            self.sync_status_text = "All Station Assets Synchronized • 100% Ready"
            self.sync_completed_timestamp = time.time()
            self.station_mgr._scan_station_assets()
            self._load_chronicles()
        except Exception as e:
            self.sync_active = False
            self.sync_error = str(e)

    # =========================================================================
    # CRATE-DIGGING VINYL STREAM RESOLVER & PRE-FETCH ENGINE (1:1 NORD CRATE)
    # =========================================================================
    def _draw_crate_stripes(self, surface: pygame.Surface, w: int, h: int, offset_x: float, col: Tuple[int, int, int], bars: List[Tuple[float, float]]):
        total_w = w * 1.8
        start_x = -w * 0.4 + offset_x
        for b_start, b_end in bars:
            left = int(start_x + b_start * total_w)
            right = int(start_x + b_end * total_w)
            bar_w = right - left
            if bar_w > 0:
                pygame.draw.rect(surface, col, (left, 0, bar_w, h))

    def _render_crate_digging_frame(self, title: str, subtitle: str, elapsed: float):
        w = SCREEN_WIDTH
        h = SCREEN_HEIGHT
        cx = w // 2
        cy = h // 2 - 32

        # 1. Base Dark Background (Nord0 #2E3440)
        self.screen.fill(NORD0)

        # 2. 3 Parallax Vertical Stripe Layers (Crate-Digging Look with Additive Glow)
        if not hasattr(self, "_crate_stripe_surf") or self._crate_stripe_surf is None or self._crate_stripe_surf.get_size() != (w, h):
            self._crate_stripe_surf = pygame.Surface((w, h))

        self._crate_stripe_surf.fill((0, 0, 0))

        # Layer 1: Nord Cyan (136, 192, 208) scaled for additive glow (~40%)
        col1 = (52, 74, 80)
        offset1 = (math.sin(elapsed * 1.5) * 0.5 + 0.5) * (w * 0.28)
        self._draw_crate_stripes(self._crate_stripe_surf, w, h, offset1, col1, [(0.0, 0.40), (0.50, 0.90)])

        # Layer 2: Nord Teal (143, 188, 187) scaled for additive glow (~35%)
        col2 = (44, 58, 58)
        offset2 = (math.sin(elapsed * 1.1 + 1.2) * 0.5 + 0.5) * (w * 0.32) - (w * 0.12)
        self._draw_crate_stripes(self._crate_stripe_surf, w, h, offset2, col2, [(0.0, 0.25), (0.35, 0.65), (0.75, 1.0)])

        # Layer 3: Nord Soft Blue (129, 161, 193) scaled for additive glow (~30%)
        col3 = (34, 44, 52)
        offset3 = (math.sin(elapsed * 0.8 + 2.4) * 0.5 + 0.5) * (w * 0.24) - (w * 0.08)
        self._draw_crate_stripes(self._crate_stripe_surf, w, h, offset3, col3, [(0.0, 0.30), (0.40, 0.80), (0.90, 1.0)])

        # Blit stripes with BLEND_ADD to achieve true luminous PorterDuff SCREEN / Neon glow!
        self.screen.blit(self._crate_stripe_surf, (0, 0), special_flags=pygame.BLEND_ADD)

        # 3. Rotating Vinyl Record Badge in Center
        vinyl_radius = int(min(w, h) * 0.21)
        rotation_angle = (elapsed * 90.0) % 360.0

        # Vinyl Disc Body (Nord1 #3B4252)
        pygame.draw.circle(self.screen, NORD1, (cx, cy), vinyl_radius)

        # Concentric Grooves (Nord2 #434C5E)
        for r_factor in (0.86, 0.72, 0.58):
            pygame.draw.circle(self.screen, NORD2, (cx, cy), int(vinyl_radius * r_factor), width=2)

        # Center Vinyl Label (Nord8 Cyan #88C0D0)
        center_label_radius = int(vinyl_radius * 0.40)
        pygame.draw.circle(self.screen, NORD8, (cx, cy), center_label_radius)

        # Center Logo inside label (rotated with 90°/s)
        if self.logo_large:
            img_w = int(center_label_radius * 1.35)
            img_h = int(img_w * (self.logo_large.get_height() / self.logo_large.get_width()))
            if not hasattr(self, "_cached_label_logo") or self._cached_label_logo is None or self._cached_label_logo.get_size() != (img_w, img_h):
                self._cached_label_logo = pygame.transform.smoothscale(self.logo_large, (img_w, img_h))

            rot_logo = pygame.transform.rotate(self._cached_label_logo, -rotation_angle)
            rot_rect = rot_logo.get_rect(center=(cx, cy))
            self.screen.blit(rot_logo, rot_rect)

        # Center Spindle Hole
        pygame.draw.circle(self.screen, (24, 28, 36), (cx, cy), 7)
        pygame.draw.circle(self.screen, NORD3, (cx, cy), 7, width=1)

        # Outer Neon Border Ring with breathing glow
        glow_factor = (180 + 75 * math.sin(elapsed * 5.0)) / 255.0
        ring_col = (int(136 * glow_factor), int(192 * glow_factor), int(208 * glow_factor))
        pygame.draw.circle(self.screen, ring_col, (cx, cy), vinyl_radius + 4, width=3)

        # 4. Track Information Banner & Resolving Text
        badge_s = self._load_font(18, bold=True).render("⚡ CRATE DIGGING // RESOLVING BROADCAST STREAM", True, NORD8)
        self.screen.blit(badge_s, ((w - badge_s.get_width()) // 2, cy + vinyl_radius + 26))

        if title:
            tit_s = self._load_font(24, bold=True).render(title, True, (255, 255, 255))
            if tit_s.get_width() > w - 100:
                tit_s = self._load_font(20, bold=True).render(title[:55] + "...", True, (255, 255, 255))
            self.screen.blit(tit_s, ((w - tit_s.get_width()) // 2, cy + vinyl_radius + 58))

        if subtitle:
            sub_s = self._load_font(18, bold=True).render(subtitle, True, NORD4)
            if sub_s.get_width() > w - 100:
                sub_s = self._load_font(16, bold=True).render(subtitle[:60] + "...", True, NORD4)
            self.screen.blit(sub_s, ((w - sub_s.get_width()) // 2, cy + vinyl_radius + 92))

        # Bottom Bar
        self.draw_bottom_bar(pills=[("B", "Cancel", NORD11)], right_text="Station North • Crate Engine")

    def _trigger_prefetch_next_track(self, curr_idx: int, is_tv: bool):
        """Pre-resolves the next track's stream URL in a background worker thread"""
        if not self.playlist:
            return
        next_idx = (curr_idx + 1) % len(self.playlist)
        next_track = self.playlist[next_idx]
        yt_id = next_track.get("youtubeId")
        if not yt_id or Path(str(yt_id)).exists() or str(yt_id).startswith("/") or str(yt_id).startswith("."):
            return
        cache_key = f"{yt_id}_{'TV' if is_tv else 'RADIO'}"
        if cache_key in self._prefetched_cache:
            return

        def _prefetch_worker():
            try:
                logging.info(f"Background pre-fetching next track [{next_track.get('title')}]...")
                url, _ = get_stream(yt_id, prefer_audio_only=not is_tv)
                if url:
                    self._prefetched_cache[cache_key] = (url, time.time() + 14400)
                    logging.info(f"Pre-fetch success for [{next_track.get('title')}]")
            except Exception as e:
                logging.warning(f"Pre-fetch failed for {yt_id}: {e}")

        t = threading.Thread(target=_prefetch_worker, daemon=True)
        t.start()

    def resolve_stream_interactive(self, track: Dict, is_tv: bool = True) -> Tuple[Optional[str], bool]:
        """Resolves stream with 0ms prefetch cache hit OR 60 FPS Crate-Digging Vinyl Animation.
        Returns: (stream_url, was_cancelled)"""
        local_path = track.get("path") or track.get("file")
        if local_path and Path(local_path).exists():
            return str(Path(local_path).resolve()), False

        yt_id = track.get("youtubeId")
        if yt_id and (Path(str(yt_id)).exists() or str(yt_id).startswith("/") or str(yt_id).startswith(".")):
            if Path(str(yt_id)).exists():
                return str(Path(str(yt_id)).resolve()), False

        if not yt_id:
            return None, False

        cache_key = f"{yt_id}_{'TV' if is_tv else 'RADIO'}"
        if cache_key in self._prefetched_cache:
            url, exp = self._prefetched_cache[cache_key]
            if time.time() < exp:
                logging.info(f"0ms Instant Start: Pre-fetch cache hit for [{track.get('title')}]")
                return url, False
            else:
                del self._prefetched_cache[cache_key]

        if not pygame.display.get_init():
            pygame.display.init()
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DISPLAY_FLAGS)
            pygame.mouse.set_visible(False)

        track_title = track.get("title", "Unknown Title")
        track_artist = track.get("artist", "Station North")

        res_box = [None, False]  # [stream_url, finished]
        def _resolve_worker():
            try:
                url, _ = get_stream(yt_id, prefer_audio_only=not is_tv)
                res_box[0] = url
            except Exception as e:
                logging.warning(f"Interactive resolve failed for {yt_id}: {e}")
            finally:
                res_box[1] = True

        worker_thread = threading.Thread(target=_resolve_worker, daemon=True)
        worker_thread.start()

        start_time = time.time()
        was_cancelled = False

        while not res_box[1]:
            elapsed = time.time() - start_time
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    was_cancelled = True
                    break
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE, pygame.K_b, pygame.K_q):
                        was_cancelled = True
                        break
                elif ev.type == pygame.JOYBUTTONDOWN:
                    if ev.button in (1, 6):
                        was_cancelled = True
                        break

            if was_cancelled:
                break

            self._render_crate_digging_frame(track_title, track_artist, elapsed)
            pygame.display.flip()
            self.clock.tick(60)

        if was_cancelled:
            return None, True

        resolved_url = res_box[0]
        if resolved_url:
            self._prefetched_cache[cache_key] = (resolved_url, time.time() + 14400)
            return resolved_url, False

        return None, False

    def show_loading_screen(self, title: str = "STATION NORTH TV", subtitle: str = "Initializing Audio Stream..."):
        if not pygame.display.get_init():
            pygame.display.init()
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DISPLAY_FLAGS)
            pygame.mouse.set_visible(False)

        self.screen.fill(NORD0)

        # 1. Harmonized 56px Top Bar
        top_title = "STATION NORTH TV" if "TV" in title else ("THE CHRONICLES" if "CHRONICLES" in title else "STATION NORTH")
        self.draw_top_bar(custom_title=top_title, subtitle="CONNECTING TO STREAM • BUFFERING")

        # 2. Centered Content Card (760x420)
        card_w = 760
        card_h = 420
        card_x = (SCREEN_WIDTH - card_w) // 2
        card_y = (SCREEN_HEIGHT - card_h) // 2 - 10
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)

        pygame.draw.rect(self.screen, (24, 28, 36), card_rect, border_radius=20)
        pygame.draw.rect(self.screen, (46, 52, 64), card_rect, width=2, border_radius=20)
        # Top Cyan Accent Line
        self._draw_horizontal_gradient(self.screen, pygame.Rect(card_x + 24, card_y, card_w - 48, 3), NORD8, NORD7)

        # Centered Station North Logo (144x90 keeps 16:10 aspect ratio)
        cx = SCREEN_WIDTH // 2
        logo_w, logo_h = 144, 90
        logo_src = self.logo_large if self.logo_large else self.logo_img
        if logo_src:
            scaled_logo = pygame.transform.smoothscale(logo_src, (logo_w, logo_h))
            self.screen.blit(scaled_logo, (cx - logo_w // 2, card_y + 36))

        # Channel Badge
        badge_y = card_y + 144
        badge_txt = "✦ STATION NORTH RETRO BROADCAST ✦"
        b_surf = self._load_font(16, bold=True).render(badge_txt, True, NORD8)
        self.screen.blit(b_surf, (cx - b_surf.get_width() // 2, badge_y))

        # Parse & Format Video Info cleanly (prevent overflow / breakout)
        display_text = subtitle
        if display_text.startswith("Loading Video: "):
            display_text = display_text[15:]

        if " - " in display_text:
            parts = display_text.split(" - ", 1)
            artist_line = parts[0].strip()
            title_line = parts[1].strip()
        else:
            artist_line = ""
            title_line = display_text.strip()

        cur_y = card_y + 184
        if artist_line:
            art_surf = self._load_font(20, bold=True).render(artist_line, True, NORD4)
            if art_surf.get_width() > card_w - 60:
                art_surf = self._load_font(18, bold=True).render(artist_line[:40] + "...", True, NORD4)
            self.screen.blit(art_surf, (cx - art_surf.get_width() // 2, cur_y))
            cur_y += 34

        t_font = self._load_font(24, bold=True)
        if t_font.size(title_line)[0] > card_w - 60:
            t_font = self._load_font(20, bold=True)
            if t_font.size(title_line)[0] > card_w - 60:
                title_line = title_line[:46] + "..."
        tit_surf = t_font.render(title_line, True, (255, 255, 255))
        self.screen.blit(tit_surf, (cx - tit_surf.get_width() // 2, cur_y))

        # Progress Bar (640px)
        pbar_w = card_w - 120
        pbar_h = 14
        pbar_x = cx - pbar_w // 2
        pbar_y = card_y + 296
        pygame.draw.rect(self.screen, (16, 20, 26), (pbar_x, pbar_y, pbar_w, pbar_h), border_radius=7)
        fill_w = int(pbar_w * 0.72)
        pygame.draw.rect(self.screen, NORD8, (pbar_x, pbar_y, fill_w, pbar_h), border_radius=7)
        pygame.draw.rect(self.screen, (255, 255, 255), (pbar_x + fill_w - 12, pbar_y + 2, 8, pbar_h - 4), border_radius=3)

        note_surf = self._load_font(16, bold=True).render("⚡ Resolving Stream via InnerTube • 4:3 Display Fill", True, NORD4)
        self.screen.blit(note_surf, (cx - note_surf.get_width() // 2, card_y + 332))

        # 3. Harmonized 48px Bottom Bar
        self.draw_bottom_bar(pills=[("B", "Cancel", NORD11)], right_text="v7.0 • Back to the Rules")

        pygame.display.flip()

    # --- AUDIO CONTROLS (RADIO MODE) ---
    def stop_audio(self):
        with self._audio_lock:
            self._resolve_id += 1
            proc = self.audio_proc
            self.audio_proc = None
            self.is_playing = False
            self.is_station_drop = False
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=0.3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

    def _audio_spectrum_reader(self, proc: subprocess.Popen):
        if not proc or not proc.stdout:
            return
        chunk_size = 2048  # 1024 16-bit mono samples (~46ms @ 22.05kHz)
        chunk_duration = 1024.0 / 22050.0
        
        # Audio DAC hardware / ring buffer delay compensation (sound takes ~0.35s to physical output)
        time.sleep(0.35)
        
        next_chunk_time = time.time()
        try:
            while proc and proc.poll() is None and self.is_playing:
                data = proc.stdout.read(chunk_size)
                if not data:
                    break
                self.visualizer.feed_pcm(data)
                
                # Pace the reader so it stays locked to real-time audio playback
                next_chunk_time += chunk_duration
                sleep_time = next_chunk_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                elif sleep_time < -0.15:
                    # If behind by more than 150ms, re-anchor
                    next_chunk_time = time.time()
        except Exception:
            pass

    def trigger_play_track_async(self, idx: int):
        with self._audio_lock:
            self.stop_audio()
            curr_id = self._resolve_id
            self.resolve_target_idx = idx
            self.is_resolving = True
        self.resolve_thread = threading.Thread(target=self._resolve_and_play_worker, args=(idx, curr_id), daemon=True)
        self.resolve_thread.start()

    def _resolve_and_play_worker(self, idx: int, req_id: int):
        try:
            if idx < 0 or idx >= len(self.playlist):
                return

            if self.state != STATE_RADIO or self._resolve_id != req_id:
                return

            # 2:1 Rotation Check (unless Repeat mode is on)
            if not self.shuffle_mgr.is_repeat_mode and self.station_mgr.should_play_station_content():
                jingle_path = self.station_mgr.get_next_jingle()
                if jingle_path and jingle_path.exists():
                    self.station_mgr.reset_counter()
                    self.is_station_drop = True
                    self.station_drop_title = f"Station North • ID #{jingle_path.stem}"
                    self.current_idx = idx
                    self.cursor_idx = idx

                    if shutil.which("ffmpeg"):
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", str(jingle_path),
                            "-filter_complex", "[0:a]asplit=2[out1][out2]",
                            "-map", "[out1]", *self.audio_sink_args,
                            "-map", "[out2]", "-flush_packets", "1", "-f", "s16le", "-ac", "1", "-ar", "22050", "-"
                        ]
                        stdout_mode = subprocess.PIPE
                    elif shutil.which("mpv"):
                        cmd = ["mpv", "--no-video", "--no-terminal", "--audio-fallback-to-null=yes", str(jingle_path)]
                        stdout_mode = subprocess.DEVNULL
                    else:
                        cmd = ["aplay", "-q", str(jingle_path)]
                        stdout_mode = subprocess.DEVNULL

                    with self._audio_lock:
                        if self.state != STATE_RADIO or self._resolve_id != req_id:
                            return
                        self.audio_proc = subprocess.Popen(cmd, stdout=stdout_mode, stderr=subprocess.DEVNULL)
                        self.is_playing = True
                    self.playback_start_time = time.time()
                    self.track_duration = 12.0
                    if stdout_mode == subprocess.PIPE:
                        threading.Thread(target=self._audio_spectrum_reader, args=(self.audio_proc,), daemon=True).start()
                    
                    proc = self.audio_proc
                    if proc:
                        try:
                            proc.wait()
                            time.sleep(0.6)  # Allow soundcard buffer to naturally drain
                        except Exception:
                            pass
                    self.is_station_drop = False

            if self.state != STATE_RADIO or self._resolve_id != req_id:
                return

            track = self.playlist[idx]
            local_path = track.get("path") or track.get("file")
            is_local = False
            stream_url = None
            duration = 210.0

            if local_path and Path(local_path).exists():
                is_local = True
                stream_url = str(Path(local_path).resolve())
            elif track.get("youtubeId") and (Path(str(track.get("youtubeId"))).exists() or str(track.get("youtubeId")).startswith("/") or str(track.get("youtubeId")).startswith(".")):
                if Path(str(track.get("youtubeId"))).exists():
                    is_local = True
                    stream_url = str(Path(str(track.get("youtubeId"))).resolve())

            if is_local:
                try:
                    prb = subprocess.run([
                        "ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", stream_url
                    ], capture_output=True, text=True, timeout=1.5)
                    if prb.stdout.strip():
                        duration = float(prb.stdout.strip())
                except Exception:
                    pass
            else:
                yt_id = track.get("youtubeId")
                cache_key = f"{yt_id}_RADIO"
                if cache_key in self._prefetched_cache:
                    cached_url, exp = self._prefetched_cache[cache_key]
                    if time.time() < exp:
                        stream_url = cached_url
                        logging.info(f"Radio: 0ms Pre-fetch Cache Hit for [{track.get('title')}]")
                if not stream_url:
                    stream_url, duration = get_stream(yt_id, prefer_audio_only=True)
                    if stream_url:
                        self._prefetched_cache[cache_key] = (stream_url, time.time() + 14400)

            if stream_url and self.state == STATE_RADIO and self._resolve_id == req_id:
                self.current_idx = idx
                self.cursor_idx = idx
                self._update_quote()

                if shutil.which("ffmpeg"):
                    reconnect_args = ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5"] if str(stream_url).startswith("http") else []
                    cmd = [
                        "ffmpeg", "-y",
                        *reconnect_args,
                        "-i", stream_url,
                        "-filter_complex", "[0:a]asplit=2[out1][out2]",
                        "-map", "[out1]", *self.audio_sink_args,
                        "-map", "[out2]", "-flush_packets", "1", "-f", "s16le", "-ac", "1", "-ar", "22050", "-"
                    ]
                    stdout_mode = subprocess.PIPE
                elif shutil.which("mpv"):
                    cmd = ["mpv", "--no-video", "--no-terminal", "--audio-fallback-to-null=yes", stream_url]
                    stdout_mode = subprocess.DEVNULL
                else:
                    cmd = ["aplay", "-q", stream_url]
                    stdout_mode = subprocess.DEVNULL

                with self._audio_lock:
                    if self.state != STATE_RADIO or self._resolve_id != req_id:
                        return
                    self.audio_proc = subprocess.Popen(cmd, stdout=stdout_mode, stderr=subprocess.DEVNULL)
                    self.is_playing = True
                    self._trigger_prefetch_next_track(idx, is_tv=False)
                self.playback_start_time = time.time()
                try:
                    self.track_duration = float(duration) if duration and float(duration) > 0 else 210.0
                except (ValueError, TypeError):
                    self.track_duration = 210.0
                if stdout_mode == subprocess.PIPE:
                    threading.Thread(target=self._audio_spectrum_reader, args=(self.audio_proc,), daemon=True).start()
        except Exception as e:
            print(f"Playback error: {e}")
        finally:
            if self._resolve_id == req_id:
                self.is_resolving = False

    # --- VIDEO CONTROLS (TV MODE: 4:3 DISPLAY FILL & FLOATING OSD) ---

    def generate_tv_overlay_image(self, track: Dict[str, str], output_path: str = "/tmp/tv_ui_overlay.png") -> str:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 0))  # 100% transparent center where video plays

        # 1. Top Bar
        pygame.draw.rect(overlay, (46, 52, 64, 215), (0, 0, SCREEN_WIDTH, 54))
        pygame.draw.line(overlay, (67, 76, 94, 230), (0, 54), (SCREEN_WIDTH, 54), 1)

        lx = 20
        if self.logo_img:
            l_scaled = pygame.transform.smoothscale(self.logo_img, (32, 32))
            overlay.blit(l_scaled, (lx, 11))
            lx += 42

        title_surf = self._load_font(19, bold=True).render("Station North", True, NORD6)
        overlay.blit(title_surf, (lx, 7))

        sub_surf = self._load_font(12, bold=True).render("SNfetchPLAYER • Television Broadcast", True, NORD8)
        overlay.blit(sub_surf, (lx, 30))

        # Battery & Time
        bat_cap, is_charging = self.hardware.get_battery_info()
        bat_color = NORD14 if bat_cap > 20 else NORD11
        bx, by = 840, 20
        pygame.draw.rect(overlay, bat_color, (bx, by, 22, 14), width=1, border_radius=2)
        pygame.draw.rect(overlay, bat_color, (bx + 22, by + 3, 2, 8))
        fill_w = max(2, int(18 * (bat_cap / 100.0)))
        pygame.draw.rect(overlay, bat_color, (bx + 2, by + 2, fill_w, 10))

        charge_symbol = "⚡ " if is_charging else ""
        bat_surf = self._load_font(12, bold=True).render(f"{charge_symbol}{bat_cap}%", True, bat_color)
        overlay.blit(bat_surf, (bx + 28, 18))

        time_str = self.hardware.get_time_str()
        time_surf = self._load_font(18, bold=True).render(time_str, True, NORD6)
        overlay.blit(time_surf, (940, 16))

        # 2. Lower Card: Title, Artist & 5 Chunky Buttons
        card2_x = 20
        card2_y = 514
        card2_w = 984
        card2_h = 238
        cx = card2_x + card2_w // 2

        pygame.draw.rect(overlay, (46, 52, 64, 225), (card2_x, card2_y, card2_w, card2_h), border_radius=16)
        pygame.draw.rect(overlay, (67, 76, 94, 240), (card2_x, card2_y, card2_w, card2_h), width=2, border_radius=16)

        title = track.get("title", "Unknown Title")
        artist = track.get("artist", "Unknown Artist")

        title_font = self._load_font(26, bold=True)
        if len(title) > 38:
            title_font = self._load_font(22, bold=True)
        t_surf = title_font.render(title, True, NORD6)
        overlay.blit(t_surf, (cx - t_surf.get_width() // 2, card2_y + 16))

        a_surf = self._load_font(17).render(artist, True, NORD4)
        overlay.blit(a_surf, (cx - a_surf.get_width() // 2, card2_y + 48))

        btn_area_x = card2_x + 16
        btn_area_w = card2_w - 32
        btn_y = card2_y + 82
        self.draw_5_button_cockpit(overlay, btn_area_x, btn_y, btn_area_w, height=140)

        pygame.image.save(overlay, output_path)
        return output_path

    def launch_video_playback(self, start_idx: int, manual_trigger: bool = True):
        """Plays fullscreen video with 4:3 display fill and floating OSD on manual skip"""
        self.stop_audio()
        curr_idx = start_idx
        show_osd_this_track = manual_trigger

        import select

        while True:
            if curr_idx < 0 or curr_idx >= len(self.playlist):
                break

            if not pygame.display.get_init():
                pygame.display.init()
                self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DISPLAY_FLAGS)
                pygame.mouse.set_visible(False)

            track = self.playlist[curr_idx]
            track_title = track.get("title", "Title")
            track_artist = track.get("artist", "Artist")

            # 2:1 Rotation Check (unless Repeat mode is on)
            if not self.shuffle_mgr.is_repeat_mode and self.station_mgr.should_play_station_content():
                tv_id_path = self.station_mgr.get_next_tv_id()
                if tv_id_path and tv_id_path.exists():
                    self.station_mgr.reset_counter()
                    self._play_tv_station_id_fullscreen(tv_id_path)
                    if not pygame.display.get_init():
                        pygame.display.init()
                        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DISPLAY_FLAGS)
                        pygame.mouse.set_visible(False)

            # Interactive Crate-Digging Resolver (0ms on pre-fetch cache hit, 60 FPS vinyl animation if loading)
            stream_url, was_cancelled = self.resolve_stream_interactive(track, is_tv=True)
            if was_cancelled:
                logging.info("User cancelled video resolution via [B]. Returning to menu.")
                break

            if not stream_url:
                logging.warning(f"Could not resolve stream for '{track_title}'. Checking next track...")
                self._render_crate_digging_frame("STREAM RESOLVER", f"Unable to resolve stream: {track_title}\nChecking connection...", 0.0)
                pygame.display.flip()
                time.sleep(1.0)
                curr_idx = self.shuffle_mgr.advance_next()
                show_osd_this_track = False
                continue

            # Bauchbinde via nativem ASS-Untertitel (blendet sanft ein und nach 4.8s automatisch aus)
            osd_file = generate_osd_ass(track, show_osd=True, is_repeat=self.shuffle_mgr.is_repeat_mode)

            logo_file = APP_DIR / "sn_logo.png"
            logo_path = str(logo_file) if logo_file.exists() else str(Path("sn_logo.png").resolve())

            is_local = track.get("is_local", False) or not (stream_url.startswith("http://") or stream_url.startswith("https://"))
            is_audio_only = is_local and Path(stream_url).suffix.lower() in {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".opus", ".aac"}
            if not is_audio_only:
                # 4:3 Display-Fill + 65% Logo Transparenz + Elegante Bauchbinde (Crash-sicheres Scale & Crop)
                vf_filter = (
                    f"scale=1024:768:force_original_aspect_ratio=increase,crop=1024:768 [main]; "
                    f"movie={logo_path},scale=175:-1,format=rgba,colorchannelmixer=aa=0.65 [logo]; "
                    f"[main][logo] overlay=main_w-overlay_w-30:main_h-overlay_h-26, "
                    f"ass='{osd_file}'"
                )
                cmd = [
                    "ffplay",
                    "-fs",
                    "-autoexit",
                    "-sync", "audio",
                    "-window_title", f"STATION NORTH • {track_artist} - {track_title}",
                    "-loglevel", "error",
                    "-vf", vf_filter,
                    stream_url
                ]
            else:
                # Local audio file played in TV mode: show Station North visualizer waves + ASS banner
                vf_filter = (
                    f"movie={logo_path},scale=240:-1,format=rgba,colorchannelmixer=aa=0.75 [logo]; "
                    f"[in][logo] overlay=(W-w)/2:(H-h)/2, "
                    f"ass='{osd_file}'"
                )
                cmd = [
                    "ffplay",
                    "-fs",
                    "-autoexit",
                    "-sync", "audio",
                    "-window_title", f"STATION NORTH • {track_artist} - {track_title}",
                    "-loglevel", "error",
                    "-showmode", "waves",
                    "-vf", vf_filter,
                    stream_url
                ]

            player_bin = "ffplay" if shutil.which("ffplay") else ("mpv" if shutil.which("mpv") else None)
            if not player_bin:
                logging.error("Neither ffplay nor mpv found on device.")
                self.show_loading_screen("VIDEO PLAYER NOT FOUND", "Install ffplay or mpv for video playback")
                time.sleep(2.0)
                return

            if player_bin == "mpv":
                cmd = [
                    "mpv",
                    "--fullscreen",
                    "--geometry=1024x768",
                    "--audio-fallback-to-null=yes",
                    "--keep-open=no",
                    "--force-window=yes",
                    f"--sub-file={osd_file}",
                    f"--title=STATION NORTH • {track_artist} - {track_title}",
                    stream_url,
                ]

            try:
                pygame.display.quit()
                play_start_time = time.time()
                env = os.environ.copy()
                env["WAYLAND_DISPLAY"] = env.get("WAYLAND_DISPLAY", "wayland-1")
                env["XDG_RUNTIME_DIR"] = env.get("XDG_RUNTIME_DIR", "/var/run/0-runtime-dir")
                env["SWAYSOCK"] = env.get("SWAYSOCK", "/var/run/0-runtime-dir/sway-ipc.0.sock")
                proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL)
                self._trigger_prefetch_next_track(curr_idx, is_tv=True)

                def _sway_focus():
                    time.sleep(0.15)
                    for _ in range(5):
                        subprocess.run(["swaymsg", '[app_id="mpv"] move to output DSI-1, fullscreen enable, focus'], capture_output=True)
                        subprocess.run(["swaymsg", '[class="mpv"] move to output DSI-1, fullscreen enable, focus'], capture_output=True)
                        time.sleep(0.2)
                threading.Thread(target=_sway_focus, daemon=True).start()
            except Exception as e:
                logging.error(f"Failed to launch video player: {e}")
                if not pygame.display.get_init():
                    pygame.display.init()
                    self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DISPLAY_FLAGS)
                    pygame.mouse.set_visible(False)
                self.show_loading_screen("PLAYBACK ERROR", f"Cannot launch video player: {e}")
                time.sleep(2.0)
                return

            input_reader = LinuxGamepadReader()
            action = "AUTO"
            is_paused = False

            while proc.poll() is None:
                # 1. Universal PortMaster Kill: SELECT (314 / 15) + START (315 / 25)
                if ({314, 315}.issubset(input_reader.pressed_keys) or 
                    {15, 25}.issubset(input_reader.pressed_keys) or
                    {314, 28}.issubset(input_reader.pressed_keys)):
                    input_reader.close()
                    proc.kill()
                    sys.exit(0)

                # 2. Immediate [B] / ESC / Q: Exit video (instant, 0ms)
                if any(k in input_reader.pressed_keys for k in (305, 1, 14, 16)):
                    action = "EXIT"
                    break

                events = input_reader.read_events(0.04)
                should_break = False
                for ev_type, ev_code, ev_val in events:
                    if ev_type == 1 and ev_val == 1:  # EV_KEY press
                        # START / P / ENTER -> Play / Pause
                        if ev_code in (315, 25, 706, 28):
                            if is_paused:
                                os.kill(proc.pid, signal.SIGCONT)
                                is_paused = False
                            else:
                                os.kill(proc.pid, signal.SIGSTOP)
                                is_paused = True

                        # [B] / ESC / Q -> Zurueck / Exit
                        elif ev_code in (305, 1, 14, 16):
                            action = "EXIT"
                            should_break = True
                            break

                        # [►] Steuerkreuz / R1 / DPAD Right -> Naechstes Video
                        elif ev_code in (547, 311, 106):
                            if is_paused:
                                os.kill(proc.pid, signal.SIGCONT)
                            action = "NEXT"
                            should_break = True
                            break

                        # [◄] Steuerkreuz / L1 / DPAD Left -> Vorheriges Video
                        elif ev_code in (546, 310, 105):
                            if is_paused:
                                os.kill(proc.pid, signal.SIGCONT)
                            action = "PREV"
                            should_break = True
                            break

                        # [X] & [Y] -> Repeat Toggle
                        elif ev_code in (307, 33, 308, 21):
                            self.shuffle_mgr.toggle_repeat()

                    elif ev_type == 3 and ev_code in (0, 16):  # EV_ABS code 0 (ABS_X)
                        # Safe deadzone: require > 18000 (over 55% deflection) to avoid drift skips!
                        if ev_val > 18000:
                            if is_paused:
                                os.kill(proc.pid, signal.SIGCONT)
                            action = "NEXT"
                            should_break = True
                            break
                        elif ev_val < -18000:
                            if is_paused:
                                os.kill(proc.pid, signal.SIGCONT)
                            action = "PREV"
                            should_break = True
                            break

                if should_break:
                    break

            input_reader.close()
            if is_paused:
                try:
                    os.kill(proc.pid, signal.SIGCONT)
                except Exception:
                    pass

            # Sicherstellen, dass ffplay sofort beendet wird
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=0.3)
                except Exception:
                    proc.kill()
                proc.kill()
                try:
                    proc.wait(timeout=0.3)
                except Exception:
                    pass

            elapsed = time.time() - play_start_time

            # If a video stream ends abnormally fast (< 3.0s) without user input, auto-advance to next video
            if action == "AUTO" and elapsed < 3.0:
                action = "NEXT"

            if action == "EXIT":
                self.current_idx = curr_idx
                self.cursor_idx = curr_idx
                break
            elif action == "NEXT" or action == "AUTO":
                self.station_mgr.increment_counter()
                curr_idx = self.shuffle_mgr.advance_next()
                self.current_idx = curr_idx
                self.cursor_idx = curr_idx
                self._update_quote()
                show_osd_this_track = True
            elif action == "PREV":
                curr_idx = self.shuffle_mgr.step_prev()
                self.current_idx = curr_idx
                self.cursor_idx = curr_idx
                self._update_quote()
                show_osd_this_track = True

        if not pygame.display.get_init():
            pygame.display.init()
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DISPLAY_FLAGS)
            pygame.mouse.set_visible(False)
        pygame.display.set_caption("Station North • SNfetchPLAYER")
        time.sleep(0.12)
        pygame.event.clear()
        self.is_playing = False

    def _play_tv_station_id_fullscreen(self, clip_path: Path) -> bool:
        logo_file = APP_DIR / "sn_logo.png"
        logo_path = str(logo_file) if logo_file.exists() else str(Path("sn_logo.png").resolve())

        # 4:3 Display-Fill + 65% Logo Transparenz unten rechts (Crash-sicheres Scale & Crop)
        vf_filter = (
            f"scale=1024:768:force_original_aspect_ratio=increase,crop=1024:768 [main]; "
            f"movie={logo_path},scale=175:-1,format=rgba,colorchannelmixer=aa=0.65 [logo]; "
            f"[main][logo] overlay=main_w-overlay_w-30:main_h-overlay_h-26"
        )

        player_bin = "ffplay" if shutil.which("ffplay") else ("mpv" if shutil.which("mpv") else None)
        if not player_bin:
            logging.warning("Video player not found for TV station ID.")
            return True

        if player_bin == "mpv":
            cmd = [
                "mpv",
                "--fullscreen",
                "--geometry=1024x768",
                "--audio-fallback-to-null=yes",
                "--keep-open=no",
                "--force-window=yes",
                "--title=STATION NORTH TV IDENT",
                str(clip_path),
            ]
        else:
            cmd = [
                "ffplay",
                "-fs",
                "-autoexit",
                "-sync", "audio",
                "-window_title", "STATION NORTH TV IDENT",
                "-loglevel", "error",
                "-vf", vf_filter,
                str(clip_path)
            ]

        try:
            pygame.display.quit()
            env = os.environ.copy()
            env["WAYLAND_DISPLAY"] = env.get("WAYLAND_DISPLAY", "wayland-1")
            env["XDG_RUNTIME_DIR"] = env.get("XDG_RUNTIME_DIR", "/var/run/0-runtime-dir")
            env["SWAYSOCK"] = env.get("SWAYSOCK", "/var/run/0-runtime-dir/sway-ipc.0.sock")
            proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL)

            def _sway_focus_id():
                time.sleep(0.15)
                for _ in range(5):
                    subprocess.run(["swaymsg", '[app_id="mpv"] move to output DSI-1, fullscreen enable, focus'], capture_output=True)
                    time.sleep(0.2)
            threading.Thread(target=_sway_focus_id, daemon=True).start()
        except Exception as e:
            logging.error(f"Failed to play TV ID: {e}")
            if not pygame.display.get_init():
                pygame.display.init()
                self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DISPLAY_FLAGS)
                pygame.mouse.set_visible(False)
            return True

        input_reader = LinuxGamepadReader()
        interrupted = False

        while proc.poll() is None:
            # 1. Kill Combo: SELECT + START
            if ({314, 315}.issubset(input_reader.pressed_keys) or 
                {15, 25}.issubset(input_reader.pressed_keys) or 
                {314, 28}.issubset(input_reader.pressed_keys)):
                input_reader.close()
                proc.kill()
                sys.exit(0)

            # 2. Immediate [B] / ESC: Skip TV ID
            if any(k in input_reader.pressed_keys for k in (305, 1, 14, 16)):
                interrupted = True
                break

            events = input_reader.read_events(0.04)
            should_break = False
            for ev_type, ev_code, ev_val in events:
                if ev_type == 1 and ev_val == 1:
                    if ev_code in (547, 546, 311, 310, 106, 105, 305, 307, 1, 33, 706, 16):
                        interrupted = True
                        should_break = True
                        break
            if should_break:
                break

        input_reader.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.3)
            except Exception:
                proc.kill()
            except Exception:
                pass
        time.sleep(0.15)
        return not interrupted

    # --- CHRONICLES AUDIO (FAITH NARRATION) ---
    def stop_chronicles_audio(self):
        with self._audio_lock:
            proc = self.chronicles_proc
            self.chronicles_proc = None
            self.chronicles_playing = False
            try:
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
            except Exception:
                pass
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=0.3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

    def toggle_chronicles_audio(self):
        if self.chronicles_playing:
            self.stop_chronicles_audio()
            return

        if not self.chronicles_data or self.chronicles_idx >= len(self.chronicles_data):
            return

        item = self.chronicles_data[self.chronicles_idx]
        panel_id = item.get("id", self.chronicles_idx + 1)
        audio_name = f"p_{panel_id:03d}.mp3"
        audio_paths = [
            APP_DIR / "assets/comic/audio" / audio_name,
            Path("assets/comic/audio") / audio_name
        ]
        target_path = None
        for ap in audio_paths:
            if ap.exists():
                target_path = ap
                break

        if target_path:
            self.stop_chronicles_audio()
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.load(str(target_path))
                    pygame.mixer.music.play()
                    self.chronicles_playing = True
                elif shutil.which("mpv"):
                    cmd = ["mpv", "--no-video", "--really-quiet", "--no-terminal", str(target_path)]
                    self.chronicles_proc = subprocess.Popen(cmd)
                    self.chronicles_playing = True
                elif shutil.which("ffplay"):
                    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", str(target_path)]
                    self.chronicles_proc = subprocess.Popen(cmd)
                    self.chronicles_playing = True
            except Exception as sub_err:
                logging.error(f"Narration playback error: {sub_err}")
        else:
            logging.warning(f"Voiceover audio file '{audio_name}' not found. Please sync media assets in Settings.")

    # =========================================================================
    # RENDER HELPER: THE 5-BUTTON PASTEL COCKPIT (MATCHING ANDROID APP)
    # =========================================================================
    def draw_5_button_cockpit(self, surface: pygame.Surface, x: int, y: int, width: int, height: int = 138):
        """Draws the massive, chunky 5-button pastel pill cockpit with geometric vector icons and focus ring"""
        num_btn = 5
        gap = 14
        btn_w = (width - (num_btn - 1) * gap) // num_btn

        buttons = [
            {"col": NORD7, "title": "Fullscreen"},
            {"col": NORD12, "title": "Prev Track"},
            {"col": NORD9, "title": "Play/Pause"},
            {"col": NORD15, "title": "Next Track"},
            {"col": NORD13, "title": "Repeat Loop"}
        ]

        for i, btn in enumerate(buttons):
            bx = x + i * (btn_w + gap)
            b_rect = pygame.Rect(bx, y, btn_w, height)
            is_focused = (i == self.cockpit_focus_idx)
            icon_col = NORD0 # Dark Polar Night charcoal

            # 1. Pastel Pill Surface
            pygame.draw.rect(surface, btn["col"], b_rect, border_radius=14)

            # 2. Glowing Android TV Focus Border
            if is_focused:
                pygame.draw.rect(surface, NORD6, (bx - 3, y - 3, btn_w + 6, height + 6), width=3, border_radius=16)
                pygame.draw.rect(surface, NORD8, (bx - 5, y - 5, btn_w + 10, height + 10), width=2, border_radius=18)

            # 3. Active Repeat Border
            if i == 4 and self.shuffle_mgr.is_repeat_mode:
                pygame.draw.rect(surface, NORD6, b_rect, width=3, border_radius=14)

            # 4. Geometric Vector Icons (Centered in Button)
            cx = bx + btn_w // 2
            cy = y + height // 2

            if i == 0:
                # Fullscreen: 4 Expanding Corner Brackets
                d = 16
                arm = 9
                w = 4
                # Top-Left
                pygame.draw.line(surface, icon_col, (cx - d, cy - d), (cx - d + arm, cy - d), w)
                pygame.draw.line(surface, icon_col, (cx - d, cy - d), (cx - d, cy - d + arm), w)
                # Top-Right
                pygame.draw.line(surface, icon_col, (cx + d, cy - d), (cx + d - arm, cy - d), w)
                pygame.draw.line(surface, icon_col, (cx + d, cy - d), (cx + d, cy - d + arm), w)
                # Bottom-Left
                pygame.draw.line(surface, icon_col, (cx - d, cy + d), (cx - d + arm, cy + d), w)
                pygame.draw.line(surface, icon_col, (cx - d, cy + d), (cx - d, cy + d - arm), w)
                # Bottom-Right
                pygame.draw.line(surface, icon_col, (cx + d, cy + d), (cx + d - arm, cy + d), w)
                pygame.draw.line(surface, icon_col, (cx + d, cy + d), (cx + d, cy - d + arm), w)

            elif i == 1:
                # Previous Track: Vertical bar + Left-pointing triangle (|◄)
                pygame.draw.rect(surface, icon_col, (cx - 16, cy - 16, 5, 32), border_radius=1)
                pts = [(cx - 12, cy), (cx + 14, cy - 16), (cx + 14, cy + 16)]
                pygame.draw.polygon(surface, icon_col, pts)

            elif i == 2:
                # Play / Pause
                if self.is_playing:
                    # Pause: Twin vertical bars (||)
                    pygame.draw.rect(surface, icon_col, (cx - 12, cy - 16, 8, 32), border_radius=2)
                    pygame.draw.rect(surface, icon_col, (cx + 4, cy - 16, 8, 32), border_radius=2)
                else:
                    # Play: Right-pointing triangle (▶)
                    pts = [(cx - 10, cy - 16), (cx + 16, cy), (cx - 10, cy + 16)]
                    pygame.draw.polygon(surface, icon_col, pts)

            elif i == 3:
                # Next Track: Triangle pointing right + Vertical bar (►|)
                pts = [(cx - 14, cy - 16), (cx + 12, cy), (cx - 14, cy + 16)]
                pygame.draw.polygon(surface, icon_col, pts)
                pygame.draw.rect(surface, icon_col, (cx + 12, cy - 16, 5, 32), border_radius=1)

            elif i == 4:
                # Repeat Loop
                rx = cx - 18
                ry = cy - 13
                rw = 36
                rh = 26
                lw = 3
                # Top horizontal
                pygame.draw.line(surface, icon_col, (rx, ry), (rx + rw, ry), lw)
                # Right vertical
                pygame.draw.line(surface, icon_col, (rx + rw, ry), (rx + rw, ry + rh), lw)
                # Bottom horizontal
                pygame.draw.line(surface, icon_col, (rx + rw, ry + rh), (rx, ry + rh), lw)
                # Left vertical
                pygame.draw.line(surface, icon_col, (rx, ry + rh), (rx, ry), lw)
                # Arrowhead top right (pointing right)
                pygame.draw.polygon(surface, icon_col, [(rx + rw, ry - 6), (rx + rw + 8, ry), (rx + rw, ry + 6)])
                # Arrowhead bottom left (pointing left)
                pygame.draw.polygon(surface, icon_col, [(rx, ry + rh - 6), (rx - 8, ry + rh), (rx, ry + rh + 6)])

                # "1" inside badge if loop mode is active
                if self.shuffle_mgr.is_repeat_mode:
                    one_surf = self._load_font(14, bold=True).render("1", True, icon_col)
                    surface.blit(one_surf, (cx - one_surf.get_width() // 2, cy - one_surf.get_height() // 2))

    # =========================================================================
    # VECTOR ICON HELPERS FOR SPLASH SCREEN & MAIN MENU (NORD SPECIFICATION)
    # =========================================================================
    def _draw_vertical_gradient(self, surface: pygame.Surface, rect: pygame.Rect, col_top: Tuple[int, int, int], col_bottom: Tuple[int, int, int], border_radius: int = 0):
        """Draws a high-precision vertical linear gradient with optional rounded corners"""
        temp = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        h = max(rect.height - 1, 1)
        for y in range(rect.height):
            factor = y / h
            r = int(col_top[0] + factor * (col_bottom[0] - col_top[0]))
            g = int(col_top[1] + factor * (col_bottom[1] - col_top[1]))
            b = int(col_top[2] + factor * (col_bottom[2] - col_top[2]))
            pygame.draw.line(temp, (r, g, b), (0, y), (rect.width, y))

        if border_radius > 0:
            mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, rect.width, rect.height), border_radius=border_radius)
            temp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

        surface.blit(temp, rect.topleft)

    def _draw_horizontal_gradient(self, surface: pygame.Surface, rect: pygame.Rect, col_left: Tuple[int, int, int], col_right: Tuple[int, int, int], border_radius: int = 0):
        """Draws a high-precision horizontal linear gradient with optional rounded corners"""
        temp = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        w = max(rect.width - 1, 1)
        for x in range(rect.width):
            factor = x / w
            r = int(col_left[0] + factor * (col_right[0] - col_left[0]))
            g = int(col_left[1] + factor * (col_right[1] - col_left[1]))
            b = int(col_left[2] + factor * (col_right[2] - col_left[2]))
            pygame.draw.line(temp, (r, g, b), (x, 0), (x, rect.height))

        if border_radius > 0:
            mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, rect.width, rect.height), border_radius=border_radius)
            temp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

        surface.blit(temp, rect.topleft)

    def _draw_splash_radio_icon(self, surface: pygame.Surface, cx: int, cy: int, col: Tuple[int, int, int]):
        """Vector Retro Boombox / Radio Tuner icon"""
        bw, bh = 114, 64
        bx, by = cx - bw // 2, cy - bh // 2 + 6
        pygame.draw.rect(surface, col, (bx, by, bw, bh), width=3, border_radius=10)
        # Handle
        hw, hh = 56, 16
        pygame.draw.rect(surface, col, (cx - hw // 2, by - hh + 2, hw, hh), width=3, border_radius=6)
        # Left Speaker
        sp_r = 18
        sp_lx = bx + 28
        sp_ly = by + bh // 2 + 2
        pygame.draw.circle(surface, col, (sp_lx, sp_ly), sp_r, width=3)
        pygame.draw.circle(surface, col, (sp_lx, sp_ly), 6)
        # Right Speaker
        sp_rx = bx + bw - 28
        pygame.draw.circle(surface, col, (sp_rx, sp_ly), sp_r, width=3)
        pygame.draw.circle(surface, col, (sp_rx, sp_ly), 6)
        # Center Cassette Door
        cw, ch = 30, 20
        pygame.draw.rect(surface, col, (cx - cw // 2, by + 12, cw, ch), width=2, border_radius=4)
        pygame.draw.line(surface, col, (cx - 10, by + 22), (cx + 10, by + 22), 2)
        # Antenna
        pygame.draw.line(surface, col, (bx + bw - 14, by), (bx + bw + 18, by - 26), 3)
        pygame.draw.circle(surface, col, (bx + bw + 18, by - 26), 4)

    def _draw_splash_tv_icon(self, surface: pygame.Surface, cx: int, cy: int, col: Tuple[int, int, int]):
        """Vector Retro CRT Television with twin rabbit-ear antennas"""
        tw, th = 114, 68
        tx, ty = cx - tw // 2, cy - th // 2 + 6
        pygame.draw.rect(surface, col, (tx, ty, tw, th), width=3, border_radius=12)
        # CRT Screen
        sw, sh = 72, 52
        sx, sy = tx + 8, ty + 8
        pygame.draw.rect(surface, col, (sx, sy, sw, sh), width=3, border_radius=10)
        # Control dials
        kx = tx + tw - 16
        pygame.draw.circle(surface, col, (kx, ty + 20), 7, width=2)
        pygame.draw.circle(surface, col, (kx, ty + 42), 7, width=2)
        # Rabbit-Ear Antennas
        pygame.draw.line(surface, col, (cx - 12, ty), (cx - 38, ty - 28), 3)
        pygame.draw.circle(surface, col, (cx - 38, ty - 28), 4)
        pygame.draw.line(surface, col, (cx + 12, ty), (cx + 38, ty - 28), 3)
        pygame.draw.circle(surface, col, (cx + 38, ty - 28), 4)
        # Feet
        pygame.draw.line(surface, col, (tx + 18, ty + th), (tx + 12, ty + th + 8), 3)
        pygame.draw.line(surface, col, (tx + tw - 18, ty + th), (tx + tw - 12, ty + th + 8), 3)

    def _draw_splash_chronicles_icon(self, surface: pygame.Surface, cx: int, cy: int, col: Tuple[int, int, int]):
        """Vector Graphic Novel / Open Lore Tome icon"""
        sy_top = cy - 24
        sy_bot = cy + 42
        pygame.draw.line(surface, col, (cx, sy_top), (cx, sy_bot), 3)
        # Left Page
        left_pts = [
            (cx, sy_top),
            (cx - 24, sy_top - 6),
            (cx - 52, sy_top + 2),
            (cx - 52, sy_bot - 4),
            (cx - 24, sy_bot - 10),
            (cx, sy_bot)
        ]
        pygame.draw.lines(surface, col, False, left_pts, 3)
        # Left page text lines
        pygame.draw.line(surface, col, (cx - 42, sy_top + 14), (cx - 12, sy_top + 9), 2)
        pygame.draw.line(surface, col, (cx - 42, sy_top + 24), (cx - 12, sy_top + 19), 2)
        pygame.draw.line(surface, col, (cx - 42, sy_top + 34), (cx - 16, sy_top + 29), 2)

        # Right Page
        right_pts = [
            (cx, sy_top),
            (cx + 24, sy_top - 6),
            (cx + 52, sy_top + 2),
            (cx + 52, sy_bot - 4),
            (cx + 24, sy_bot - 10),
            (cx, sy_bot)
        ]
        pygame.draw.lines(surface, col, False, right_pts, 3)
        # Right page text lines
        pygame.draw.line(surface, col, (cx + 12, sy_top + 9), (cx + 42, sy_top + 14), 2)
        pygame.draw.line(surface, col, (cx + 12, sy_top + 19), (cx + 42, sy_top + 24), 2)
        pygame.draw.line(surface, col, (cx + 16, sy_top + 29), (cx + 42, sy_top + 34), 2)
        # Bookmark ribbon
        pygame.draw.line(surface, col, (cx, sy_bot), (cx + 8, sy_bot + 16), 3)

    def _draw_pro_gear_icon(self, surface: pygame.Surface, cx: int, cy: int, col: Tuple[int, int, int]):
        """High-precision mechanical gear with 8 chamfered teeth and center hub"""
        r_outer = 38
        r_inner = 28
        r_hub = 12
        pts = []
        num_teeth = 8
        for i in range(num_teeth * 2):
            angle = (i * 360 / (num_teeth * 2)) - 90
            rad = math.radians(angle)
            r = r_outer if i % 2 == 0 else r_inner
            pts.append((cx + math.cos(rad) * r, cy + math.sin(rad) * r))
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.circle(surface, (20, 24, 32), (cx, cy), r_hub)
        pygame.draw.circle(surface, col, (cx, cy), r_hub, 2)

    def _draw_pro_exit_icon(self, surface: pygame.Surface, cx: int, cy: int, col: Tuple[int, int, int]):
        """Professional Emergency Exit / Running Man & Doorway Symbol"""
        door_w, door_h = 24, 60
        door_x, door_y = cx + 8, cy - door_h // 2
        pygame.draw.rect(surface, col, (door_x, door_y, door_w, door_h), width=4, border_radius=4)
        # Arrow through door
        pygame.draw.line(surface, col, (door_x + 6, cy), (door_x + 18, cy), 3)
        pygame.draw.line(surface, col, (door_x + 12, cy - 6), (door_x + 18, cy), 3)
        pygame.draw.line(surface, col, (door_x + 12, cy + 6), (door_x + 18, cy), 3)

        # Running figure heading towards door
        hx, hy = cx - 18, cy - 20
        pygame.draw.circle(surface, col, (hx, hy), 7)
        pygame.draw.line(surface, col, (hx, hy + 7), (hx + 4, cy + 6), 5)
        pygame.draw.line(surface, col, (hx + 2, hy + 10), (hx + 16, hy + 4), 4)
        pygame.draw.line(surface, col, (hx + 2, hy + 10), (hx - 12, hy + 16), 4)
        pygame.draw.line(surface, col, (hx + 4, cy + 6), (hx + 18, cy + 22), 5)
        pygame.draw.line(surface, col, (hx + 4, cy + 6), (hx - 14, cy + 20), 5)

    # =========================================================================
    # RENDERER 1: 3D ROTATING LOGO SPLASH & DOCKING TRANSITION (v6.0)
    # =========================================================================
    def _draw_3d_intro_splash(self):
        """Cinematic 3D Y-Axis Rotating Coin-Spin Logo Intro with Harmonized Frame (Glitch-Free)"""
        self.screen.fill(NORD0)

        # Standard Harmonized Top Bar WITHOUT logo (logo will dock here after spin)
        self.draw_top_bar(custom_title="STATION NORTH", subtitle="SYSTEM BOOT SEQUENCE • 3D INITIALIZATION", show_logo=False)

        now = time.time()
        elapsed = now - self.intro_start_time

        cx = SCREEN_WIDTH // 2
        cy = 388
        base_w = 340
        base_h = 212

        # 1. Cached smooth pulsing radial cyan glow behind center
        pulse = 1.0 + 0.12 * math.sin(elapsed * 4.0)
        glow_size = int(460 * pulse)
        if self._cached_radial_glow is None:
            self._cached_radial_glow = pygame.Surface((460, 460), pygame.SRCALPHA)
            for r in range(220, 20, -16):
                alpha = int(14 * (1.0 - r / 220))
                pygame.draw.circle(self._cached_radial_glow, (136, 192, 208, alpha), (230, 230), r)

        scaled_glow = pygame.transform.smoothscale(self._cached_radial_glow, (glow_size, glow_size))
        self.screen.blit(scaled_glow, (cx - glow_size // 2, cy - glow_size // 2))

        # 2. 3D Coin Spin (Y-Axis rotation)
        self.intro_angle = elapsed * 3.6
        rad = self.intro_angle
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        face_is_front = (cos_a >= 0)
        curr_scale_x = abs(cos_a)
        curr_w = max(4, int(base_w * curr_scale_x))

        logo_src = self.logo_large if self.logo_large else self.logo_img
        if logo_src:
            # Determine active face: Front or Mirrored Back
            if face_is_front:
                active_face = logo_src
            else:
                active_face = pygame.transform.flip(logo_src, True, False)
                # Apply shadow shading to reverse side
                shaded = active_face.copy()
                shaded.fill((165, 185, 210), special_flags=pygame.BLEND_RGB_MULT)
                active_face = shaded

            # Scale active face ONCE (super fast & fluid on ARM)
            face_scaled = pygame.transform.smoothscale(active_face, (curr_w, base_h))

            # 3D Depth / Extrusion Rim (projects behind the face)
            rim_depth = int(14 * abs(sin_a))
            # Direction: when rotating counter-clockwise, rim projects along -sin_a
            rim_dir = -1 if sin_a > 0 else 1
            if rim_depth > 1:
                rim_surf = face_scaled.copy()
                rim_surf.fill((46, 62, 84), special_flags=pygame.BLEND_RGB_MULT)
                step = 2
                for ox in range(rim_depth, 0, -step):
                    self.screen.blit(rim_surf, (cx - curr_w // 2 + ox * rim_dir, cy - base_h // 2))

            # Blit Main Face on top of extrusion with dynamic 3D lighting (no glitchy white rect bars!)
            if face_is_front:
                # Subtle specular highlight on front face based on angle to camera
                shine_val = int(255 * (0.82 + 0.18 * cos_a))
                lit_face = face_scaled.copy()
                lit_face.fill((shine_val, shine_val, shine_val), special_flags=pygame.BLEND_RGB_MULT)
                self.screen.blit(lit_face, (cx - curr_w // 2, cy - base_h // 2))
            else:
                self.screen.blit(face_scaled, (cx - curr_w // 2, cy - base_h // 2))

        # 3. Typography below logo (Large & Crisp for 3.5" screen)
        brand_surf = self._load_font(36, bold=True).render("STATION NORTH", True, NORD6)
        self.screen.blit(brand_surf, (cx - brand_surf.get_width() // 2, cy + 130))

        status_s = self._load_font(18, bold=True).render("INITIALIZING LIVE AUDIO & BROADCAST STREAMS...", True, NORD8)
        pygame.draw.circle(self.screen, NORD7, (cx - status_s.get_width() // 2 - 16, cy + 185), 6)
        self.screen.blit(status_s, (cx - status_s.get_width() // 2, cy + 175))

        # Harmonized Bottom Bar with Skip button
        self.draw_bottom_bar(pills=[("A", "Skip", NORD8)], right_text="v7.0 • Back to the Rules")

    def _draw_intro_transition(self, ease: float):
        """Smooth docking transition from 3D rotating splash to docked header & 3+2 menu"""
        slide_offset = int(60 * (1.0 - ease))
        self._draw_3plus2_main_menu(slide_offset=slide_offset, alpha=int(255 * ease), show_top_logo=False)

        # Flying / Docking Logo interpolates from center to top-left corner
        start_x, start_y = SCREEN_WIDTH // 2, 388
        start_w, start_h = 340, 212

        dest_x, dest_y = 20 + 33, 7 + 21
        dest_w, dest_h = 67, 42

        cur_cx = int(start_x + (dest_x - start_x) * ease)
        cur_cy = int(start_y + (dest_y - start_y) * ease)
        cur_w = max(4, int(start_w + (dest_w - start_w) * ease))
        cur_h = max(4, int(start_h + (dest_h - start_h) * ease))

        logo_src = self.logo_large if self.logo_large else self.logo_img
        if logo_src:
            scaled = pygame.transform.smoothscale(logo_src, (cur_w, cur_h))
            self.screen.blit(scaled, (cur_cx - cur_w // 2, cur_cy - cur_h // 2))

    # =========================================================================
    # RENDERER 1: MAIN 3+2 TILE MENU (v6.0 AUTHENTIC NORD AURORA)
    # =========================================================================
    def draw_splash_screen(self):
        now = time.time()
        # 1. Handle 3D Intro Splash Phase
        if self.intro_active:
            elapsed = now - self.intro_start_time
            if not self.intro_transitioning and elapsed > 3.8:
                self.intro_transitioning = True
                self.intro_transition_start = now

            if self.intro_transitioning:
                t_elapsed = now - self.intro_transition_start
                t_progress = min(1.0, t_elapsed / 0.50)
                # Smooth ease-out cubic
                ease = 1.0 - math.pow(1.0 - t_progress, 3)
                if t_progress >= 1.0:
                    self.intro_active = False
                    self.intro_transitioning = False
                else:
                    self._draw_intro_transition(ease)
                    return
            else:
                self._draw_3d_intro_splash()
                return

        # 2. Main 3+2 Tile Menu
        self._draw_3plus2_main_menu()

    def _draw_3plus2_main_menu(self, slide_offset: int = 0, alpha: int = 255, show_top_logo: bool = True):
        self.screen.fill(NORD0)

        # 1. Top Bar / Header with official SN Logo
        self.draw_top_bar(custom_title="STATION NORTH", subtitle="CYBERDECK MEDIA SUITE • v7.0", show_logo=show_top_logo)

        # Layout Dimensions (Total width 910px centered on 1024px screen)
        card_w = 230
        card_h = 320
        gap = 20
        right_col_w = 160
        right_card_h = (card_h - gap) // 2
        total_w = 3 * card_w + right_col_w + 3 * gap
        start_x = (SCREEN_WIDTH - total_w) // 2

        # 2. Upper Section: Asset Synchronisation & Queen Directives Quote Box
        box_w = 910
        box_h = 286
        box_x = start_x
        box_y = 74 + slide_offset

        pygame.draw.rect(self.screen, (34, 39, 49), (box_x, box_y, box_w, box_h), border_radius=16)

        # Subtle dark-tinted background artwork if available
        if hasattr(self, "quote_bg_surfaces") and self.quote_bg_surfaces:
            bg_surf = self.quote_bg_surfaces[self.current_quote_bg_idx % len(self.quote_bg_surfaces)]
            self.screen.blit(bg_surf, (box_x, box_y))

        pygame.draw.rect(self.screen, (46, 52, 64), (box_x, box_y, box_w, box_h), width=2, border_radius=16)

        j_found, t_found, c_found, total_found, pct = self.get_asset_stats()
        is_celebrating = (self.sync_completed_timestamp > 0 and (time.time() - self.sync_completed_timestamp < 5.0))
        show_progress_bar = self.sync_active or is_celebrating or (pct < 99.0)

        # Randomized Lore & Quotes from sprueche.json in Aurora Colors
        self._check_cycle_quote()

        if show_progress_bar:
            if self.sync_active:
                disp_pct = self.sync_pct
                hdr_text = f"DOWNLOADING MEDIA ASSETS ({int(disp_pct)}% READY)"
                hdr_col = NORD8
                sub_text = self.sync_status_text if self.sync_status_text else "Downloading media pack from GitHub..."
                sub_col = NORD5
            elif is_celebrating:
                hdr_text = "✦ ALL MEDIA ASSETS SYNCHRONIZED (100% READY) ✦"
                hdr_col = NORD14
                sub_text = "174 Station Jingles   •   42 Retro TV Idents (4:3)   •   131 Chronicles Pages & Lore Audio Ready"
                sub_col = (255, 255, 255)
            else:
                hdr_text = f"ASSETS INCOMPLETE ({int(pct)}% READY) • OFFLINE MODE"
                hdr_col = NORD13
                sub_text = f"Local Assets: {j_found}/174 Jingles   •   {t_found}/42 TV Idents   •   {c_found}/131 Chronicles"
                sub_col = NORD5

            # Header with indicator dot
            pygame.draw.circle(self.screen, hdr_col, (box_x + 34, box_y + 32), 7)
            sync_title = self._load_font(21, bold=True).render(hdr_text, True, hdr_col)
            self.screen.blit(sync_title, (box_x + 50, box_y + 20))

            # Subtext breakdown
            details_surf = self._load_font(17, bold=True).render(sub_text, True, sub_col)
            self.screen.blit(details_surf, (box_x + 28, box_y + 52))

            # Segmented LED Progress Bar (Cyberdeck Style: 30 rectangles with 4px gap)
            bar_w = box_w - 56
            bar_h = 16
            bar_x = box_x + 28
            bar_y = box_y + 82
            num_segs = 30
            seg_gap = 4
            total_gaps = (num_segs - 1) * seg_gap
            seg_w = (bar_w - total_gaps) // num_segs
            curr_pct = self.sync_pct if self.sync_active else (100.0 if pct >= 99.0 else pct)
            active_segs = int((min(100.0, curr_pct) / 100.0) * num_segs)

            for s_idx in range(num_segs):
                sx = bar_x + s_idx * (seg_w + seg_gap)
                s_rect = pygame.Rect(sx, bar_y, seg_w, bar_h)
                if s_idx < active_segs:
                    seg_col = NORD8 if self.sync_active else (NORD14 if pct >= 99.0 else NORD13)
                    pygame.draw.rect(self.screen, seg_col, s_rect, border_radius=3)
                else:
                    pygame.draw.rect(self.screen, (22, 26, 34), s_rect, border_radius=3)
                    pygame.draw.rect(self.screen, (38, 44, 56), s_rect, width=1, border_radius=3)

            # Divider line and lower quote section
            div_y = box_y + 112
            pygame.draw.line(self.screen, (46, 52, 64), (box_x + 28, div_y), (box_x + box_w - 28, div_y), 1)

            badge_surf = self._load_font(14, bold=True).render("✦ QUEEN DIRECTIVES // TRANSMISSION FEED ✦", True, NORD9)
            self.screen.blit(badge_surf, (box_x + 28, box_y + 122))

            max_visible_lines = 4
            q_font = self._load_font(19, bold=True)
            max_q_w = box_w - 56
            quote_lines = self._render_wrapped_lines(f"“{self.current_quote}”", q_font, max_q_w)
            visible_lines = quote_lines[:max_visible_lines]
            line_y = box_y + 148
            line_h = 26
            for line in visible_lines:
                q_surf = q_font.render(line, True, self.current_quote_color)
                self.screen.blit(q_surf, (box_x + 28, line_y))
                line_y += line_h
        else:
            # Variant B: Pure Queen Directives Console aligned to the bottom of the box!
            # The upper area stays completely free of text to let the artwork shine.
            badge_font = self._load_font(18, bold=True)
            badge_surf = badge_font.render("✦ THE QUEEN'S DIRECTIVES // TRANSMISSION FEED ✦", True, NORD8)
            badge_h = badge_surf.get_height()

            # Measure quote block (adaptive font size to guarantee 0 clipping)
            max_q_w = box_w - 56
            q_font = self._load_font(21, bold=True)
            quote_lines = self._render_wrapped_lines(f"“{self.current_quote}”", q_font, max_q_w)
            if len(quote_lines) >= 3:
                q_font = self._load_font(18, bold=True)
                quote_lines = self._render_wrapped_lines(f"“{self.current_quote}”", q_font, max_q_w)

            max_visible_lines = 6
            visible_lines = quote_lines[:max_visible_lines]
            line_h = 30 if len(visible_lines) <= 2 else 26
            quote_block_h = len(visible_lines) * line_h

            total_text_h = badge_h + 10 + quote_block_h
            bottom_pad = 22
            badge_y = (box_y + box_h) - bottom_pad - total_text_h
            quote_start_y = badge_y + badge_h + 10

            # Glowing indicator dot & Badge text
            pygame.draw.circle(self.screen, NORD8, (box_x + 34, badge_y + badge_h // 2), 6)
            self.screen.blit(badge_surf, (box_x + 48, badge_y))

            line_y = quote_start_y
            for line in visible_lines:
                q_surf = q_font.render(line, True, self.current_quote_color)
                self.screen.blit(q_surf, (box_x + 28, line_y))
                line_y += line_h

        # 3. Lower Section: 3+2 Grid Setup (Balanced for 48px footer and upper box)
        card_y = box_y + box_h + 18

        # 5 Target Rectangles: 0=Radio, 1=TV, 2=Chronicles, 3=Settings, 4=Exit
        target_rects = [
            pygame.Rect(start_x, card_y, card_w, card_h),
            pygame.Rect(start_x + (card_w + gap), card_y, card_w, card_h),
            pygame.Rect(start_x + 2 * (card_w + gap), card_y, card_w, card_h),
            pygame.Rect(start_x + 3 * (card_w + gap), card_y, right_col_w, right_card_h),
            pygame.Rect(start_x + 3 * (card_w + gap), card_y + right_card_h + gap, right_col_w, right_card_h),
        ]

        # Snappy, Responsive Selection Border Interpolation (Lerp with Snap)
        dest_rect = target_rects[min(max(0, self.splash_cursor), 4)]
        if self._cursor_fx is None:
            self._cursor_fx = float(dest_rect.x)
            self._cursor_fy = float(dest_rect.y)
            self._cursor_fw = float(dest_rect.width)
            self._cursor_fh = float(dest_rect.height)
        else:
            lerp_speed = 0.55
            self._cursor_fx += (dest_rect.x - self._cursor_fx) * lerp_speed
            self._cursor_fy += (dest_rect.y - self._cursor_fy) * lerp_speed
            self._cursor_fw += (dest_rect.width - self._cursor_fw) * lerp_speed
            self._cursor_fh += (dest_rect.height - self._cursor_fh) * lerp_speed

            if abs(dest_rect.x - self._cursor_fx) < 1.5: self._cursor_fx = float(dest_rect.x)
            if abs(dest_rect.y - self._cursor_fy) < 1.5: self._cursor_fy = float(dest_rect.y)
            if abs(dest_rect.width - self._cursor_fw) < 1.5: self._cursor_fw = float(dest_rect.width)
            if abs(dest_rect.height - self._cursor_fh) < 1.5: self._cursor_fh = float(dest_rect.height)

        cur_rect = pygame.Rect(int(self._cursor_fx), int(self._cursor_fy), int(self._cursor_fw), int(self._cursor_fh))

        # The 3 Main Cards (Left)
        cards_left = [
            {"title": "Radio", "top_col": NORD8, "bot_col": NORD9, "icon": self._draw_splash_radio_icon},
            {"title": "TV", "top_col": NORD7, "bot_col": NORD14, "icon": self._draw_splash_tv_icon},
            {"title": "Chronicles", "top_col": NORD13, "bot_col": NORD12, "icon": self._draw_splash_chronicles_icon}
        ]

        for i, c in enumerate(cards_left):
            rect = target_rects[i]
            is_sel = (i == self.splash_cursor)

            # Solid deep charcoal base card
            pygame.draw.rect(self.screen, (20, 24, 32), rect, border_radius=16)

            # Inset Artwork Square with Nord Aurora gradient
            pad = 8
            art_size = card_w - (pad * 2)
            art_rect = pygame.Rect(rect.x + pad, rect.y + pad, art_size, art_size)
            self._draw_vertical_gradient(self.screen, art_rect, c["top_col"], c["bot_col"], border_radius=12)

            # Draw Handcrafted Vector Icon in center of artwork
            c["icon"](self.screen, rect.x + card_w // 2, rect.y + pad + art_size // 2, (255, 255, 255))

            # Text in bottom black banner
            txt_surf = self._load_font(24, bold=True).render(c["title"], True, (255, 255, 255))
            text_y = rect.y + pad + art_size + (card_h - (pad + art_size) - txt_surf.get_height()) // 2
            self.screen.blit(txt_surf, (rect.x + (card_w - txt_surf.get_width()) // 2, text_y))

            # Subtle inactive border
            if not is_sel:
                pygame.draw.rect(self.screen, (40, 46, 58), rect, width=2, border_radius=16)

        # Card 4: Settings (Top Right, Polar Slate Nord1 to Nord2)
        rect_set = target_rects[3]
        is_sel_settings = (self.splash_cursor == 3)
        pygame.draw.rect(self.screen, (20, 24, 32), rect_set, border_radius=16)
        pad_r = 6
        art_set_rect = pygame.Rect(rect_set.x + pad_r, rect_set.y + pad_r, right_col_w - pad_r * 2, right_card_h - pad_r * 2)
        self._draw_vertical_gradient(self.screen, art_set_rect, NORD1, NORD2, border_radius=12)
        self._draw_pro_gear_icon(self.screen, rect_set.x + right_col_w // 2, rect_set.y + right_card_h // 2, (255, 255, 255))
        if not is_sel_settings:
            pygame.draw.rect(self.screen, (40, 46, 58), rect_set, width=2, border_radius=16)

        # Card 5: Exit (Bottom Right, Aurora Crimson Red Nord11)
        rect_exit = target_rects[4]
        is_sel_exit = (self.splash_cursor == 4)
        pygame.draw.rect(self.screen, (20, 24, 32), rect_exit, border_radius=16)
        art_exit_rect = pygame.Rect(rect_exit.x + pad_r, rect_exit.y + pad_r, right_col_w - pad_r * 2, right_card_h - pad_r * 2)
        self._draw_vertical_gradient(self.screen, art_exit_rect, NORD11, (130, 32, 44), border_radius=12)
        self._draw_pro_exit_icon(self.screen, rect_exit.x + right_col_w // 2, rect_exit.y + right_card_h // 2, (255, 255, 255))
        if not is_sel_exit:
            pygame.draw.rect(self.screen, (40, 46, 58), rect_exit, width=2, border_radius=16)

        # Smooth, Punchy Glowing Selection Border around active card (White & Cyan Glow)
        glow_rect = cur_rect.inflate(8, 8)
        pygame.draw.rect(self.screen, (136, 192, 208), glow_rect, width=4, border_radius=18)
        pygame.draw.rect(self.screen, (255, 255, 255), cur_rect.inflate(4, 4), width=2, border_radius=17)

        # 4. Harmonized Bottom Footer Bar with Pills (NO [B] Exit!)
        menu_pills = [
            ("A", "Launch", NORD8),
            ("D-Pad", "Navigate", NORD7),
            ("Sel", "Settings", NORD9)
        ]
        self.draw_bottom_bar(pills=menu_pills, right_text="v7.0 • Back to the Rules")

    # =========================================================================
    # RENDERER 2: RADIO ZEN VISUALIZER (FULLSCREEN SPECTRUM ANALYZER)
    # =========================================================================
    def draw_radio_zen_mode(self):
        """Full 1024x768 Zen Visualizer screen for ambient desk listening"""
        self.screen.fill(NORD0)

        # 1. Fullscreen Visualizer across bottom 440px
        self.visualizer.update(is_active=self.is_playing)
        self.visualizer.draw(self.screen, x=32, y=260, width=960, max_h=440)

        # 2. Station North Logo Watermark (top left, proportional un-distorted)
        if self.logo_large:
            orig_w, orig_h = self.logo_large.get_size()
            wm_h = 60
            wm_w = int(wm_h * (orig_w / orig_h))
            wm = pygame.transform.smoothscale(self.logo_large, (wm_w, wm_h))
            wm.set_alpha(180)
            self.screen.blit(wm, (40, 36))

        # Station Title / Clock (top right)
        clock_str = HardwareManager.get_time_str()
        time_s = self._load_font(26, bold=True).render(clock_str, True, NORD4)
        self.screen.blit(time_s, (SCREEN_WIDTH - 44 - time_s.get_width(), 42))

        # 3. Track Info (Centered, Large & Floating)
        track = self.playlist[self.current_idx] if self.current_idx < len(self.playlist) else {}
        title = track.get("title", "Unknown Title")
        artist = track.get("artist", "The Queen's Frequency" if self.is_station_drop else "Unknown Artist")
        if self.is_station_drop:
            title = self.station_drop_title

        cx = SCREEN_WIDTH // 2
        t_font = self._load_font(34, bold=True)
        if len(title) > 30:
            t_font = self._load_font(26, bold=True)
        t_surf = t_font.render(title, True, NORD6)
        self.screen.blit(t_surf, (cx - t_surf.get_width() // 2, 90))

        a_surf = self._load_font(20, bold=True).render(artist, True, NORD8)
        self.screen.blit(a_surf, (cx - a_surf.get_width() // 2, 138))

        # Auto-Hide Check (4.0 Sekunden Inaktivitaet)
        if time.time() - self.radio_osd_last_interaction > 4.0:
            self.radio_osd_visible = False

        if self.radio_osd_visible:
            # Schwebendes On-Screen-Menue (5 Chunky Buttons)
            card_w = 900
            card_h = 136
            card_x = (SCREEN_WIDTH - card_w) // 2
            card_y = 596

            osd_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            pygame.draw.rect(osd_surf, (46, 52, 64, 235), (0, 0, card_w, card_h), border_radius=18)
            pygame.draw.rect(osd_surf, (67, 76, 94, 255), (0, 0, card_w, card_h), width=2, border_radius=18)
            self.screen.blit(osd_surf, (card_x, card_y))

            self.draw_5_button_cockpit(self.screen, card_x + 16, card_y + 14, card_w - 32, height=108)
        else:
            # Dezenter Hinweis wenn ausgeblendet
            hint_s = self._load_font(13).render("ON-SCREEN MENU HIDDEN • PRESS D-PAD TO SHOW • [B] TO EXIT", True, NORD3)
            self.screen.blit(hint_s, (cx - hint_s.get_width() // 2, 738))

    # =========================================================================
    # RENDERER 3: TOP-BAR (STATUSLEISTE MIT FIXIERTEN SLOTS)
    # =========================================================================
    def draw_top_bar(self, custom_title: Optional[str] = None, subtitle: Optional[str] = None, show_logo: bool = True):
        pygame.draw.rect(self.screen, COLOR_BAR_BG, (0, 0, SCREEN_WIDTH, 56))
        pygame.draw.line(self.screen, (50, 56, 68), (0, 56), (SCREEN_WIDTH, 56), 2)

        lx = 20
        logo_w = self.logo_img.get_width() if self.logo_img else 67
        if show_logo and self.logo_img:
            self.screen.blit(self.logo_img, (lx, 7))
        lx += logo_w + 14

        title_text = custom_title if custom_title else "STATION NORTH"
        title_surf = self._load_font(24, bold=True).render(title_text, True, NORD6)
        self.screen.blit(title_surf, (lx, 7))

        sub_text = subtitle if subtitle else "CYBERDECK MEDIA SUITE • v7.0"
        sub_surf = self._load_font(15, bold=True).render(sub_text, True, NORD8)
        self.screen.blit(sub_surf, (lx, 33))

        # Statusleiste rechts (WLAN, Batterie & Uhrzeit)
        # 1. WLAN Symbol (Nord8 Cyan wenn aktiv, Nord3 wenn getrennt)
        is_wifi = self.hardware.get_wifi_status()
        wifi_col = NORD8 if is_wifi else NORD3
        wx, wy = 770, 18
        pygame.draw.circle(self.screen, wifi_col, (wx + 10, wy + 16), 2)
        pygame.draw.arc(self.screen, wifi_col, (wx + 5, wy + 9, 10, 10), 0.785, 2.356, 2)
        pygame.draw.arc(self.screen, wifi_col, (wx + 1, wy + 3, 18, 18), 0.785, 2.356, 2)

        # 2. Batterie
        bat_cap, is_charging = self.hardware.get_battery_info()
        bat_color = NORD14 if bat_cap > 20 else NORD11
        bx, by = 825, 18
        pygame.draw.rect(self.screen, bat_color, (bx, by, 24, 16), width=2, border_radius=3)
        pygame.draw.rect(self.screen, bat_color, (bx + 24, by + 4, 3, 8))
        fill_w = max(2, int(18 * (bat_cap / 100.0)))
        pygame.draw.rect(self.screen, bat_color, (bx + 3, by + 3, fill_w, 10))

        charge_symbol = "⚡" if is_charging else ""
        bat_surf = self._load_font(15, bold=True).render(f"{charge_symbol}{bat_cap}%", True, bat_color)
        self.screen.blit(bat_surf, (bx + 32, 17))

        # 3. Uhrzeit
        time_str = self.hardware.get_time_str()
        time_surf = self._load_font(22, bold=True).render(time_str, True, NORD6)
        self.screen.blit(time_surf, (932, 14))

    # =========================================================================
    # RENDERER 3: RADIO MODE (THE QUEEN'S FREQUENCY - 2-CARD STAGE)
    # =========================================================================
    def draw_radio_dashboard(self):
        self.screen.fill(NORD0)
        self.draw_top_bar(custom_title="STATION NORTH • RADIO", subtitle="THE QUEEN'S FREQUENCY • LIVE STREAM")

        track = self.playlist[self.current_idx] if self.current_idx < len(self.playlist) else {}
        title = track.get("title", "Unknown Title")
        artist = track.get("artist", "Unknown Artist")

        # 1. Obere Karte: Visualizer Bühne
        card1_x = 20
        card1_y = 66
        card1_w = 984
        card1_h = 368
        pygame.draw.rect(self.screen, NORD1, (card1_x, card1_y, card1_w, card1_h), border_radius=16)
        pygame.draw.rect(self.screen, NORD2, (card1_x, card1_y, card1_w, card1_h), width=1, border_radius=16)

        cx = card1_x + card1_w // 2

        if self.is_station_drop:
            drop_s = self._load_font(36, bold=True).render("STATION NORTH IDENT", True, NORD8)
            self.screen.blit(drop_s, (cx - drop_s.get_width() // 2, card1_y + 40))
            sub_s = self._load_font(20, bold=True).render("LIVE JINGLE BROADCAST", True, NORD13)
            self.screen.blit(sub_s, (cx - sub_s.get_width() // 2, card1_y + 85))
        else:
            sn_s = self._load_font(54, bold=True).render("SN", True, NORD6)
            self.screen.blit(sn_s, (cx - sn_s.get_width() // 2, card1_y + 20))

            sub_sn = self._load_font(18, bold=True).render("Station North", True, NORD4)
            self.screen.blit(sub_sn, (cx - sub_sn.get_width() // 2, card1_y + 76))

            stream_s = self._load_font(22, bold=True).render("SN-RADIO AUDIO STREAM", True, NORD8)
            self.screen.blit(stream_s, (cx - stream_s.get_width() // 2, card1_y + 106))

        # Vollbreiter organischer Wellen-Visualizer mit bunten Kappen
        vis_x = card1_x + 14
        vis_w = card1_w - 28
        vis_y = card1_y + 142
        vis_h = 212
        self.visualizer.update(is_active=self.is_playing)
        self.visualizer.draw(self.screen, x=vis_x, y=vis_y, width=vis_w, max_h=vis_h)

        # 2. Untere Karte: Song-Titel, Artist & 5 Große Chunky Buttons
        card2_x = 20
        card2_y = 448
        card2_w = 984
        card2_h = 260
        pygame.draw.rect(self.screen, NORD1, (card2_x, card2_y, card2_w, card2_h), border_radius=16)
        pygame.draw.rect(self.screen, NORD2, (card2_x, card2_y, card2_w, card2_h), width=1, border_radius=16)

        # Song-Titel zentriert
        disp_title = self.station_drop_title if self.is_station_drop else title
        title_font = self._load_font(30, bold=True)
        if len(disp_title) > 34:
            title_font = self._load_font(24, bold=True)
        t_surf = title_font.render(disp_title, True, NORD6)
        self.screen.blit(t_surf, (cx - t_surf.get_width() // 2, card2_y + 14))

        # Interpret zentriert
        disp_artist = "The Queen's Frequency" if self.is_station_drop else artist
        a_surf = self._load_font(20, bold=True).render(disp_artist, True, NORD4)
        self.screen.blit(a_surf, (cx - a_surf.get_width() // 2, card2_y + 50))

        # 5 Große Chunky Buttons
        btn_area_x = card2_x + 16
        btn_area_w = card2_w - 32
        btn_y = card2_y + 90
        self.draw_5_button_cockpit(self.screen, btn_area_x, btn_y, btn_area_w, height=155)

        # Harmonized Bottom Bar with Pills
        radio_pills = [
            ("A", "Play / Pause", NORD8),
            ("◄/►", "Track", NORD14),
            ("X", "Zen Fullscreen", NORD13),
            ("B", "Main Menu", NORD11)
        ]
        self.draw_bottom_bar(pills=radio_pills, right_text="Station North • Radio")

    # =========================================================================
    # RENDERER 4: TV MODE (TELEVISION BROADCAST - 2-CARD STAGE)
    # =========================================================================
    def draw_tv_dashboard(self):
        self.screen.fill(NORD0)
        self.draw_top_bar(custom_title="STATION NORTH • TV", subtitle="TELEVISION BROADCAST • 4:3 CRT MODE")

        track = self.playlist[self.current_idx] if self.current_idx < len(self.playlist) else {}
        title = track.get("title", "Unknown Title")
        artist = track.get("artist", "Unknown Artist")
        yt_id = track.get("youtubeId", "")

        # 1. Obere Karte: Großes Video-Thumbnail & Fullscreen-Trigger
        card1_x = 20
        card1_y = 66
        card1_w = 984
        card1_h = 368
        card1_rect = pygame.Rect(card1_x, card1_y, card1_w, card1_h)

        pygame.draw.rect(self.screen, NORD1, card1_rect, border_radius=16)
        pygame.draw.rect(self.screen, NORD2, card1_rect, width=1, border_radius=16)

        thumb_surf = self.thumb_mgr.get_thumbnail(yt_id, title, size=(card1_w, card1_h))
        self.screen.blit(thumb_surf, (card1_x, card1_y))

        # Dezent abgedunkelter Scrim für maximale Textlesbarkeit
        scrim = pygame.Surface((card1_w, card1_h), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, 85))
        self.screen.blit(scrim, (card1_x, card1_y))

        cx = card1_x + card1_w // 2

        # "PRESS for FULLSCREEN" zentriert
        p_font = self._load_font(36, bold=True)
        f_font = self._load_font(56, bold=True)

        p_sh = p_font.render("PRESS for", True, (15, 18, 24))
        f_sh = f_font.render("FULLSCREEN", True, (15, 18, 24))
        self.screen.blit(p_sh, (cx - p_sh.get_width() // 2 + 2, card1_y + 112))
        self.screen.blit(f_sh, (cx - f_sh.get_width() // 2 + 3, card1_y + 162))

        p_s = p_font.render("PRESS for", True, NORD6)
        f_s = f_font.render("FULLSCREEN", True, NORD6)
        self.screen.blit(p_s, (cx - p_s.get_width() // 2, card1_y + 110))
        self.screen.blit(f_s, (cx - f_s.get_width() // 2, card1_y + 160))

        # SN Wasserzeichen unten rechts
        if self.logo_large:
            wm_w, wm_h = 76, 76
            wm = pygame.transform.smoothscale(self.logo_large, (wm_w, wm_h))
            wm.set_alpha(165)
            self.screen.blit(wm, (card1_x + card1_w - wm_w - 24, card1_y + card1_h - wm_h - 22))
            wm_txt = self._load_font(15, bold=True).render("Station North", True, (220, 220, 220))
            wm_txt.set_alpha(165)
            self.screen.blit(wm_txt, (card1_x + card1_w - wm_txt.get_width() - 24, card1_y + card1_h - 22))

        # 2. Untere Karte: Titel, Artist & 5 Große Chunky Buttons
        card2_x = 20
        card2_y = 448
        card2_w = 984
        card2_h = 260
        pygame.draw.rect(self.screen, NORD1, (card2_x, card2_y, card2_w, card2_h), border_radius=16)
        pygame.draw.rect(self.screen, NORD2, (card2_x, card2_y, card2_w, card2_h), width=1, border_radius=16)

        title_font = self._load_font(30, bold=True)
        if len(title) > 34:
            title_font = self._load_font(24, bold=True)
        t_surf = title_font.render(title, True, NORD6)
        self.screen.blit(t_surf, (cx - t_surf.get_width() // 2, card2_y + 14))

        a_surf = self._load_font(20, bold=True).render(artist, True, NORD4)
        self.screen.blit(a_surf, (cx - a_surf.get_width() // 2, card2_y + 50))

        btn_area_x = card2_x + 16
        btn_area_w = card2_w - 32
        btn_y = card2_y + 90
        self.draw_5_button_cockpit(self.screen, btn_area_x, btn_y, btn_area_w, height=155)

        # Harmonized Bottom Bar with Pills
        tv_pills = [
            ("A", "Launch Fullscreen", NORD8),
            ("◄/►", "Channel", NORD14),
            ("B", "Main Menu", NORD11)
        ]
        self.draw_bottom_bar(pills=tv_pills, right_text="Station North • Television")

    def _trigger_cockpit_action(self, idx: int):
        """Executes the action of the focused button (Android TV navigation model)"""
        if idx == 0:
            # Fullscreen Mode [ ]
            if self.state == STATE_RADIO:
                self.is_radio_zen_mode = not self.is_radio_zen_mode
                self.radio_osd_visible = True
                self.radio_osd_last_interaction = time.time()
            elif self.state == STATE_TV:
                self.launch_video_playback(self.current_idx, manual_trigger=True)

        elif idx == 1:
            # Previous Track
            self.current_idx = self.shuffle_mgr.step_prev()
            if self.state == STATE_RADIO:
                self.trigger_play_track_async(self.current_idx)
            elif self.state == STATE_TV:
                self._update_quote()

        elif idx == 2:
            # Play / Pause
            if self.state == STATE_RADIO:
                if self.is_playing:
                    self.stop_audio()
                else:
                    self.trigger_play_track_async(self.current_idx)
            elif self.state == STATE_TV:
                self.launch_video_playback(self.current_idx, manual_trigger=True)

        elif idx == 3:
            # Next Track (increments station jingle counter!)
            self.station_mgr.increment_counter()
            self.current_idx = self.shuffle_mgr.advance_next()
            if self.state == STATE_RADIO:
                self.trigger_play_track_async(self.current_idx)
            elif self.state == STATE_TV:
                self._update_quote()

        elif idx == 4:
            # Repeat Loop Toggle
            self.shuffle_mgr.toggle_repeat()

    # =========================================================================
    # RENDERER 5: THE CHRONICLES (AUDIO-BOX LINKS UNTER BILD, TEXT RECHTS)
    # =========================================================================
    def draw_chronicles_screen(self):
        self.screen.fill(NORD0)
        self.draw_top_bar(custom_title="STATION NORTH • CHRONICLES", subtitle="ILLUSTRATED LORE & NARRATIVE ARCHIVES")

        if not self.chronicles_data:
            msg_s = self.font_hero.render("No Chronicles Data Found (assets/comic)", True, NORD11)
            self.screen.blit(msg_s, ((SCREEN_WIDTH - msg_s.get_width()) // 2, 350))
            self.draw_bottom_bar(pills=[("B", "Main Menu", NORD11)], right_text="Station North • Chronicles")
            return

        item = self.chronicles_data[self.chronicles_idx]
        image_name = item.get("image", "")
        chapter_name = item.get("chapter", "Chapter 1")
        text_content = item.get("text", "")
        panel_id = item.get("id", self.chronicles_idx + 1)

        col1_x = 40
        col1_w = 440
        panel_y = 66
        panel_h = 504
        panel_rect = pygame.Rect(col1_x, panel_y, col1_w, panel_h)
        pygame.draw.rect(self.screen, (0, 0, 0), panel_rect, border_radius=16)
        pygame.draw.rect(self.screen, (35, 42, 54), panel_rect, width=2, border_radius=16)

        # 1. Left Comic Panel: Chapter Header over image, Panel Counter under image
        if ":" in chapter_name:
            chap_parts = chapter_name.split(":", 1)
            c_prefix = chap_parts[0].strip().upper()
            c_sub = chap_parts[1].strip()
            cp_s = self._load_font(15, bold=True).render(c_prefix, True, NORD8)
            self.screen.blit(cp_s, (col1_x + (col1_w - cp_s.get_width()) // 2, panel_y + 10))
            cs_s = self._load_font(18, bold=True).render(c_sub, True, NORD6)
            if cs_s.get_width() > col1_w - 24:
                cs_s = self._load_font(15, bold=True).render(c_sub, True, NORD6)
            self.screen.blit(cs_s, (col1_x + (col1_w - cs_s.get_width()) // 2, panel_y + 30))
        else:
            c_s = self._load_font(18, bold=True).render(chapter_name, True, NORD8)
            if c_s.get_width() > col1_w - 24:
                c_s = self._load_font(15, bold=True).render(chapter_name, True, NORD8)
            self.screen.blit(c_s, (col1_x + (col1_w - c_s.get_width()) // 2, panel_y + 18))

        pygame.draw.line(self.screen, (40, 46, 58), (col1_x + 20, panel_y + 54), (col1_x + col1_w - 20, panel_y + 54), 1)

        # Scale and render Comic Panel in centered image space
        img_area_top = panel_y + 58
        img_area_bottom = panel_y + panel_h - 46
        avail_h = img_area_bottom - img_area_top

        if image_name not in self.chronicles_img_cache:
            img_paths = [
                APP_DIR / "assets/comic" / image_name,
                Path("assets/comic") / image_name
            ]
            loaded_surf = None
            for ip in img_paths:
                if ip.exists():
                    try:
                        raw = pygame.image.load(str(ip))
                        if pygame.display.get_surface():
                            raw = raw.convert()
                        rw, rh = raw.get_size()
                        scale = min((col1_w - 24) / rw, avail_h / rh)
                        target_size = (int(rw * scale), int(rh * scale))
                        scaled = pygame.transform.smoothscale(raw, target_size)
                        loaded_surf = scaled
                        break
                    except Exception:
                        pass
            if loaded_surf:
                self.chronicles_img_cache[image_name] = loaded_surf

        if image_name in self.chronicles_img_cache:
            surf = self.chronicles_img_cache[image_name]
            px = col1_x + (col1_w - surf.get_width()) // 2
            py = img_area_top + (avail_h - surf.get_height()) // 2
            self.screen.blit(surf, (px, py))

        # Panel Navigation & Counter at bottom of comic box
        pygame.draw.line(self.screen, (40, 46, 58), (col1_x + 20, panel_y + panel_h - 44), (col1_x + col1_w - 20, panel_y + panel_h - 44), 1)
        pan_txt = f"◄   PANEL {panel_id} OF {len(self.chronicles_data)}   ►"
        pan_s = self._load_font(16, bold=True).render(pan_txt, True, NORD13)
        self.screen.blit(pan_s, (col1_x + (col1_w - pan_s.get_width()) // 2, panel_y + panel_h - 32))

        # Audio Box direkt unter dem Comic-Panel
        abox_y = panel_y + panel_h + 14
        abox_h = 124
        abox_rect = pygame.Rect(col1_x, abox_y, col1_w, abox_h)
        pygame.draw.rect(self.screen, NORD1, abox_rect, border_radius=12)
        pygame.draw.rect(self.screen, NORD8 if self.chronicles_playing else NORD2, abox_rect, width=2 if self.chronicles_playing else 1, border_radius=12)

        astat_text = "❚❚ NARRATION PLAYING" if self.chronicles_playing else "▶ READ ALOUD [A] / [Start]"
        astat_col = NORD14 if self.chronicles_playing else NORD8
        astat_s = self._load_font(20, bold=True).render(astat_text, True, astat_col)
        self.screen.blit(astat_s, (col1_x + 20, abox_y + 18))

        audio_name = f"Voice Audio #{panel_id:03d} • Queen Faith"
        aname_s = self._load_font(17, bold=True).render(audio_name, True, NORD4)
        self.screen.blit(aname_s, (col1_x + 20, abox_y + 58))

        # 2. Right Column: Narrative Log with clean spacious layout
        col2_x = 504
        col2_w = 480
        col2_y = 66
        col2_h = 642

        tbox_rect = pygame.Rect(col2_x, col2_y, col2_w, col2_h)
        pygame.draw.rect(self.screen, NORD1, tbox_rect, border_radius=16)
        pygame.draw.rect(self.screen, NORD2, tbox_rect, width=1, border_radius=16)

        h_surf = self._load_font(17, bold=True).render("✦ THE CHRONICLES // NARRATIVE LOG ✦", True, NORD8)
        self.screen.blit(h_surf, (col2_x + 24, col2_y + 16))
        pygame.draw.line(self.screen, NORD2, (col2_x + 20, col2_y + 44), (col2_x + col2_w - 20, col2_y + 44), 1)

        # Word wrap text with elevated 21px bold font for crystal clarity
        words = text_content.split()
        lines = []
        cur_line = []
        for w in words:
            test_line = " ".join(cur_line + [w])
            if self.font_body.size(test_line)[0] < (col2_w - 48):
                cur_line.append(w)
            else:
                lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))

        ty = col2_y + 58
        for l in lines[:18]:
            lsurf = self.font_body.render(l, True, NORD6)
            self.screen.blit(lsurf, (col2_x + 24, ty))
            ty += 32

        chronicles_pills = [
            ("◄/►", "Browse Panels", NORD8),
            ("A", "Read Aloud", NORD14),
            ("B", "Main Menu", NORD11)
        ]
        self.draw_bottom_bar(pills=chronicles_pills, right_text="Station North • Chronicles")

    # =========================================================================
    # RENDERER 6: SETTINGS SCREEN
    # =========================================================================
    def draw_settings_screen(self):
        self.screen.fill(NORD0)
        self.draw_top_bar(custom_title="STATION NORTH • SETTINGS", subtitle="STORAGE & SYSTEM CONFIGURATION")

        # Queen Directives Header Quote
        q_header = "\"A well-maintained machine rules without interruption. Manage storage & updates.\" — Queen Directives"
        qh_s = self._load_font(17, bold=True).render(q_header, True, NORD13)
        self.screen.blit(qh_s, ((SCREEN_WIDTH - qh_s.get_width()) // 2, 62))

        # --- LEFT COLUMN: SETTINGS & CONTROLS (x=30, w=480) ---
        j_found, t_found, c_found, tot_found, a_pct = self.get_asset_stats()
        settings_items = [
            ("Radio Active Playlist", self.available_playlists[self.radio_playlist_idx]["title"] if self.available_playlists else "Default"),
            ("TV Active Playlist", self.available_playlists[self.tv_playlist_idx]["title"] if self.available_playlists else "Default"),
            ("Jingle Rotation Frequency", f"Every {self.station_mgr.rotation_interval} Songs" if self.station_mgr.rotation_interval > 0 else "OFF"),
            ("Single-Track Repeat Loop", "ENABLED (Repeat One)" if self.shuffle_mgr.is_repeat_mode else "DISABLED (Shuffle)"),
            ("Master Audio Volume", f"{self.hardware.get_master_volume()}%"),
            ("Screen Backlight Brightness", f"{self.hardware.get_brightness()}%"),
            ("Media Assets & Sync", f"{tot_found}/347 ({int(a_pct)}%) • [A] Check / Sync"),
            ("📖 Open System Handbook", "Press [A] or [►] to Jump to Right Column")
        ]

        start_y = 88
        row_h = 60
        box_w = 480

        for i, (label, val) in enumerate(settings_items):
            ry = start_y + i * (row_h + 8)
            r_rect = pygame.Rect(30, ry, box_w, row_h)
            is_sel = (i == self.settings_cursor and self.settings_column == 0)

            # Highlight item 7 specially as an action button to the handbook
            if i == 7:
                bg_col = (46, 52, 64) if is_sel else (32, 38, 48)
                b_col = NORD7 if is_sel else NORD3
            else:
                bg_col = NORD1 if is_sel else (36, 41, 51)
                b_col = NORD8 if is_sel else NORD2

            pygame.draw.rect(self.screen, bg_col, r_rect, border_radius=12)
            pygame.draw.rect(self.screen, b_col, r_rect, width=2 if is_sel else 1, border_radius=12)

            l_col = NORD8 if is_sel else NORD6
            l_surf = self._load_font(20, bold=True).render(label, True, l_col)
            self.screen.blit(l_surf, (r_rect.x + 20, ry + 8))

            val_col = NORD7 if i == 7 else (NORD14 if "ENABLED" in val or "%" in val else NORD13)
            val_font = self._load_font(18, bold=True)
            val_surf = val_font.render(val, True, val_col)
            # Auto-scale/truncate value text if it exceeds box_w - 40 (440px) to prevent overflow
            if val_surf.get_width() > box_w - 40:
                val_font = self._load_font(15, bold=True)
                val_surf = val_font.render(val, True, val_col)
                if val_surf.get_width() > box_w - 40:
                    short_val = val
                    while val_font.size(short_val + "...")[0] > box_w - 40 and len(short_val) > 6:
                        short_val = short_val[:-1]
                    val_surf = val_font.render(short_val + "...", True, val_col)
            self.screen.blit(val_surf, (r_rect.x + 20, ry + 32))

            if is_sel:
                pygame.draw.rect(self.screen, NORD7 if i == 7 else NORD8, (34, ry + 6, 6, row_h - 12), border_radius=3)

        if self.settings_feedback_msg and (time.time() - self.settings_feedback_time < 3.0):
            fb_s = self._load_font(18, bold=True).render(self.settings_feedback_msg, True, NORD14)
            self.screen.blit(fb_s, (30 + (box_w - fb_s.get_width()) // 2, start_y + len(settings_items) * (row_h + 8) + 4))

        # --- RIGHT COLUMN: HANDBOOK, TV CONTROLS & CURATOR GUIDE (x=530, w=464) ---
        guide_x = 530
        guide_y = 88
        guide_w = 464
        guide_h = 620
        guide_rect = pygame.Rect(guide_x, guide_y, guide_w, guide_h)

        is_guide_focused = (self.settings_column == 1)
        pygame.draw.rect(self.screen, NORD1, guide_rect, border_radius=16)
        pygame.draw.rect(self.screen, NORD8 if is_guide_focused else NORD2, guide_rect, width=2 if is_guide_focused else 1, border_radius=16)

        # Card Header: Cleanly stacked vertically so title and hint never collide
        gh_s = self._load_font(21, bold=True).render("SYSTEM HANDBOOK", True, NORD8)
        self.screen.blit(gh_s, (guide_x + 20, guide_y + 12))

        hint_text = "[▲/▼] Scroll • [◄/B] Back to Menu" if is_guide_focused else "[A] Focus Handbook • [◄] Return"
        hint_col = NORD14 if is_guide_focused else NORD4
        hint_s = self._load_font(14, bold=True).render(hint_text, True, hint_col)
        self.screen.blit(hint_s, (guide_x + 20, guide_y + 36))

        pygame.draw.line(self.screen, NORD2, (guide_x + 18, guide_y + 56), (guide_x + guide_w - 18, guide_y + 56), 1)

        # Scrollable content surface with guaranteed margin protection (< 390px width)
        content_w = guide_w - 36
        content_h = 880
        content_surf = pygame.Surface((content_w, content_h), pygame.SRCALPHA)
        content_surf.fill((0, 0, 0, 0))

        gy = 6

        # Section 1: TV Player Controls (4 dedicated functions)
        t_sec = self._load_font(19, bold=True).render("📺 TV CONTROLS (4 DEDICATED KEYS):", True, NORD7)
        content_surf.blit(t_sec, (4, gy))
        gy += 28

        ctrl_lines = [
            ("START", "Play / Pause Video (Toggle)"),
            ("B", "Exit instantly to Main Menu"),
            ("◄ / ►", "Prev / Next Video (D-Pad/Stick)"),
            ("X / Y", "Toggle Repeat One / Loop")
        ]
        for key_btn, key_desc in ctrl_lines:
            kb_s = self._load_font(16, bold=True).render(f"[{key_btn}]", True, NORD13)
            kd_s = self._load_font(16).render(key_desc, True, NORD6)
            content_surf.blit(kb_s, (6, gy))
            content_surf.blit(kd_s, (82, gy))
            gy += 26

        gy += 12
        pygame.draw.line(content_surf, NORD2, (4, gy), (content_w - 4, gy), 1)
        gy += 14

        # Section 2: Custom Media & Playlists
        m_sec = self._load_font(19, bold=True).render("📁 CUSTOM MEDIA & PLAYLISTS:", True, NORD12)
        content_surf.blit(m_sec, (4, gy))
        gy += 28

        msg1 = [
            "Drop music, videos and playlists directly into the",
            "/playlists/ folder on your micro SD card.",
            "Supports YouTube streams, MP4/MKV videos, and",
            "high-fidelity local MP3 / FLAC audio files."
        ]
        for line in msg1:
            ls = self._load_font(16).render(line, True, NORD4)
            content_surf.blit(ls, (6, gy))
            gy += 24

        gy += 12
        pygame.draw.line(content_surf, NORD2, (4, gy), (content_w - 4, gy), 1)
        gy += 14

        # Section 3: Native Android APK & Curator
        c_sec = self._load_font(19, bold=True).render("📱 NATIVE ANDROID APK & CURATOR:", True, NORD14)
        content_surf.blit(c_sec, (4, gy))
        gy += 28

        msg2 = [
            "For Android handhelds (Odin, Retroid, RG556) or",
            "phones, SNfetchPLAYER is also available as APK!",
            "👉 github.com/StationNorthMedia/SNfetchPLAYER",
            "Includes touch controls and the Curator Console",
            "to create and export custom playlists."
        ]
        for line in msg2:
            ls = self._load_font(16).render(line, True, NORD4)
            content_surf.blit(ls, (6, gy))
            gy += 24

        gy += 12
        pygame.draw.line(content_surf, NORD2, (4, gy), (content_w - 4, gy), 1)
        gy += 14

        # Section 4: Radio Fullscreen Cockpit (OSD)
        r_sec = self._load_font(19, bold=True).render("📻 RADIO FULLSCREEN COCKPIT (OSD):", True, NORD8)
        content_surf.blit(r_sec, (4, gy))
        gy += 28

        msg3 = [
            "Press [X] to launch the fullscreen visualizer.",
            "The 5-button cockpit auto-hides after 4 seconds.",
            "Press any key to show menu • [B] to exit."
        ]
        for line in msg3:
            ls = self._load_font(16).render(line, True, NORD4)
            content_surf.blit(ls, (6, gy))
            gy += 24

        clip_h = guide_h - 72
        self.settings_guide_max_scroll = max(0, gy - clip_h + 20)
        self.screen.blit(content_surf, (guide_x + 16, guide_y + 60), area=pygame.Rect(0, self.settings_guide_scroll_y, content_w, clip_h))

        # Vertical Scrollbar
        track_h = clip_h - 16
        pygame.draw.rect(self.screen, (46, 52, 64), (guide_x + guide_w - 12, guide_y + 66, 4, track_h), border_radius=2)
        if self.settings_guide_max_scroll > 0:
            thumb_ratio = clip_h / float(gy)
            thumb_h = max(24, int(track_h * thumb_ratio))
            scroll_pct = self.settings_guide_scroll_y / float(self.settings_guide_max_scroll)
            thumb_y = guide_y + 66 + int((track_h - thumb_h) * scroll_pct)
            thumb_col = NORD8 if is_guide_focused else NORD2
            pygame.draw.rect(self.screen, thumb_col, (guide_x + guide_w - 13, thumb_y, 6, thumb_h), border_radius=3)

        if self.settings_column == 1:
            settings_pills = [
                ("▲/▼", "Scroll", NORD8),
                ("◄/B", "Back", NORD11)
            ]
        else:
            settings_pills = [
                ("▲/▼", "Navigate", NORD8),
                ("◄/►", "Change", NORD14),
                ("A", "Handbook", NORD13),
                ("B", "Main Menu", NORD11)
            ]
        self.draw_bottom_bar(pills=settings_pills, right_text="Station North • Settings")

    # =========================================================================
    # RENDERER 7: BOTTOM BAR (UNIFIED PILL BADGE FOOTER)
    # =========================================================================
    def draw_bottom_bar(self, pills: Optional[List[Tuple[str, str, Tuple[int, int, int]]]] = None, custom_controls: Optional[str] = None, right_text: str = "v7.0 • Back to the Rules"):
        by = SCREEN_HEIGHT - 48
        pygame.draw.rect(self.screen, (28, 33, 42), (0, by, SCREEN_WIDTH, 48))
        pygame.draw.line(self.screen, (46, 52, 64), (0, by), (SCREEN_WIDTH, by), 2)

        cur_x = 24
        if pills:
            for key, text, col_bg in pills:
                k_txt = self._load_font(15, bold=True).render(key, True, (20, 24, 30))
                kw = max(28, k_txt.get_width() + 14)
                kh = 26
                ky = by + (48 - kh) // 2
                pygame.draw.rect(self.screen, col_bg, (cur_x, ky, kw, kh), border_radius=13)
                self.screen.blit(k_txt, (cur_x + (kw - k_txt.get_width()) // 2, ky + (kh - k_txt.get_height()) // 2))

                lbl = self._load_font(17, bold=True).render(text, True, NORD6)
                self.screen.blit(lbl, (cur_x + kw + 8, ky + (kh - lbl.get_height()) // 2))
                cur_x += kw + 8 + lbl.get_width() + 22
        elif custom_controls:
            ctrl_surf = self._load_font(17, bold=True).render(custom_controls, True, NORD6)
            self.screen.blit(ctrl_surf, (24, by + (48 - ctrl_surf.get_height()) // 2))

        ver_surf = self._load_font(16, bold=True).render(right_text, True, NORD4)
        self.screen.blit(ver_surf, (SCREEN_WIDTH - 24 - ver_surf.get_width(), by + (48 - ver_surf.get_height()) // 2))

    # =========================================================================
    # UNIFIED INPUT DISPATCHER (KEYBOARD & GAMEPAD)
    # =========================================================================
    def _handle_action_key(self, key: int) -> bool:
        """Central key and controller button event handler. Returns False if application should exit."""
        now = time.time()
        # 1. Cooldown filter: Ignore duplicate action keys within 160ms (fixes double-firing from gptokeyb + direct joystick)
        if now - self._last_action_time.get(key, 0.0) < 0.16:
            return True
        self._last_action_time[key] = now

        # 2. State transition debounce: Block action keys for 250ms right after a state change to avoid bleed-through
        if now - self._state_transition_time < 0.25:
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_a, pygame.K_ESCAPE, pygame.K_b, pygame.K_q, pygame.K_BACKSPACE, pygame.K_TAB, pygame.K_s):
                return True

        # Global Settings Toggle [Select] (Tab / S)
        if key in (pygame.K_TAB, pygame.K_s):
            if self.state == STATE_SETTINGS:
                self.state = self.previous_state
            else:
                self.previous_state = self.state
                self.state = STATE_SETTINGS
            self._state_transition_time = now
            pygame.event.clear()
            return True

        # --- SPLASH SCREEN (3+2 TILE MATRIX & 3D INTRO) ---
        if self.state == STATE_SPLASH:
            if self.intro_active:
                # Any button skips intro directly into the menu
                self.intro_active = False
                self.intro_transitioning = False
                self._state_transition_time = now
                return True

            if key == pygame.K_LEFT:
                if self.splash_cursor == 0:
                    self.splash_cursor = 3
                elif self.splash_cursor in (1, 2):
                    self.splash_cursor -= 1
                elif self.splash_cursor in (3, 4):
                    self.splash_cursor = 2
            elif key == pygame.K_RIGHT:
                if self.splash_cursor in (0, 1):
                    self.splash_cursor += 1
                elif self.splash_cursor == 2:
                    self.splash_cursor = 3
                elif self.splash_cursor in (3, 4):
                    self.splash_cursor = 0
            elif key == pygame.K_UP:
                if self.splash_cursor == 4:
                    self.splash_cursor = 3
                elif self.splash_cursor == 3:
                    self.splash_cursor = 4
            elif key == pygame.K_DOWN:
                if self.splash_cursor == 3:
                    self.splash_cursor = 4
                elif self.splash_cursor == 4:
                    self.splash_cursor = 3
            elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_p, pygame.K_a):
                if self.splash_cursor == 0:
                    self.state = STATE_RADIO
                    self._state_transition_time = time.time()
                    pygame.event.clear()
                    self._load_active_playlist(is_tv=False)
                    self.trigger_play_track_async(self.current_idx)
                    return True
                elif self.splash_cursor == 1:
                    self._load_active_playlist(is_tv=True)
                    self.launch_video_playback(self.current_idx, manual_trigger=True)
                    self.state = STATE_SPLASH
                    self.splash_enter_time = time.time()
                    self._state_transition_time = time.time()
                    pygame.event.clear()
                    return True
                elif self.splash_cursor == 2:
                    self.state = STATE_CHRONICLES
                    self._state_transition_time = time.time()
                    pygame.event.clear()
                    return True
                elif self.splash_cursor == 3:
                    self.previous_state = self.state
                    self.state = STATE_SETTINGS
                    self._state_transition_time = time.time()
                    pygame.event.clear()
                    return True
                elif self.splash_cursor == 4:
                    # Clean Exit back to EmulationStation
                    return False
            elif key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE, pygame.K_b):
                # In Main Menu, [B] must NEVER exit the application.
                # Exiting is reserved exclusively for selecting the dedicated Exit card (#4) via [A].
                return True
            return True

        # --- RADIO MODE (ANDROID TV D-PAD FOCUS CURSOR) ---
        elif self.state == STATE_RADIO:
            if self.is_radio_zen_mode:
                if key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE, pygame.K_b):
                    self.is_radio_zen_mode = False
                    self.radio_osd_visible = True
                    return True

                if not self.radio_osd_visible:
                    self.radio_osd_visible = True
                    self.radio_osd_last_interaction = time.time()
                    return True

                self.radio_osd_last_interaction = time.time()
                if key == pygame.K_LEFT:
                    self.cockpit_focus_idx = (self.cockpit_focus_idx - 1) % 5
                elif key == pygame.K_RIGHT:
                    self.cockpit_focus_idx = (self.cockpit_focus_idx + 1) % 5
                elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_a):
                    self._trigger_cockpit_action(self.cockpit_focus_idx)
                elif key in (pygame.K_f, pygame.K_x):
                    self.is_radio_zen_mode = False
                elif key in (pygame.K_p, pygame.K_PAUSE):
                    self._trigger_cockpit_action(2)
                elif key == pygame.K_y:
                    self._trigger_cockpit_action(4)
                elif key == pygame.K_UP:
                    self.station_mgr.increment_counter()
                    self.current_idx = self.shuffle_mgr.advance_previous()
                    self.trigger_play_track_async(self.current_idx)
                elif key == pygame.K_DOWN:
                    self.station_mgr.increment_counter()
                    self.current_idx = self.shuffle_mgr.advance_next()
                    self.trigger_play_track_async(self.current_idx)
                return True

            if key == pygame.K_LEFT:
                self.cockpit_focus_idx = (self.cockpit_focus_idx - 1) % 5
            elif key == pygame.K_RIGHT:
                self.cockpit_focus_idx = (self.cockpit_focus_idx + 1) % 5
            elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_a):
                self._trigger_cockpit_action(self.cockpit_focus_idx)
            elif key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE, pygame.K_b):
                self.stop_audio()
                self.state = STATE_SPLASH
                self.splash_enter_time = time.time()
                self._state_transition_time = time.time()
                pygame.event.clear()
                return True
            elif key in (pygame.K_f, pygame.K_x):
                self.is_radio_zen_mode = True
                self.radio_osd_visible = True
                self.radio_osd_last_interaction = time.time()
            elif key in (pygame.K_p, pygame.K_PAUSE):
                self._trigger_cockpit_action(2)
            elif key == pygame.K_y:
                self._trigger_cockpit_action(4)
            elif key == pygame.K_UP:
                self.station_mgr.increment_counter()
                self.current_idx = self.shuffle_mgr.advance_previous()
                self.trigger_play_track_async(self.current_idx)
            elif key == pygame.K_DOWN:
                self.station_mgr.increment_counter()
                self.current_idx = self.shuffle_mgr.advance_next()
                self.trigger_play_track_async(self.current_idx)
            return True

        # --- TV MODE (ANDROID TV D-PAD FOCUS CURSOR) ---
        elif self.state == STATE_TV:
            if key == pygame.K_LEFT:
                self.cockpit_focus_idx = (self.cockpit_focus_idx - 1) % 5
            elif key == pygame.K_RIGHT:
                self.cockpit_focus_idx = (self.cockpit_focus_idx + 1) % 5
            elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_a):
                self._trigger_cockpit_action(self.cockpit_focus_idx)
            elif key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE, pygame.K_b):
                self.state = STATE_SPLASH
                self.splash_enter_time = time.time()
                self._state_transition_time = time.time()
                pygame.event.clear()
                return True
            elif key in (pygame.K_f, pygame.K_x):
                self._trigger_cockpit_action(0)
            elif key in (pygame.K_p, pygame.K_PAUSE):
                self._trigger_cockpit_action(2)
            elif key == pygame.K_y:
                self._trigger_cockpit_action(4)
            elif key == pygame.K_UP:
                self.station_mgr.increment_counter()
                self.current_idx = self.shuffle_mgr.advance_previous()
                self._update_quote()
            elif key == pygame.K_DOWN:
                self.station_mgr.increment_counter()
                self.current_idx = self.shuffle_mgr.advance_next()
                self._update_quote()
            return True

        # --- CHRONICLES ---
        elif self.state == STATE_CHRONICLES:
            if key == pygame.K_LEFT:
                if self.chronicles_idx > 0:
                    self.stop_chronicles_audio()
                    self.chronicles_idx -= 1
            elif key == pygame.K_RIGHT:
                if self.chronicles_idx < len(self.chronicles_data) - 1:
                    self.stop_chronicles_audio()
                    self.chronicles_idx += 1
            elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_p, pygame.K_a):
                self.toggle_chronicles_audio()
            elif key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE, pygame.K_b):
                self.stop_chronicles_audio()
                self.state = STATE_SPLASH
                self.splash_enter_time = time.time()
                self._state_transition_time = time.time()
                pygame.event.clear()
                return True
            return True

        # --- SETTINGS ---
        elif self.state == STATE_SETTINGS:
            if self.settings_column == 0:
                if key == pygame.K_UP:
                    self.settings_cursor = (self.settings_cursor - 1) % 8
                elif key == pygame.K_DOWN:
                    self.settings_cursor = (self.settings_cursor + 1) % 8
                elif key == pygame.K_LEFT:
                    if self.settings_cursor in (0, 1, 2, 3, 4, 5):
                        self._adjust_setting(delta=-1)
                elif key == pygame.K_RIGHT:
                    if self.settings_cursor in (6, 7):
                        self.settings_column = 1
                    else:
                        self._adjust_setting(delta=1)
                elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_a):
                    if self.settings_cursor == 6:
                        self._execute_setting_action()
                    elif self.settings_cursor == 7:
                        self.settings_column = 1
                    else:
                        self.settings_column = 1
                elif key in (pygame.K_f, pygame.K_x, pygame.K_y, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                    self.settings_column = 1
                elif key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE, pygame.K_b):
                    self.state = self.previous_state
                    self._state_transition_time = time.time()
                    pygame.event.clear()
                    return True
            else:
                # Column 1: Handbook scrolling
                if key == pygame.K_UP:
                    self.settings_guide_scroll_y = max(0, self.settings_guide_scroll_y - 36)
                elif key == pygame.K_DOWN:
                    self.settings_guide_scroll_y = min(self.settings_guide_max_scroll, self.settings_guide_scroll_y + 36)
                elif key in (pygame.K_LEFT, pygame.K_b, pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE, pygame.K_f, pygame.K_x, pygame.K_y, pygame.K_a, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                    self.settings_column = 0
            return True

        return True

    # =========================================================================
    # EVENT LOOP & EXECUTION
    # =========================================================================
    def run(self):
        running = True

        while running:
            self.clock.tick(30)

            # Auto-Advance in Radio Mode (shielded while jingle plays or resolver runs)
            if (self.state == STATE_RADIO and self.audio_proc and 
                self.audio_proc.poll() is not None and 
                not self.is_station_drop and not self.is_resolving):
                
                self.station_mgr.increment_counter()
                if not self.shuffle_mgr.is_repeat_mode:
                    self.current_idx = self.shuffle_mgr.advance_next()
                self.trigger_play_track_async(self.current_idx)

            # Auto-Advance in Chronicles
            if self.state == STATE_CHRONICLES and self.chronicles_playing and self.chronicles_proc and self.chronicles_proc.poll() is not None:
                self.chronicles_proc = None
                self.chronicles_playing = False
                if self.chronicles_idx < len(self.chronicles_data) - 1:
                    self.chronicles_idx += 1
                    self.toggle_chronicles_audio()

            # Universal PortMaster Kill: SELECT (Tab) + START (P)
            keys = pygame.key.get_pressed()
            if (keys[pygame.K_TAB] and keys[pygame.K_p]) or (keys[pygame.K_p] and keys[pygame.K_TAB]):
                self.stop_audio()
                self.stop_chronicles_audio()
                pygame.quit()
                sys.exit(0)



            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if not self._handle_action_key(event.key):
                        running = False

            if self.state == STATE_SPLASH:
                self.draw_splash_screen()
            elif self.state == STATE_RADIO:
                if self.is_radio_zen_mode:
                    self.draw_radio_zen_mode()
                else:
                    self.draw_radio_dashboard()
            elif self.state == STATE_TV:
                self.draw_tv_dashboard()
            elif self.state == STATE_CHRONICLES:
                self.draw_chronicles_screen()
            elif self.state == STATE_SETTINGS:
                self.draw_settings_screen()

            pygame.display.flip()

        self.stop_audio()
        self.stop_chronicles_audio()
        pygame.quit()
        sys.exit(0)

    # --- SETTINGS LOGIC ---
    def _adjust_setting(self, delta: int):
        if self.settings_cursor == 0:
            if self.available_playlists:
                self.radio_playlist_idx = (self.radio_playlist_idx + delta) % len(self.available_playlists)
                self._load_active_playlist(is_tv=False)
        elif self.settings_cursor == 1:
            if self.available_playlists:
                self.tv_playlist_idx = (self.tv_playlist_idx + delta) % len(self.available_playlists)
                self._load_active_playlist(is_tv=True)
        elif self.settings_cursor == 2:
            self.station_mgr.rotation_interval = max(0, min(10, self.station_mgr.rotation_interval + delta))
        elif self.settings_cursor == 3:
            self.shuffle_mgr.toggle_repeat()
        elif self.settings_cursor == 4:
            curr_v = self.hardware.get_master_volume()
            self.hardware.set_master_volume(curr_v + delta * 5)
        elif self.settings_cursor == 5:
            curr_b = self.hardware.get_brightness()
            self.hardware.set_brightness(curr_b + delta * 5)

    def _execute_setting_action(self):
        if self.settings_cursor == 3:
            rep = self.shuffle_mgr.toggle_repeat()
            self.settings_feedback_msg = f"Single-Track Repeat Loop: {'ON' if rep else 'OFF'}"
            self.settings_feedback_time = time.time()
        elif self.settings_cursor == 6:
            self._start_background_asset_sync()
            self.station_mgr._scan_station_assets()
            self._discover_playlists()
            j, t, c, tot, pct = self.get_asset_stats()
            self.settings_feedback_msg = f"Asset Sync Triggered ({tot} found, {int(pct)}% ready)!"
            self.settings_feedback_time = time.time()
