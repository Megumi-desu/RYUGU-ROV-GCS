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
import socket
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GCS")

# ── Load .env (Supabase keys, tunables) — before any app code ────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — GCS still runs; broadcaster no-ops

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
from core.telemetry_broadcaster import TelemetryBroadcaster
from core.mjpeg_server import MjpegStreamServer
from utils.constants import (
    STREAM_URL_FRONT, STREAM_URL_BOTTOM,
    GCS_IP, TELEM_PORT,
    POSITION_MODE, MJPEG_PORT,
)


# ── Network verification ─────────────────────────────────────────────────

def _check_network():
    """Warn if the expected GCS static IP is not present on any interface."""
    try:
        # Enumerate all IPs bound to this host
        hostname = socket.gethostname()
        local_ips = {
            addr[4][0]
            for addr in socket.getaddrinfo(hostname, None, socket.AF_INET)
        }
        # Also include loopback / common detection via UDP trick
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # doesn't actually send data
            local_ips.add(s.getsockname()[0])
            s.close()
        except OSError:
            pass

        if GCS_IP in local_ips:
            logger.info(
                "Network OK — GCS IP %s found on this machine.", GCS_IP
            )
        else:
            logger.warning(
                "GCS IP is not %s. Telemetry data might not be received! "
                "Detected IPs: %s. "
                "Please configure a static IP of %s on the Ethernet adapter "
                "connected to the ROV.",
                GCS_IP, ", ".join(sorted(local_ips)), GCS_IP,
            )
    except Exception as e:
        logger.warning("Network check failed: %s", e)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── Startup network check ─────────────────────────────────────────
    _check_network()

    # ── Main window ───────────────────────────────────────────────────
    window = MainWindow()

    # ── Gamepad controller ─────────────────────────────────────────────
    gamepad = GamepadController()

    # ── Ethernet worker ────────────────────────────────────────────────
    eth_worker = EthernetWorker()

    # ── Camera stream workers ──────────────────────────────────────────
    cam_front = CameraStreamWorker(STREAM_URL_FRONT, "FRONT CAM")
    cam_bottom = CameraStreamWorker(STREAM_URL_BOTTOM, "BOTTOM CAM")

    # ── Telemetry broadcaster (Supabase Realtime) ──────────────────────
    broadcaster = TelemetryBroadcaster(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        hz=float(os.getenv("TELEMETRY_BROADCAST_HZ", "5")),
        use_simulated_depth=(POSITION_MODE == "PIXHAWK_HYBRID"),
    )

    # ── MJPEG server (web spectator video) ─────────────────────────────
    mjpeg = MjpegStreamServer(
        urls={"cam1": STREAM_URL_FRONT, "cam2": STREAM_URL_BOTTOM},
        port=int(os.getenv("MJPEG_PORT", str(MJPEG_PORT))),
    )

    # ── Wire gamepad → MainWindow ─────────────────────────────────────
    # Position delta → Trajectory Panel (dead reckoning)
    gamepad.position_delta.connect(window.traj_panel.update_position)

    # Axes → MainWindow handler (yaw → trajectory heading + forward to Jetson)
    gamepad.axes_updated.connect(window.on_axes_updated)

    # Flight mode → status bar + forward to Jetson
    gamepad.mode_changed.connect(window.on_mode_changed)

    # ARM/DISARM → status bar + forward to Jetson
    gamepad.arm_event.connect(window.on_arm_event)

    # Button events (gripper, speed mode) → forward to MainWindow
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

    # ── Tap Ethernet telemetry → broadcaster (read-only, no UDP) ──────
    eth_worker.imu_updated.connect(broadcaster.on_imu)
    eth_worker.depth_updated.connect(broadcaster.on_depth)
    eth_worker.status_updated.connect(broadcaster.on_status)
    eth_worker.connection_changed.connect(broadcaster.on_connection)
    window.simulated_depth_changed.connect(broadcaster.on_simulated_depth)

    # ── Tap trajectory & QR → broadcaster ────────────────────────────
    window.traj_panel.position_changed.connect(broadcaster.on_position)
    window.qr_panel.qr_data_updated.connect(broadcaster.on_qr)
    window.qr_panel.qr_image_updated.connect(broadcaster.on_qr_image)

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
    broadcaster.start()
    mjpeg.start()

    # ── Show window ───────────────────────────────────────────────────
    window.showMaximized()

    # ── Clean shutdown ────────────────────────────────────────────────
    def on_quit():
        cam_front.stop()
        cam_bottom.stop()
        broadcaster.stop()
        mjpeg.stop()
        gamepad.stop()
        eth_worker.stop()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
