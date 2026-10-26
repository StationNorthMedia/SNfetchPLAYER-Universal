#!/usr/bin/env python3
"""
Station North SNfetchPLAYER - Minimalist TV Video Companion (PC Edition)
Option A Architecture:
- Fixed 1024x768 (4:3) Windowed Mode with pan-and-scan (zero black bars, full bleed)
- Seamless 16:9 Widescreen Fullscreen Toggle ([ ] / ><) with uncropped video
- Proportional vector-smooth Logo watermark scaling across all resolutions
- Classic MTV-Style Lower Third (Bauchbinde) appearing for 6s on track start
- Sleek 5-Button Pastel Cockpit (Pure Pygame Style) with 3.5s auto-hide and hover-pause
- Bidirectional JSON-IPC over stdin / stdout with standalone fallback
"""

import sys
import os
import json
import time
import locale
import threading
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
NORD6 = "#eceff4"
NORD7 = "#8fbcbb"   # Mint ([ ] Fullscreen)
NORD8 = "#88c0d0"   # Frost Cyan (Accent / Title)
NORD9 = "#81a1c1"   # Arctic Blue (Play / Pause)
NORD11 = "#bf616a"  # Red
NORD12 = "#d08770"  # Peach (|◄ Prev)
NORD13 = "#ebcb8b"  # Gold (✕ Close / Deck)
NORD15 = "#b48ead"  # Lavender (►| Next)

APP_DIR = Path(__file__).resolve().parent
FIXED_WINDOW_W = 1024
FIXED_WINDOW_H = 768


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
    """Native Qt OpenGL Widget rendering libmpv directly into Qt Framebuffer."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mpv_player = mpv.MPV(
            vo='libmpv',
            hwdec='auto',
            idle='yes',
            keep_open='yes'
        )
        self.render_ctx = None

        # Master Logo for proportional scaling
        self.master_logo: QPixmap = QPixmap()
        logo_path = APP_DIR / "assets/sn_logo_overlay.png"
        if not logo_path.exists():
            logo_path = APP_DIR / "sn_logo.png"
        if logo_path.exists():
            self.master_logo = QPixmap(str(logo_path))

        # Station watermark label in bottom-right corner of video
        self.watermark = QtWidgets.QLabel(self)
        self.watermark.setStyleSheet("background: transparent;")
        if self.master_logo.isNull():
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
        self.reposition_watermark()

    def reposition_watermark(self):
        vw = self.width()
        vh = self.height()
        if not self.master_logo.isNull():
            # Dynamically scale logo proportional to window height (~6.5% of height)
            logo_h = max(34, int(vh * 0.065))
            logo_w = int(logo_h * (self.master_logo.width() / self.master_logo.height()))
            scaled = self.master_logo.scaled(
                logo_w, logo_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.watermark.setPixmap(scaled)
            self.watermark.setFixedSize(scaled.size())
            margin_x = max(16, int(vw * 0.025))
            margin_y = max(16, int(vh * 0.035))
            self.watermark.move(vw - scaled.width() - margin_x, vh - scaled.height() - margin_y)
        else:
            self.watermark.move(vw - 50, vh - 40)
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


class HoverAwareCockpit(QtWidgets.QFrame):
    """Cockpit frame that pauses auto-hide when the mouse hovers over it."""
    def __init__(self, parent=None, on_enter=None, on_leave=None):
        super().__init__(parent)
        self._on_enter = on_enter
        self._on_leave = on_leave

    def enterEvent(self, event):
        if self._on_enter:
            self._on_enter()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._on_leave:
            self._on_leave()
        super().leaveEvent(event)


class IPCBridge(QObject):
    sig_command = pyqtSignal(dict)
    sig_eof = pyqtSignal()


class MinimalistTVWindow(QtWidgets.QMainWindow):
    """
    Station North Minimalist TV Window:
    - Fixed 1024x768 4:3 windowed mode with pan & scan (zero black bars).
    - Uncropped 16:9 fullscreen with proportional watermark.
    - MTV-style Lower Third (Bauchbinde) on track start (6s auto-fade).
    - Pure 5-Button Pastel Cockpit with 3.5s auto-hide.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Station North • Television Broadcast")
        self.setStyleSheet(f"background-color: {NORD0}; color: {NORD6};")

        self.bridge = IPCBridge()
        self.bridge.sig_command.connect(self.handle_command)
        self.bridge.sig_eof.connect(self.on_track_eof)

        self.current_title = "Alright"
        self.current_artist = "Kendrick Lamar"
        self.is_playing = False
        self.is_standalone = False
        self.standalone_playlist = []
        self.standalone_idx = 0

        self.init_ui()

        # Lock to fixed 1024x768 in windowed mode
        self.apply_windowed_fixed_size()

        # Listen for EOF property in MPV
        @self.video_widget.mpv_player.property_observer('eof-reached')
        def _on_eof_observer(name, value):
            if value:
                self.bridge.sig_eof.emit()

        # Start stdin listener
        self.ipc_thread = threading.Thread(target=self._stdin_worker, daemon=True)
        self.ipc_thread.start()

        self._send_event({"event": "ready"})
        self._load_standalone_playlist()

    def apply_windowed_fixed_size(self):
        """Sets fixed 1024x768 size and 4:3 pan & scan cropping in windowed mode."""
        self.setMinimumSize(FIXED_WINDOW_W, FIXED_WINDOW_H)
        self.setMaximumSize(FIXED_WINDOW_W, FIXED_WINDOW_H)
        self.resize(FIXED_WINDOW_W, FIXED_WINDOW_H)
        # Pan & Scan = 1.0 crops left/right to fill 4:3 container with zero black bars
        self.video_widget.mpv_player.panscan = 1.0

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
        # 1. Video Widget is the central widget (100% video display)
        self.video_widget = MpvGLWidget(self)
        self.setCentralWidget(self.video_widget)

        # 2. Classic MTV-Style Lower Third (Bauchbinde) in Bottom-Left Corner
        self.lower_third = QtWidgets.QFrame(self.video_widget)
        self.lower_third.setObjectName("LowerThird")
        self.lower_third.setStyleSheet(f"""
            QFrame#LowerThird {{
                background-color: rgba(20, 26, 38, 0.90);
                border: 1px solid rgba(76, 86, 106, 0.85);
                border-left: 5px solid {NORD8};
                border-radius: 12px;
            }}
        """)
        lt_layout = QtWidgets.QVBoxLayout(self.lower_third)
        lt_layout.setContentsMargins(14, 8, 16, 8)
        lt_layout.setSpacing(3)

        self.lt_artist = QtWidgets.QLabel(self.current_artist, self.lower_third)
        self.lt_artist.setStyleSheet(f"color: {NORD6}; font-size: 15px; font-weight: bold; border: none;")
        lt_layout.addWidget(self.lt_artist)

        self.lt_title = QtWidgets.QLabel(f"{self.current_title} • Television Broadcast", self.lower_third)
        self.lt_title.setStyleSheet(f"color: {NORD8}; font-size: 12px; font-weight: bold; border: none;")
        lt_layout.addWidget(self.lt_title)

        self.lower_third.adjustSize()
        self.lower_third.hide()

        self.lower_third_timer = QTimer(self)
        self.lower_third_timer.setInterval(6000)
        self.lower_third_timer.timeout.connect(self.lower_third.hide)

        # 3. Floating 5-Button Pastel Cockpit (Pure Pygame Style)
        self.cockpit = HoverAwareCockpit(
            self.video_widget,
            on_enter=self._on_cockpit_hover_enter,
            on_leave=self._on_cockpit_hover_leave
        )
        self.cockpit.setObjectName("FloatingCockpit")
        self.cockpit.setStyleSheet(f"""
            QFrame#FloatingCockpit {{
                background-color: rgba(20, 26, 38, 0.92);
                border: 1px solid rgba(76, 86, 106, 0.85);
                border-radius: 18px;
            }}
        """)
        cockpit_layout = QtWidgets.QHBoxLayout(self.cockpit)
        cockpit_layout.setContentsMargins(14, 8, 14, 8)
        cockpit_layout.setSpacing(10)

        def make_cockpit_btn(label, bg_color):
            b = QtWidgets.QPushButton(label, self.cockpit)
            b.setFixedHeight(44)
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

        # 1: Fullscreen [ ] / ><
        self.btn_fs = make_cockpit_btn("[ ]", NORD7)
        self.btn_fs.setToolTip("Toggle Fullscreen (16:9) / Windowed (4:3)")
        self.btn_fs.clicked.connect(self.toggle_fullscreen)
        cockpit_layout.addWidget(self.btn_fs)

        # 2: Prev |◄
        self.btn_prev = make_cockpit_btn("|◄", NORD12)
        self.btn_prev.setToolTip("Previous Track")
        self.btn_prev.clicked.connect(self.on_prev_clicked)
        cockpit_layout.addWidget(self.btn_prev)

        # 3: Play / Pause ||
        self.btn_play = make_cockpit_btn("||", NORD9)
        self.btn_play.setToolTip("Pause / Resume Video")
        self.btn_play.clicked.connect(self.toggle_pause)
        cockpit_layout.addWidget(self.btn_play)

        # 4: Next ►|
        self.btn_next = make_cockpit_btn("►|", NORD15)
        self.btn_next.setToolTip("Next Track")
        self.btn_next.clicked.connect(self.on_next_clicked)
        cockpit_layout.addWidget(self.btn_next)

        # 5: Close / Deck ✕ (Pastel Gold)
        self.btn_close = make_cockpit_btn("✕", NORD13)
        self.btn_close.setToolTip("Close TV / Back to Pygame Deck")
        self.btn_close.clicked.connect(self.on_deck_return)
        cockpit_layout.addWidget(self.btn_close)

        # Mouse tracking & Auto-hide timer
        self.setMouseTracking(True)
        self.video_widget.setMouseTracking(True)

        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(3500)
        self.hide_timer.timeout.connect(self.cockpit.hide)

        # Initial wake
        self.wake_cockpit()

    def _on_cockpit_hover_enter(self):
        self.hide_timer.stop()

    def _on_cockpit_hover_leave(self):
        self.hide_timer.start(3500)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_overlays()

    def reposition_overlays(self):
        vw = self.video_widget.width()
        vh = self.video_widget.height()

        # 1. Reposition Cockpit (Bottom Center)
        w = min(560, vw - 40)
        h = 60
        x = (vw - w) // 2
        y = vh - h - 22
        self.cockpit.setGeometry(x, y, w, h)
        self.cockpit.raise_()

        # 2. Reposition Lower Third (Bottom Left, elevated above cockpit line)
        lt_w = min(420, max(280, int(vw * 0.38)))
        lt_h = 58
        lt_x = max(24, int(vw * 0.03))
        lt_y = vh - h - 22 - lt_h - 14
        self.lower_third.setGeometry(lt_x, lt_y, lt_w, lt_h)
        self.lower_third.raise_()

    def mouseMoveEvent(self, event):
        self.wake_cockpit()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.toggle_fullscreen()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        self.wake_cockpit()

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

    def wake_cockpit(self):
        self.reposition_overlays()
        self.cockpit.show()
        self.cockpit.raise_()
        self.hide_timer.start(3500)

    def show_lower_third(self):
        self.lt_artist.setText(self.current_artist)
        self.lt_title.setText(f"{self.current_title} • Television Broadcast")
        self.reposition_overlays()
        self.lower_third.show()
        self.lower_third.raise_()
        self.lower_third_timer.start(6000)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            # Exit fullscreen back to fixed 1024x768 4:3 pan & scan
            self.showNormal()
            self.apply_windowed_fixed_size()
            self.btn_fs.setText("[ ]")
        else:
            # Enter Fullscreen: Unlock constraints and switch to 16:9 uncropped
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.showFullScreen()
            # In 16:9 Fullscreen, panscan = 0.0 gives full native widescreen without cropping
            self.video_widget.mpv_player.panscan = 0.0
            self.btn_fs.setText("><")

        self.wake_cockpit()

    def toggle_pause(self):
        if not self.is_playing:
            return
        paused = self.video_widget.mpv_player.pause
        self.video_widget.mpv_player.pause = not paused
        txt = "▶" if not paused else "||"
        self.btn_play.setText(txt)
        self._send_event({"event": "paused" if not paused else "resumed"})
        self.wake_cockpit()

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
        self.wake_cockpit()

    def on_prev_clicked(self):
        if self.is_standalone and self.standalone_playlist:
            self.standalone_idx = (self.standalone_idx - 1) % len(self.standalone_playlist)
            self._play_standalone_idx(self.standalone_idx)
        else:
            self._send_event({"event": "request_prev"})
        self.wake_cockpit()

    def _play_standalone_idx(self, idx: int):
        if 0 <= idx < len(self.standalone_playlist):
            item = self.standalone_playlist[idx]
            title = item.get("title", "")
            artist = item.get("artist", "")
            yt_id = item.get("youtubeId", "")
            if yt_id:
                url = f"https://www.youtube.com/watch?v={yt_id}"
                self.play_url(url, title, artist)

    def play_url(self, url: str, title: str = "", artist: str = ""):
        self.current_title = title or "Broadcast Stream"
        self.current_artist = artist or "Station North"
        self.btn_play.setText("||")

        self.video_widget.mpv_player.play(url)
        self.video_widget.mpv_player.pause = False
        self.is_playing = True
        self.show()
        self.raise_()
        self.activateWindow()

        # Wake Cockpit & show broadcast Lower Third for 6 seconds
        self.wake_cockpit()
        self.show_lower_third()

        self._send_event({"event": "playback_started", "title": self.current_title})

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
            self.wake_cockpit()
        elif action == "resume":
            self.video_widget.mpv_player.pause = False
            self.btn_play.setText("||")
            self.wake_cockpit()
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
            self.wake_cockpit()
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

    win = MinimalistTVWindow()
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        title = sys.argv[2] if len(sys.argv) > 2 else "Broadcast Stream"
        artist = sys.argv[3] if len(sys.argv) > 3 else "Station North"
        win.play_url(target_url, title, artist)
    else:
        if sys.stdin.isatty():
            win.is_standalone = True
            sample_bumper = APP_DIR / "assets/tv_ids/SN_tv_000001.mp4"
            if sample_bumper.exists():
                win.play_url(str(sample_bumper), "Station North ID #1", "Station North TV")
            elif win.standalone_playlist:
                win._play_standalone_idx(0)

    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
