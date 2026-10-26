#!/usr/bin/env python3
"""
Station North SNfetchPLAYER - High-Performance TV Companion (PC Edition)
Powered by PyQt6 & libmpv with hardware GPU acceleration.
- Persistent OpenGL window (idle='yes') - zero flicker, no window closing between tracks
- Floating Nord Glass OSD with auto-hide timer (3.5s)
- In-place fullscreen toggle
- Bidirectional JSON-IPC over stdin / stdout
"""

import sys
import os
import json
import time
import locale
import threading
from pathlib import Path

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject

# Ensure C locale for libmpv timestamps
os.environ.setdefault("LC_NUMERIC", "C")
try:
    locale.setlocale(locale.LC_NUMERIC, "C")
except Exception:
    pass

import mpv

NORD0 = "#2e3440"
NORD1 = "#3b4252"
NORD2 = "#434c5e"
NORD3 = "#4c566a"
NORD4 = "#d8dee9"
NORD6 = "#eceff4"
NORD7 = "#8fbcbb"
NORD8 = "#88c0d0"
NORD9 = "#81a1c1"
NORD11 = "#bf616a"
NORD14 = "#a3be8c"

class IPCBridge(QObject):
    sig_command = pyqtSignal(dict)
    sig_eof = pyqtSignal()

class VideoPlayerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Station North • Television Broadcast (PC Suite)")
        self.resize(1024, 768)
        self.setMinimumSize(640, 480)
        self.setStyleSheet("background-color: #000000;")

        self.bridge = IPCBridge()
        self.bridge.sig_command.connect(self.handle_command)
        self.bridge.sig_eof.connect(self.on_track_eof)

        # Central video container
        self.video_widget = QtWidgets.QWidget(self)
        self.video_widget.setStyleSheet("background-color: #000000;")
        self.setCentralWidget(self.video_widget)

        # Ensure container winId exists
        self.video_widget.winId()

        # Initialize libmpv
        self.player = mpv.MPV(
            wid=str(int(self.video_widget.winId())),
            vo='gpu,x11,wlshm',
            hwdec='auto',
            idle='yes',
            keep_open='yes',
            input_default_bindings=True,
            input_vo_keyboard=True
        )

        # Listen for EOF property in MPV
        @self.player.property_observer('eof-reached')
        def _on_eof_observer(name, value):
            if value:
                self.bridge.sig_eof.emit()

        # Setup Floating Glass OSD
        self.init_osd()

        # Track metadata
        self.current_title = "Station North TV"
        self.current_artist = "Television Broadcast"
        self.is_playing = False

        # Set mouse tracking for auto-show OSD
        self.setMouseTracking(True)
        self.video_widget.setMouseTracking(True)

        # Start stdin listener thread
        self.ipc_thread = threading.Thread(target=self._stdin_worker, daemon=True)
        self.ipc_thread.start()

        # Notify parent that companion is ready
        self._send_event({"event": "ready"})

    def init_osd(self):
        self.osd = QtWidgets.QFrame(self.video_widget)
        self.osd.setObjectName("OSDFrame")
        self.osd.setStyleSheet(f"""
            QFrame#OSDFrame {{
                background-color: rgba(36, 41, 51, 0.92);
                border: 1px solid rgba(76, 86, 106, 0.85);
                border-radius: 16px;
            }}
            QPushButton {{
                background-color: rgba(46, 52, 64, 0.9);
                color: {NORD6};
                border: 1px solid rgba(67, 76, 94, 0.8);
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {NORD3};
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: {NORD8};
                color: {NORD0};
            }}
        """)
        osd_layout = QtWidgets.QHBoxLayout(self.osd)
        osd_layout.setContentsMargins(18, 10, 18, 10)
        osd_layout.setSpacing(12)

        # Title & Artist info
        info_layout = QtWidgets.QVBoxLayout()
        self.lbl_title = QtWidgets.QLabel("Station North TV", self.osd)
        self.lbl_title.setStyleSheet(f"color: {NORD6}; font-size: 15px; font-weight: bold;")
        self.lbl_artist = QtWidgets.QLabel("Broadcast Satellite Feed", self.osd)
        self.lbl_artist.setStyleSheet(f"color: {NORD8}; font-size: 12px; font-weight: bold;")
        info_layout.addWidget(self.lbl_title)
        info_layout.addWidget(self.lbl_artist)
        osd_layout.addLayout(info_layout, stretch=1)

        # Control Buttons
        self.btn_fs = QtWidgets.QPushButton("[ ] Zoom", self.osd)
        self.btn_fs.clicked.connect(self.toggle_fullscreen)
        osd_layout.addWidget(self.btn_fs)

        self.btn_prev = QtWidgets.QPushButton("|◄ Prev", self.osd)
        self.btn_prev.clicked.connect(lambda: self._send_event({"event": "request_prev"}))
        osd_layout.addWidget(self.btn_prev)

        self.btn_play = QtWidgets.QPushButton("|| Pause", self.osd)
        self.btn_play.clicked.connect(self.toggle_pause)
        osd_layout.addWidget(self.btn_play)

        self.btn_next = QtWidgets.QPushButton("Next ►|", self.osd)
        self.btn_next.clicked.connect(lambda: self._send_event({"event": "request_next"}))
        osd_layout.addWidget(self.btn_next)

        self.btn_close = QtWidgets.QPushButton("✕ Deck", self.osd)
        self.btn_close.setStyleSheet(f"color: {NORD11}; font-weight: bold;")
        self.btn_close.clicked.connect(self.on_deck_return)
        osd_layout.addWidget(self.btn_close)

        # OSD Auto-Hide Timer
        self.osd_timer = QTimer(self)
        self.osd_timer.setInterval(3500)
        self.osd_timer.timeout.connect(self.hide_osd)
        self.osd_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_osd()

    def reposition_osd(self):
        w = min(880, self.width() - 40)
        h = 68
        x = (self.width() - w) // 2
        y = self.height() - h - 28
        self.osd.setGeometry(x, y, w, h)

    def mouseMoveEvent(self, event):
        self.wake_osd()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        self.wake_osd()
        if event.key() == Qt.Key.Key_Escape or event.key() == Qt.Key.Key_B:
            self.on_deck_return()
        elif event.key() in (Qt.Key.Key_F, Qt.Key.Key_0):
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Space:
            self.toggle_pause()
        elif event.key() == Qt.Key.Key_Right:
            self._send_event({"event": "request_next"})
        elif event.key() == Qt.Key.Key_Left:
            self._send_event({"event": "request_prev"})
        super().keyPressEvent(event)

    def wake_osd(self):
        self.reposition_osd()
        self.osd.show()
        self.osd_timer.start(3500)

    def hide_osd(self):
        self.osd.hide()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.btn_fs.setText("[ ] Zoom")
        else:
            self.showFullScreen()
            self.btn_fs.setText(">< Normal")
        self.wake_osd()

    def toggle_pause(self):
        if not self.is_playing:
            return
        paused = self.player.pause
        self.player.pause = not paused
        self.btn_play.setText("▶ Play" if not paused else "|| Pause")
        self._send_event({"event": "paused" if not paused else "resumed"})
        self.wake_osd()

    def on_deck_return(self):
        self._send_event({"event": "return_to_deck"})
        self.hide()

    def play_url(self, url: str, title: str = "", artist: str = ""):
        self.current_title = title or "Broadcast Feed"
        self.current_artist = artist or "Station North"
        self.lbl_title.setText(self.current_title)
        self.lbl_artist.setText(self.current_artist)
        self.btn_play.setText("|| Pause")

        # Play video seamlessly inside existing OpenGL window
        self.player.play(url)
        self.player.pause = False
        self.is_playing = True
        self.show()
        self.raise_()
        self.activateWindow()
        self.wake_osd()
        self._send_event({"event": "playback_started", "title": self.current_title})

    def on_track_eof(self):
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
            self.player.pause = True
            self.btn_play.setText("▶ Play")
            self.wake_osd()
        elif action == "resume":
            self.player.pause = False
            self.btn_play.setText("|| Pause")
            self.wake_osd()
        elif action == "toggle_pause":
            self.toggle_pause()
        elif action == "toggle_fullscreen":
            self.toggle_fullscreen()
        elif action == "stop":
            self.player.stop()
            self.is_playing = False
        elif action == "show":
            self.show()
            self.raise_()
        elif action == "hide":
            self.hide()
        elif action == "quit":
            self.player.terminate()
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

    win = VideoPlayerWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
