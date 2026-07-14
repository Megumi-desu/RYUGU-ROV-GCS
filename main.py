"""
ROV GCS — Main Entry Point
RYUGU ROV Universitas Brawijaya | KKI 2026

Run:
    python main.py

Requirements:
    pip install -r requirements.txt
    (see verify_env.py to check your setup)
"""

import sys
import os
import ctypes

# ── DPI fix — MUST be before QApplication ────────────────────────────────
# Without this, Windows 11 DPI scaling breaks the layout at 125% / 150%.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware v2
except Exception:
    pass  # Non-Windows or already set by manifest

# ── Qt high-DPI attributes — also before QApplication ────────────────────
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# ── Local imports ─────────────────────────────────────────────────────────
# Add project root to path so sub-packages resolve correctly when running
# directly (python main.py) rather than as a module.
sys.path.insert(0, os.path.dirname(__file__))

from gui.main_window import MainWindow
from core.gamepad_controller import GamepadController
from core.ethernet_worker import EthernetWorker
from core.camera_stream_worker import CameraStreamWorker
from utils.constants import (
    STREAM_URL_FRONT, STREAM_URL_BOTTOM,
)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── Main window ───────────────────────────────────────────────────
    window = MainWindow()

    # ── Gamepad controller ─────────────────────────────────────────────
    gamepad = GamepadController()

    # ── Ethernet worker ────────────────────────────────────────────────
    eth_worker = EthernetWorker()

    # ── Camera stream workers ──────────────────────────────────────────
    cam_front = CameraStreamWorker(STREAM_URL_FRONT, "FRONT CAM")
    cam_bottom = CameraStreamWorker(STREAM_URL_BOTTOM, "BOTTOM CAM")

    # ── Wire gamepad → MainWindow ─────────────────────────────────────
    # Position delta → Trajectory Panel (dead reckoning)
    gamepad.position_delta.connect(window.traj_panel.update_position)

    # Axes → MainWindow handler (yaw → trajectory heading + forward to Jetson)
    gamepad.axes_updated.connect(window.on_axes_updated)

    # Flight mode → status bar + forward to Jetson
    gamepad.mode_changed.connect(window.on_mode_changed)

    # ARM/DISARM → status bar + forward to Jetson
    gamepad.arm_event.connect(window.on_arm_event)

    # Button events (gripper, ballast) → forward to Jetson
    gamepad.button_event.connect(window.on_button_event)

    # Connection status → GAMEPAD indicator + status log
    def _on_gamepad_lost():
        window._footer.set_gamepad_status(False, "LOST")
        window.qr_panel.add_log("GAMEPAD: LOST", "#f44336")

    def _on_gamepad_restored():
        window._footer.set_gamepad_status(True, "OK")
        window.qr_panel.add_log("GAMEPAD: OK", "#4caf50")

    gamepad.connection_lost.connect(_on_gamepad_lost)
    gamepad.connection_restored.connect(_on_gamepad_restored)

    # ── Wire Ethernet worker → MainWindow ─────────────────────────────
    window.wire_ethernet(eth_worker)

    # ── Wire camera streams → camera panels ───────────────────────────
    cam_front.frame_ready.connect(window.cam_front.update_frame_qimage)
    cam_front.connection_status.connect(window.cam_front.set_stream_status)

    cam_bottom.frame_ready.connect(window.cam_bottom.update_frame_qimage)
    cam_bottom.connection_status.connect(window.cam_bottom.set_stream_status)

    # ── Start threads ─────────────────────────────────────────────────
    gamepad.start()
    eth_worker.start()
    cam_front.start()
    cam_bottom.start()

    # ── Show window ───────────────────────────────────────────────────
    window.showMaximized()

    # ── Clean shutdown ────────────────────────────────────────────────
    def on_quit():
        cam_front.stop()
        cam_bottom.stop()
        gamepad.stop()
        eth_worker.stop()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
