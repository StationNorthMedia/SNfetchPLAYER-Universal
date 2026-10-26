#!/usr/bin/env python3
"""
Station North SNfetchPLAYER - High-Performance TV Companion (PC Edition)
Unified Single-Window Architecture:
- Native QOpenGLWidget + MpvRenderContext (Zero-Copy Framebuffer Injection)
- Normal Mode: 16:9 Video + Bottom Control Card (Title/Artist/5 Pastel Buttons) + Right Metadata Panel
- Live Wikipedia Metadata Integration for currently playing artists
- Fullscreen Mode: 100% Screen Video with Floating Auto-Hide OSD (3.5s)
- Bidirectional JSON-IPC over stdin / stdout with standalone fallback
"""

import sys
import os
import re
import json
import time
import locale
import threading
import urllib.request
import urllib.parse
from pathlib import Path

os.environ.setdefault("LC_NUMERIC", "C")
try:
    locale.setlocale(locale.LC_NUMERIC, "C")
except Exception:
    pass

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtGui import QOpenGLContext, QPixmap

import mpv

# Nord Theme Palette
NORD0 = "#2e3440"
NORD1 = "#3b4252"
NORD2 = "#434c5e"
NORD3 = "#4c566a"
NORD4 = "#d8dee9"
NORD5 = "#e5e9f0"
NORD6 = "#eceff4"
NORD7 = "#8fbcbb"   # Mint (Fullscreen)
NORD8 = "#88c0d0"   # Frost Cyan (Artist/Accent)
NORD9 = "#81a1c1"   # Arctic Blue (Play/Pause)
NORD11 = "#bf616a"  # Red (Deck/Close)
NORD12 = "#d08770"  # Peach (Prev)
NORD13 = "#ebcb8b"  # Gold (Deck/Action)
NORD14 = "#a3be8c"  # Green
NORD15 = "#b48ead"  # Lavender (Next)

APP_DIR = Path(__file__).resolve().parent

# OpenGL proc address callback for libmpv
@mpv.MpvGlGetProcAddressFn
def _c_get_proc_address(ctx, name):
    glctx = QOpenGLContext.currentContext()
    if not glctx:
        return 0
    qba = QtCore.QByteArray(name)
    ptr = glctx.getProcAddress(qba)
    return int(ptr) if ptr else 0


class MpvGLWidget(QOpenGLWidget):
    """Native Qt OpenGL Widget rendering libmpv directly into Qt Framebuffer (Zero-Copy)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mpv_player = mpv.MPV(
            vo='libmpv',
            hwdec='auto',
            idle='yes',
            keep_open='yes'
        )
        self.render_ctx = None

        # Subtle station watermark in bottom-right corner of video
        self.watermark = QtWidgets.QLabel(self)
        self.watermark.setStyleSheet("background: transparent;")
        logo_path = APP_DIR / "assets/sn_logo_overlay.png"
        if not logo_path.exists():
            logo_path = APP_DIR / "sn_logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(
                68, 42,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.watermark.setPixmap(pix)
            self.watermark.setFixedSize(pix.size())
        else:
            self.watermark.setText("SN")
            self.watermark.setStyleSheet("color: rgba(236, 239, 244, 0.65); font-weight: bold; font-size: 14px;")

    def initializeGL(self):
        self.render_ctx = mpv.MpvRenderContext(
            self.mpv_player,
            api_type='opengl',
            opengl_init_params={'get_proc_address': _c_get_proc_address}
        )
        self.render_ctx.update_cb = lambda: self.update()

    def paintGL(self):
        if self.render_ctx:
            fbo = self.defaultFramebufferObject()
            dpr = self.devicePixelRatio()
            w = int(self.width() * dpr)
            h = int(self.height() * dpr)
            self.render_ctx.render(opengl_fbo={'fbo': fbo, 'w': w, 'h': h}, flip_y=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position watermark 18px from right and bottom
        wm_w = self.watermark.width()
        wm_h = self.watermark.height()
        self.watermark.move(self.width() - wm_w - 18, self.height() - wm_h - 18)
        self.watermark.raise_()

    def closeEvent(self, event):
        if self.render_ctx:
            try:
                self.render_ctx.free()
            except Exception:
                pass
            self.render_ctx = None
        if self.mpv_player:
            try:
                self.mpv_player.terminate()
            except Exception:
                pass
        super().closeEvent(event)


class IPCBridge(QObject):
    sig_command = pyqtSignal(dict)
    sig_eof = pyqtSignal()
    sig_meta_loaded = pyqtSignal(str, str)  # artist, extract


class UnifiedTVWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SNfetchPLAYER — Urban & R&B Media Network")
        self.resize(1024, 768)
        self.setMinimumSize(820, 600)
        self.setStyleSheet(f"background-color: {NORD0}; color: {NORD6};")

        self.bridge = IPCBridge()
        self.bridge.sig_command.connect(self.handle_command)
        self.bridge.sig_eof.connect(self.on_track_eof)
        self.bridge.sig_meta_loaded.connect(self.on_meta_loaded)

        self.current_title = "Alright"
        self.current_artist = "Kendrick Lamar"
        self.is_playing = False
        self.is_standalone = False
        self.standalone_playlist = []
        self.standalone_idx = 0
        self.meta_cache = {}

        self.init_ui()

        # Listen for EOF property in MPV
        @self.video_widget.mpv_player.property_observer('eof-reached')
        def _on_eof_observer(name, value):
            if value:
                self.bridge.sig_eof.emit()

        # Start stdin listener
        self.ipc_thread = threading.Thread(target=self._stdin_worker, daemon=True)
        self.ipc_thread.start()

        self._send_event({"event": "ready"})

        # Load standalone playlist as fallback
        self._load_standalone_playlist()

    def _load_standalone_playlist(self):
        pl_candidates = [
            APP_DIR / "playlists/us_hiphop_top50.json",
            APP_DIR / "playlists/main_top100.json",
            APP_DIR / "playlists/us_rnb_top50.json",
        ]
        for p in pl_candidates:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list) and data:
                            self.standalone_playlist = data
                            break
                except Exception:
                    pass

    def init_ui(self):
        # Central Main Widget
        self.central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(14, 12, 14, 12)
        self.main_layout.setSpacing(10)

        # 1. Top Header Bar
        self.header_frame = QtWidgets.QFrame(self.central_widget)
        self.header_frame.setFixedHeight(48)
        header_layout = QtWidgets.QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(12)

        # Left: Station Logo + Title + Subtitle
        logo_box = QtWidgets.QHBoxLayout()
        logo_box.setSpacing(10)

        self.lbl_sn_badge = QtWidgets.QLabel(self.header_frame)
        badge_path = APP_DIR / "sn_logo.png"
        if badge_path.exists():
            pix = QPixmap(str(badge_path)).scaled(
                36, 36,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_sn_badge.setPixmap(pix)
        else:
            self.lbl_sn_badge.setText("SN")
            self.lbl_sn_badge.setStyleSheet(
                f"background-color: {NORD2}; color: {NORD6}; "
                f"font-weight: bold; border-radius: 6px; padding: 4px;"
            )
        logo_box.addWidget(self.lbl_sn_badge)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(2)
        sn_title = QtWidgets.QLabel("STATION NORTH", self.header_frame)
        sn_title.setStyleSheet(f"color: {NORD6}; font-size: 16px; font-weight: bold; letter-spacing: 1px;")
        sn_sub = QtWidgets.QLabel("Urban R&B Network", self.header_frame)
        sn_sub.setStyleSheet(f"color: {NORD8}; font-size: 11px; font-weight: bold;")
        title_box.addWidget(sn_title)
        title_box.addWidget(sn_sub)
        logo_box.addLayout(title_box)

        header_layout.addLayout(logo_box, stretch=1)

        # Right: Mode Pill Buttons
        btn_tv = QtWidgets.QPushButton("📺 TV", self.header_frame)
        btn_tv.setStyleSheet(f"""
            QPushButton {{
                background-color: {NORD8};
                color: {NORD0};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 16px;
                border: none;
                border-radius: 8px;
            }}
        """)
        header_layout.addWidget(btn_tv)

        btn_radio = QtWidgets.QPushButton("📻 RADIO", self.header_frame)
        btn_radio.setStyleSheet(f"""
            QPushButton {{
                background-color: {NORD1};
                color: {NORD6};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 16px;
                border: 1px solid {NORD2};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {NORD2};
                color: #ffffff;
            }}
        """)
        btn_radio.clicked.connect(lambda: self._send_event({"event": "switch_mode", "mode": "radio"}))
        header_layout.addWidget(btn_radio)

        btn_settings = QtWidgets.QPushButton("⚙ SETTINGS", self.header_frame)
        btn_settings.setStyleSheet(f"""
            QPushButton {{
                background-color: {NORD1};
                color: {NORD6};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 16px;
                border: 1px solid {NORD2};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {NORD2};
                color: #ffffff;
            }}
        """)
        btn_settings.clicked.connect(lambda: self._send_event({"event": "switch_mode", "mode": "settings"}))
        header_layout.addWidget(btn_settings)

        self.main_layout.addWidget(self.header_frame)

        # 2. Body Area (Split: Left Video+Controls, Right Metadata)
        self.body_layout = QtWidgets.QHBoxLayout()
        self.body_layout.setSpacing(14)
        self.main_layout.addLayout(self.body_layout, stretch=1)

        # Left Column (Video + Control Card)
        self.left_column = QtWidgets.QWidget(self.central_widget)
        left_layout = QtWidgets.QVBoxLayout(self.left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Video Widget (QOpenGLWidget with direct libmpv injection)
        self.video_widget = MpvGLWidget(self.left_column)
        self.video_widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self.video_widget, stretch=1)

        # Bottom Control Card (5 Chunky Pastel Cockpit Buttons)
        self.ctrl_card = QtWidgets.QFrame(self.left_column)
        self.ctrl_card.setFixedHeight(126)
        self.ctrl_card.setStyleSheet(f"""
            QFrame {{
                background-color: {NORD1};
                border: 1px solid {NORD2};
                border-radius: 14px;
            }}
        """)
        ctrl_layout = QtWidgets.QVBoxLayout(self.ctrl_card)
        ctrl_layout.setContentsMargins(16, 8, 16, 10)
        ctrl_layout.setSpacing(6)

        # Centered Title & Artist
        self.lbl_title = QtWidgets.QLabel(self.current_title, self.ctrl_card)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet(f"color: {NORD6}; font-size: 22px; font-weight: bold; border: none;")
        ctrl_layout.addWidget(self.lbl_title)

        self.lbl_artist = QtWidgets.QLabel(self.current_artist, self.ctrl_card)
        self.lbl_artist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_artist.setStyleSheet(f"color: {NORD8}; font-size: 14px; font-weight: bold; border: none;")
        ctrl_layout.addWidget(self.lbl_artist)

        # 5 Pastel Buttons Row
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)

        def make_cockpit_btn(label, bg_color):
            b = QtWidgets.QPushButton(label, self.ctrl_card)
            b.setFixedHeight(46)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: {NORD0};
                    font-size: 17px;
                    font-weight: bold;
                    border: none;
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    opacity: 0.9;
                }}
            """)
            return b

        self.btn_fs = make_cockpit_btn("[ ]", NORD7)
        self.btn_fs.setToolTip("Toggle Fullscreen Video")
        self.btn_fs.clicked.connect(self.toggle_fullscreen)
        btn_row.addWidget(self.btn_fs)

        self.btn_prev = make_cockpit_btn("|◄", NORD12)
        self.btn_prev.setToolTip("Previous Track")
        self.btn_prev.clicked.connect(self.on_prev_clicked)
        btn_row.addWidget(self.btn_prev)

        self.btn_play = make_cockpit_btn("||", NORD9)
        self.btn_play.setToolTip("Pause / Resume Video")
        self.btn_play.clicked.connect(self.toggle_pause)
        btn_row.addWidget(self.btn_play)

        self.btn_next = make_cockpit_btn("►|", NORD15)
        self.btn_next.setToolTip("Next Track")
        self.btn_next.clicked.connect(self.on_next_clicked)
        btn_row.addWidget(self.btn_next)

        self.btn_deck = make_cockpit_btn("✕", NORD13)
        self.btn_deck.setToolTip("Return to Main Menu / Deck")
        self.btn_deck.clicked.connect(self.on_deck_return)
        btn_row.addWidget(self.btn_deck)

        ctrl_layout.addLayout(btn_row)
        left_layout.addWidget(self.ctrl_card)

        self.body_layout.addWidget(self.left_column, stretch=3)

        # Right Column (Metadata Panel matching media_1793050423329.png)
        self.right_column = QtWidgets.QFrame(self.central_widget)
        self.right_column.setFixedWidth(260)
        self.right_column.setStyleSheet(f"""
            QFrame {{
                background-color: {NORD1};
                border: 1px solid {NORD2};
                border-radius: 14px;
            }}
        """)
        right_layout = QtWidgets.QVBoxLayout(self.right_column)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)

        self.lbl_meta_artist = QtWidgets.QLabel(self.current_artist, self.right_column)
        self.lbl_meta_artist.setStyleSheet(f"color: {NORD6}; font-size: 18px; font-weight: bold; border: none;")
        right_layout.addWidget(self.lbl_meta_artist)

        meta_tag_row = QtWidgets.QHBoxLayout()
        meta_tag_row.setSpacing(6)
        lbl_meta_badge = QtWidgets.QLabel("SN", self.right_column)
        lbl_meta_badge.setStyleSheet(
            f"background-color: {NORD2}; color: {NORD6}; font-size: 10px; font-weight: bold; "
            f"padding: 2px 4px; border-radius: 4px; border: none;"
        )
        meta_tag_row.addWidget(lbl_meta_badge)
        meta_tag = QtWidgets.QLabel("Wikipedia Live Metadata", self.right_column)
        meta_tag.setStyleSheet(f"color: {NORD8}; font-size: 11px; font-weight: bold; border: none;")
        meta_tag_row.addWidget(meta_tag, stretch=1)
        right_layout.addLayout(meta_tag_row)

        self.txt_meta_desc = QtWidgets.QTextEdit(self.right_column)
        self.txt_meta_desc.setReadOnly(True)
        self.txt_meta_desc.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                color: {NORD4};
                font-size: 12px;
                line-height: 1.45;
            }}
        """)
        self.txt_meta_desc.setText(self._get_default_metadata())
        right_layout.addWidget(self.txt_meta_desc, stretch=1)

        self.body_layout.addWidget(self.right_column, stretch=1)

        # 3. Floating OSD for Fullscreen Mode
        self.init_fullscreen_osd()

    def _get_default_metadata(self):
        return (
            "Station North Urban & R&B Media Network.\n\n"
            "High-Definition Television Broadcast suite powered by PyQt6 and libmpv hardware OpenGL engine.\n\n"
            "Hardware Direct Pipeline: On dArkOS / RK3326 consoles, rendering streams direct-to-framebuffer (KMS/DRM).\n\n"
            "On PC, zero-copy OpenGL framebuffer injection delivers smooth 60 FPS playback with uninterrupted track bumpers."
        )

    def init_fullscreen_osd(self):
        self.osd_bar = QtWidgets.QFrame(self.video_widget)
        self.osd_bar.setObjectName("FloatingOSD")
        self.osd_bar.setStyleSheet(f"""
            QFrame#FloatingOSD {{
                background-color: rgba(15, 20, 30, 0.90);
                border: 1px solid rgba(76, 86, 106, 0.85);
                border-radius: 20px;
            }}
            QPushButton {{
                background-color: rgba(46, 52, 64, 0.85);
                color: {NORD6};
                border: 1px solid rgba(67, 76, 94, 0.7);
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {NORD3};
                color: #ffffff;
            }}
        """)
        osd_layout = QtWidgets.QHBoxLayout(self.osd_bar)
        osd_layout.setContentsMargins(18, 6, 18, 6)
        osd_layout.setSpacing(12)

        self.fs_lbl = QtWidgets.QLabel(f"{self.current_title} • {self.current_artist}", self.osd_bar)
        self.fs_lbl.setStyleSheet(f"color: {NORD6}; font-size: 14px; font-weight: bold; border: none;")
        osd_layout.addWidget(self.fs_lbl, stretch=1)

        b_fs = QtWidgets.QPushButton(">< Normal", self.osd_bar)
        b_fs.clicked.connect(self.toggle_fullscreen)
        osd_layout.addWidget(b_fs)

        b_prev = QtWidgets.QPushButton("|◄", self.osd_bar)
        b_prev.clicked.connect(self.on_prev_clicked)
        osd_layout.addWidget(b_prev)

        self.fs_b_play = QtWidgets.QPushButton("||", self.osd_bar)
        self.fs_b_play.clicked.connect(self.toggle_pause)
        osd_layout.addWidget(self.fs_b_play)

        b_next = QtWidgets.QPushButton("►|", self.osd_bar)
        b_next.clicked.connect(self.on_next_clicked)
        osd_layout.addWidget(b_next)

        b_close = QtWidgets.QPushButton("✕ Deck", self.osd_bar)
        b_close.setStyleSheet(f"color: {NORD11}; font-weight: bold;")
        b_close.clicked.connect(self.on_deck_return)
        osd_layout.addWidget(b_close)

        self.osd_bar.hide()

        self.osd_timer = QTimer(self)
        self.osd_timer.setInterval(3500)
        self.osd_timer.timeout.connect(self.osd_bar.hide)

        self.setMouseTracking(True)
        self.video_widget.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isFullScreen():
            w = self.video_widget.width()
            h = self.video_widget.height()
            osd_w = min(720, w - 60)
            osd_h = 56
            self.osd_bar.setGeometry((w - osd_w) // 2, h - osd_h - 32, osd_w, osd_h)
            self.osd_bar.raise_()

    def mouseMoveEvent(self, event):
        if self.isFullScreen():
            self.osd_bar.show()
            self.osd_bar.raise_()
            self.osd_timer.start(3500)
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if self.isFullScreen():
            self.osd_bar.show()
            self.osd_bar.raise_()
            self.osd_timer.start(3500)

        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_B):
            if self.isFullScreen():
                self.toggle_fullscreen()
            else:
                self.on_deck_return()
        elif event.key() in (Qt.Key.Key_F, Qt.Key.Key_0):
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Space:
            self.toggle_pause()
        elif event.key() == Qt.Key.Key_Right:
            self.on_next_clicked()
        elif event.key() == Qt.Key.Key_Left:
            self.on_prev_clicked()
        super().keyPressEvent(event)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.header_frame.show()
            self.ctrl_card.show()
            self.right_column.show()
            self.main_layout.setContentsMargins(14, 12, 14, 12)
            self.osd_bar.hide()
            self.btn_fs.setText("[ ]")
        else:
            self.header_frame.hide()
            self.ctrl_card.hide()
            self.right_column.hide()
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.showFullScreen()
            self.btn_fs.setText("><")
            self.osd_bar.show()
            self.osd_bar.raise_()
            self.osd_timer.start(3500)

    def toggle_pause(self):
        if not self.is_playing:
            return
        paused = self.video_widget.mpv_player.pause
        self.video_widget.mpv_player.pause = not paused
        txt = "▶" if not paused else "||"
        self.btn_play.setText(txt)
        self.fs_b_play.setText(txt)
        self._send_event({"event": "paused" if not paused else "resumed"})

    def on_deck_return(self):
        if self.isFullScreen():
            self.toggle_fullscreen()
        self._send_event({"event": "return_to_deck"})
        self.hide()

    def on_next_clicked(self):
        if self.is_standalone and self.standalone_playlist:
            self.standalone_idx = (self.standalone_idx + 1) % len(self.standalone_playlist)
            self._play_standalone_idx(self.standalone_idx)
        else:
            self._send_event({"event": "request_next"})

    def on_prev_clicked(self):
        if self.is_standalone and self.standalone_playlist:
            self.standalone_idx = (self.standalone_idx - 1) % len(self.standalone_playlist)
            self._play_standalone_idx(self.standalone_idx)
        else:
            self._send_event({"event": "request_prev"})

    def _play_standalone_idx(self, idx: int):
        if 0 <= idx < len(self.standalone_playlist):
            item = self.standalone_playlist[idx]
            title = item.get("title", "")
            artist = item.get("artist", "")
            yt_id = item.get("youtubeId", "")
            if yt_id:
                # Play directly via mpv ytdl hook or local
                url = f"https://www.youtube.com/watch?v={yt_id}"
                self.play_url(url, title, artist)

    def play_url(self, url: str, title: str = "", artist: str = ""):
        self.current_title = title or "Broadcast Stream"
        self.current_artist = artist or "Station North"
        self.lbl_title.setText(self.current_title)
        self.lbl_artist.setText(self.current_artist)
        self.lbl_meta_artist.setText(self.current_artist)
        self.fs_lbl.setText(f"{self.current_title} • {self.current_artist}")
        self.btn_play.setText("||")
        self.fs_b_play.setText("||")

        self.fetch_wikipedia_metadata(self.current_artist)

        self.video_widget.mpv_player.play(url)
        self.video_widget.mpv_player.pause = False
        self.is_playing = True
        self.show()
        self.raise_()
        self.activateWindow()
        self._send_event({"event": "playback_started", "title": self.current_title})

    def fetch_wikipedia_metadata(self, artist: str):
        if not artist or artist in ("Station North", "Station North TV"):
            self.txt_meta_desc.setText(self._get_default_metadata())
            return

        clean = re.split(r'\s+(?:ft\.?|feat\.?|vs\.?|&|,)\s+', artist, flags=re.IGNORECASE)[0].strip()
        if clean in self.meta_cache:
            self.txt_meta_desc.setText(self.meta_cache[clean])
            return

        def _fetch():
            summary = ""
            try:
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(clean)}"
                req = urllib.request.Request(url, headers={"User-Agent": "StationNorthPlayer/1.0"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = json.loads(resp.read().decode())
                    summary = data.get("extract", "")
            except Exception:
                pass
            if not summary:
                summary = self._get_default_metadata()
            self.meta_cache[clean] = summary
            self.bridge.sig_meta_loaded.emit(clean, summary)

        threading.Thread(target=_fetch, daemon=True).start()

    def on_meta_loaded(self, artist: str, extract: str):
        clean_cur = re.split(r'\s+(?:ft\.?|feat\.?|vs\.?|&|,)\s+', self.current_artist, flags=re.IGNORECASE)[0].strip()
        if artist == clean_cur:
            self.txt_meta_desc.setText(extract)

    def on_track_eof(self):
        if self.is_standalone and self.standalone_playlist:
            self.on_next_clicked()
        else:
            self._send_event({"event": "eof"})

    def _send_event(self, data: dict):
        try:
            sys.stdout.write(json.dumps(data) + "\n")
            sys.stdout.flush()
        except Exception:
            pass

    def handle_command(self, cmd: dict):
        action = cmd.get("action")
        if action == "play":
            url = cmd.get("url")
            title = cmd.get("title", "")
            artist = cmd.get("artist", "")
            if url:
                self.play_url(url, title, artist)
        elif action == "pause":
            self.video_widget.mpv_player.pause = True
            self.btn_play.setText("▶")
            self.fs_b_play.setText("▶")
        elif action == "resume":
            self.video_widget.mpv_player.pause = False
            self.btn_play.setText("||")
            self.fs_b_play.setText("||")
        elif action == "toggle_pause":
            self.toggle_pause()
        elif action == "toggle_fullscreen":
            self.toggle_fullscreen()
        elif action == "stop":
            self.video_widget.mpv_player.stop()
            self.is_playing = False
        elif action == "show":
            self.show()
            self.raise_()
            self.activateWindow()
        elif action == "hide":
            self.hide()
        elif action == "quit":
            self.video_widget.mpv_player.terminate()
            QtWidgets.QApplication.quit()

    def _stdin_worker(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
                self.bridge.sig_command.emit(cmd)
            except Exception:
                pass


def main():
    app = QtWidgets.QApplication(sys.argv)
    try:
        locale.setlocale(locale.LC_NUMERIC, "C")
    except Exception:
        pass

    win = UnifiedTVWindow()
    # Check if run with a URL argument or standalone
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        title = sys.argv[2] if len(sys.argv) > 2 else "Broadcast Stream"
        artist = sys.argv[3] if len(sys.argv) > 3 else "Station North"
        win.play_url(target_url, title, artist)
    else:
        # Check if stdin is a tty (standalone user run)
        if sys.stdin.isatty():
            win.is_standalone = True
            # Play first video or bumper
            sample_bumper = APP_DIR / "assets/tv_ids/SN_tv_000001.mp4"
            if sample_bumper.exists():
                win.play_url(str(sample_bumper), "Station North ID #1", "Station North TV")
            elif win.standalone_playlist:
                win._play_standalone_idx(0)

    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
