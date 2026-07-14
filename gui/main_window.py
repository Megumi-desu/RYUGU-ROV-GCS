import os
import time
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QPixmap

from gui.widgets.camera_panel     import CameraPanel
from gui.widgets.qr_panel         import QRResultPanel
from gui.widgets.altitude_panel   import AltitudePanel
from gui.widgets.trajectory_panel import TrajectoryPanel
from gui.widgets.rov_design_panel import ROVDesignPanel
from gui.widgets.status_bar       import FooterStatusBar

from utils.constants import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    WINDOW_MIN_W, WINDOW_MIN_H,
    TEAM_NAME, UNIVERSITY_NAME, COMPETITION,
    COLOR_BG, COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT,
    COLOR_TEXT, COLOR_TEXT_DIM,
    COLOR_OK, COLOR_ERROR, COLOR_WARN,
    FONT_FAMILY,
    ASSET_LOGO_UB, ASSET_LOGO_KKI, ASSET_LOGO_TEAM
)

# Timeout threshold for downlink telemetry packets (seconds)
_TELEM_TIMEOUT_S = 3.0


def _load_qss(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


class MainWindow(QMainWindow):
    """
    Top-level window for the ROV GCS.
    Hosts all panels and wires them to data threads via Qt signals.
    """

    def __init__(self):
        super().__init__()
        self._setup_window()
        self._apply_stylesheet()

        # Track arm state for UI feedback
        self._armed = False
        # Reference to ethernet worker (set via wire_ethernet)
        self._eth_worker = None

        # Track previous connection state for status-log transitions
        self._prev_connected: bool | None = None
        # Track previous flight mode for status-log transitions
        self._prev_mode: str | None = None

        # Timestamps for last received telemetry packets (monotonic)
        self._last_imu_time: float = 0.0
        self._last_depth_time: float = 0.0
        self._last_status_time: float = 0.0

        self._build_ui()
        self._start_clock()

    # ── Window setup ──────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_W, WINDOW_MIN_H)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def _apply_stylesheet(self):
        qss_path = os.path.join(
            os.path.dirname(__file__), "styles", "dark_theme.qss"
        )
        qss = _load_qss(qss_path)
        if qss:
            self.setStyleSheet(qss)

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(4)

        # 1. Top info bar
        root_layout.addWidget(self._build_top_bar())

        # 2. Main content grid (2 rows × 3 columns)
        root_layout.addLayout(self._build_grid(), stretch=1)

        # 3. Footer status bar
        self._footer = FooterStatusBar()
        root_layout.addWidget(self._footer)

        # Initial status
        self._footer.set_mode("MANUAL")
        self._footer.set_connection(False)
        self._footer.set_bar30_status(False, "NO LINK")
        self._footer.set_battery_status(False, "NO LINK")
        self._footer.set_gamepad_status(False, "NO LINK")
        self._footer.set_imu_status(False, "NO LINK")
        self._footer.set_logging(False)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setFixedHeight(52)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        # UB Logo
        self._logo_ub = QLabel()
        self._logo_ub.setFixedSize(44, 44)
        self._logo_ub.setStyleSheet("border: none;")
        self._load_logo(self._logo_ub, ASSET_LOGO_UB, 44)
        layout.addWidget(self._logo_ub)

        layout.addSpacing(6)

        # Ryugu Team Logo
        self._logo_team = QLabel()
        self._logo_team.setFixedSize(44, 44)
        self._logo_team.setStyleSheet("border: none;")
        self._load_logo(self._logo_team, ASSET_LOGO_TEAM, 44)
        layout.addWidget(self._logo_team)

        layout.addSpacing(8)

        # Team name — RYUGU (large, accent)
        lbl_team = QLabel(TEAM_NAME)
        lbl_team.setObjectName("topBarTeam")
        lbl_team.setFont(QFont(FONT_FAMILY, 16, QFont.Bold))
        layout.addWidget(lbl_team)

        sep1 = QLabel("  |  ")
        sep1.setStyleSheet(f"color: {COLOR_BORDER}; font-size: 16px;")
        layout.addWidget(sep1)

        lbl_uni = QLabel(UNIVERSITY_NAME)
        lbl_uni.setObjectName("topBarUniversity")
        lbl_uni.setFont(QFont(FONT_FAMILY, 13))
        layout.addWidget(lbl_uni)

        sep2 = QLabel("  |  ")
        sep2.setStyleSheet(f"color: {COLOR_BORDER}; font-size: 16px;")
        layout.addWidget(sep2)

        lbl_comp = QLabel(COMPETITION)
        lbl_comp.setFont(QFont(FONT_FAMILY, 12))
        lbl_comp.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: bold;")
        layout.addWidget(lbl_comp)

        layout.addStretch()

        # Live clock
        self._clock_label = QLabel()
        self._clock_label.setObjectName("topBarDatetime")
        self._clock_label.setFont(QFont("Consolas", 12))
        self._clock_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._clock_label)

        layout.addSpacing(8)

        # KKI Logo
        self._logo_kki = QLabel()
        self._logo_kki.setFixedSize(44, 44)
        self._logo_kki.setStyleSheet("border: none;")
        self._load_logo(self._logo_kki, ASSET_LOGO_KKI, 44)
        layout.addWidget(self._logo_kki)

        return bar

    def _build_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(4)

        # ── Row 0 ─────────────────────────────────────────────────────
        # Col 0: Front Camera
        self.cam_front = CameraPanel("FRONT CAM")
        grid.addWidget(self.cam_front, 0, 0)

        # Col 1: Bottom / Side Camera
        self.cam_bottom = CameraPanel("BOTTOM CAM")
        grid.addWidget(self.cam_bottom, 0, 1)

        # Col 2: QR Result Panel
        self.qr_panel = QRResultPanel()
        self.qr_panel.emergency_stop.connect(self._on_emergency_stop)
        grid.addWidget(self.qr_panel, 0, 2)

        # ── Row 1 ─────────────────────────────────────────────────────
        # Col 0: Altitude
        self.alt_panel = AltitudePanel()
        grid.addWidget(self.alt_panel, 1, 0)

        # Col 1: Trajectory Map
        self.traj_panel = TrajectoryPanel()
        grid.addWidget(self.traj_panel, 1, 1)

        # Col 2: ROV Design
        self.rov_panel = ROVDesignPanel()
        grid.addWidget(self.rov_panel, 1, 2)

        # Cameras (col 0 & 1) wider than QR/ROV panels
        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 4)
        grid.setColumnStretch(2, 3)
        # Row height ratio — cameras (row 0) vs telemetry panels (row 1)
        # Adjusted from 7:3 to 6:4 for better lower panel visibility
        grid.setRowStretch(0, 6)
        grid.setRowStretch(1, 4)

        return grid

    @staticmethod
    def _load_logo(label: QLabel, path: str, size: int):
        pix = QPixmap(path)
        if not pix.isNull():
            label.setPixmap(pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            label.setText("")

    # ── Clock ─────────────────────────────────────────────────────────

    def _start_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    def _tick_clock(self):
        now = datetime.now()
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day = day_names[now.weekday()]
        text = f"{day}  {now.strftime('%d %b %Y')}    {now.strftime('%H:%M:%S')}"
        self._clock_label.setText(text)

        # ── Telemetry timeout checks ──────────────────────────────────
        mono = time.monotonic()

        if self._last_imu_time and (mono - self._last_imu_time) > _TELEM_TIMEOUT_S:
            self._footer.set_imu_status(False, "OFFLINE")
            self._last_imu_time = 0.0   # avoid repeated updates

        if self._last_depth_time and (mono - self._last_depth_time) > _TELEM_TIMEOUT_S:
            self._footer.set_bar30_status(False, "OFFLINE")
            self._last_depth_time = 0.0

        if self._last_status_time and (mono - self._last_status_time) > _TELEM_TIMEOUT_S:
            self._footer.set_battery_status(False, "OFFLINE")
            self._last_status_time = 0.0

    # ── Gamepad signal handlers ───────────────────────────────────────

    @pyqtSlot(dict)
    def on_axes_updated(self, axes: dict):
        """Handle gamepad axes update.

        - Forward yaw to trajectory panel heading
        - Forward all axes to Ethernet worker as motion command
        """
        # Yaw → trajectory heading
        yaw_norm = axes.get("yaw", 0) / 1000.0  # back to -1..+1
        if yaw_norm != 0.0:
            self.traj_panel.update_heading(yaw_norm)

        # Forward to Jetson via Ethernet
        if self._eth_worker is not None:
            self._eth_worker.send_motion(axes)

    @pyqtSlot(bool)
    def on_arm_event(self, armed: bool):
        """Handle ARM/DISARM from gamepad."""
        self._armed = armed
        if armed:
            self.qr_panel.add_log("SYSTEM ARMED", COLOR_OK)
        else:
            self.qr_panel.add_log("SYSTEM DISARMED", COLOR_WARN)

        # Forward to Jetson
        if self._eth_worker is not None:
            self._eth_worker.send_arm(armed)

    @pyqtSlot(str, bool)
    def on_button_event(self, action: str, pressed: bool):
        """Handle button events from gamepad (gripper, ballast).

        Gripper uses one-shot trigger: only send on press, not on release.
        Ballast retains hold-to-activate behaviour.
        """
        if self._eth_worker is None:
            return

        if action == "gripper_open":
            if pressed:
                self._eth_worker.send_gripper(1)   # OPEN
        elif action == "gripper_close":
            if pressed:
                self._eth_worker.send_gripper(2)   # CLOSE
        elif action == "ballast_fill":
            self._eth_worker.send_ballast(1 if pressed else 0)
        elif action == "ballast_drain":
            self._eth_worker.send_ballast(2 if pressed else 0)

    @pyqtSlot(str)
    def on_mode_changed(self, mode: str):
        """Handle flight mode change from gamepad."""
        self._footer.set_mode(mode)

        # Log mode transition to status log
        if self._prev_mode != mode:
            self._prev_mode = mode
            self.qr_panel.add_log(f"MODE: {mode}", "#00BCD4")

        # Forward to Jetson
        if self._eth_worker is not None:
            self._eth_worker.send_mode(mode)

    # ── Emergency Stop handler ────────────────────────────────────────

    def _on_emergency_stop(self):
        """
        Called when the E-STOP button is pressed.
        Updates footer and sends E-STOP command to Jetson.
        """
        self._footer.set_mode("E-STOP")
        self._armed = False

        if self._eth_worker is not None:
            self._eth_worker.send_estop()

    # ── Public wiring helpers (called by main.py after thread setup) ──

    def wire_ethernet(self, worker):
        """Connect an EthernetWorker's signals to the correct panels.

        Parameters
        ----------
        worker : EthernetWorker
            The Ethernet worker thread instance.
        """
        self._eth_worker = worker

        # Telemetry → panels
        worker.depth_updated.connect(self._on_depth_updated)
        worker.imu_updated.connect(self._on_imu_updated)
        worker.status_updated.connect(self._on_status_updated)
        worker.qr_detected.connect(self.qr_panel.update_qr)

        # Connection status → footer + status log
        worker.connection_changed.connect(self._on_connection_changed)

        # ACK feedback
        worker.command_timeout.connect(self._on_command_timeout)

    @pyqtSlot(bool)
    def _on_connection_changed(self, connected: bool):
        """Handle Jetson connection status change — update footer and log."""
        self._footer.set_connection(connected)

        # Log only on actual transitions
        if self._prev_connected != connected:
            self._prev_connected = connected
            if connected:
                self.qr_panel.add_log("JETSON: ONLINE", COLOR_OK)
            else:
                self.qr_panel.add_log("JETSON: OFFLINE", COLOR_ERROR)

    @pyqtSlot(float, float, float)
    def _on_imu_updated(self, pitch: float, roll: float, yaw: float):
        """Handle IMU data from Ethernet — update ROV design panel + footer."""
        self.rov_panel.update_state(f"P:{pitch:.0f}° R:{roll:.0f}° Y:{yaw:.0f}°")

        # Mark IMU as alive
        self._last_imu_time = time.monotonic()
        self._footer.set_imu_status(
            True, f"P:{pitch:.0f}° R:{roll:.0f}° Y:{yaw:.0f}°"
        )

    @pyqtSlot(dict)
    def _on_status_updated(self, status: dict):
        """Handle status telemetry from Ethernet."""
        battery = status.get("battery_v", 0.0)
        arm = status.get("arm_state", False)
        mode = status.get("mode", "MANUAL")
        self._armed = arm
        self._footer.set_mode(mode)

        # Mark battery status as alive
        self._last_status_time = time.monotonic()
        self._footer.set_battery_status(True, f"{battery:.1f}V")

    @pyqtSlot(int)
    def _on_command_timeout(self, packet_id: int):
        """Handle critical command ACK timeout."""
        # Show timeout on the battery indicator (status packet)
        self._footer.set_battery_status(
            False, f"CMD TIMEOUT (0x{packet_id:02X})"
        )

    # ── Depth packet handler (called via wire_ethernet lambda) ────────

    def _on_depth_updated(self, depth: float, alt: float):
        """Handle depth telemetry — update altitude panel + BAR30 indicator."""
        self.alt_panel.update_depth(depth)
        self._last_depth_time = time.monotonic()
        self._footer.set_bar30_status(True, f"{depth:.2f}m")

    # ── Legacy wiring helpers (kept for compatibility) ────────────────

    def wire_telemetry(self, thread):
        """Connect a TelemetryThread's signals to the correct panels."""
        thread.depth_updated.connect(self.alt_panel.update_depth)
        thread.position_updated.connect(self.traj_panel.update_position)
        thread.state_updated.connect(self.rov_panel.update_state)
        thread.mode_updated.connect(self._footer.set_mode)

    def wire_qr(self, thread):
        """Connect a QRThread's signals to the QR panel."""
        thread.qr_detected.connect(self.qr_panel.update_qr)

    def wire_cameras(self, front_thread, bottom_thread):
        """Connect camera threads to camera panels."""
        front_thread.frame_ready.connect(self.cam_front.update_frame)
        bottom_thread.frame_ready.connect(self.cam_bottom.update_frame)
