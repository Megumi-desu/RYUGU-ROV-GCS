import math
import datetime
import os
from enum import IntEnum

import cv2
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QPointF, QTimer
from PyQt5.QtGui import QFont, QImage

from utils.constants import (
    COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT,
    COLOR_OK, COLOR_TEXT_DIM,
    POOL_SIZE_X, POOL_SIZE_Y, FONT_FAMILY
)

pg.setConfigOption("background", "#0d1b2a")
pg.setConfigOption("foreground", "#7a8a99")


# ── Compass helper ─────────────────────────────────────────────────────────

_COMPASS_DIRS = [
    (0,   "E"), (45,  "NE"), (90,  "N"), (135, "NW"),
    (180, "W"), (225, "SW"), (270, "S"), (315, "SE"),
]


def _compass_label(deg: float) -> str:
    """Convert heading in degrees (0°=East, CCW positive) to compass string."""
    deg = deg % 360
    closest = min(_COMPASS_DIRS, key=lambda d: min(abs(deg - d[0]), 360 - abs(deg - d[0])))
    return closest[1]


class _SetupPhase(IntEnum):
    IDLE = 0
    PICK_ORIGIN = 1
    PICK_HEADING = 2
    RUNNING = 3


class TrajectoryPanel(QFrame):
    """
    2D top-down trajectory map using pyqtgraph.
    Shows: pool boundary, path line, and a white dot for current ROV position.
    Start (S) and End (E) markers are plotted when START/END are confirmed.

    Buttons: START, PAUSE, END, RESET.
    Position updated via update_position(dx, dy) from gamepad left stick.
    Heading updated via update_heading(dyaw) from gamepad right stick.

    Dead reckoning: open-loop integration of gamepad inputs.
    """

    # Speed constants for dead reckoning calibration (meters per update at full stick)
    SPEED_SURGE = 0.05
    SPEED_SWAY = 0.05

    mission_started = pyqtSignal()
    mission_paused = pyqtSignal()
    mission_ended = pyqtSignal()
    mission_reset = pyqtSignal()
    position_changed = pyqtSignal(float, float, float)  # x, y, total_distance
    heading_changed = pyqtSignal(float)                  # heading_deg (plot convention, live)
    # Emitted once when setup completes: carries the initial GCS heading (plot
    # convention, 0°=East CCW+) that the operator chose by dragging on the map.
    # MainWindow uses this to compute the Pixhawk yaw offset.
    heading_setup_done = pyqtSignal(float)               # initial_heading_deg
    recording_started = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path_x: list[float] = []
        self._path_y: list[float] = []
        self._mission_active = False
        self._mission_locked = False
        self._rov_x = POOL_SIZE_X / 2
        self._rov_y = POOL_SIZE_Y / 2
        self._sensitivity = 0.5
        self._total_distance = 0.0

        # Setup phase
        self._setup_phase = _SetupPhase.IDLE
        self._heading_deg = 0.0
        self._drag_origin_x = 0.0
        self._drag_origin_y = 0.0

        # Plot items
        self._start_marker = None
        self._end_marker = None
        self._start_text = None
        self._end_text = None
        self._heading_arrow = None
        self._rov_arrow = None
        self._preview_dot = None
        self._record_timer = QTimer()
        self._record_timer.timeout.connect(self._record_frame)
        self._traj_writer = None
        self._traj_record_path = ""

        self._setup_ui()
        self._connect_mouse_events()

    def _connect_mouse_events(self):
        self._plot.scene().sigMouseClicked.connect(self._on_map_clicked)
        self._plot.scene().sigMouseMoved.connect(self._on_map_mouse_moved)

    def _scene_to_data(self, scene_pos: QPointF):
        vb = self._plot.getViewBox()
        data_pos = vb.mapSceneToView(scene_pos)
        return data_pos.x(), data_pos.y()

    # ── Mouse event handlers ───────────────────────────────────────────────

    def _on_map_clicked(self, event):
        if self._setup_phase == _SetupPhase.PICK_ORIGIN:
            scene_pos = event.scenePos()
            x, y = self._scene_to_data(scene_pos)
            self._drag_origin_x = x
            self._drag_origin_y = y

            self._preview_dot = pg.ScatterPlotItem(
                size=10,
                pen=pg.mkPen(None),
                brush=pg.mkBrush("#00FFFF")
            )
            self._preview_dot.setData([x], [y])
            self._plot.addItem(self._preview_dot)

            self._instr_label.setText(
                "Drag from origin to set heading, release to confirm"
            )
            self._setup_phase = _SetupPhase.PICK_HEADING

        elif self._setup_phase == _SetupPhase.PICK_HEADING:
            scene_pos = event.scenePos()
            x, y = self._scene_to_data(scene_pos)
            dx = x - self._drag_origin_x
            dy = y - self._drag_origin_y
            deg = math.degrees(math.atan2(dy, dx))
            if deg < 0:
                deg += 360

            self._rov_x = self._drag_origin_x
            self._rov_y = self._drag_origin_y
            self._heading_deg = deg
            self._mission_active = True
            self._total_distance = 0.0
            self._pos_dot.setData([self._rov_x], [self._rov_y])
            self._plot_start_marker(self._rov_x, self._rov_y)
            self._update_rov_arrow()
            self._update_coord_label()

            self._instr_label.hide()
            self._plot.setCursor(Qt.ArrowCursor)

            if self._preview_dot is not None:
                self._plot.removeItem(self._preview_dot)
                self._preview_dot = None
            if self._heading_arrow is not None:
                self._plot.removeItem(self._heading_arrow)
                self._heading_arrow = None

            self._start_btn.setEnabled(False)
            self._pause_btn.setEnabled(True)
            self._pause_btn.setStyleSheet(
                "min-height: 30px; font-weight: bold; border-radius: 4px;"
                " border: none; color: #ffffff; background-color: #FF9800;"
            )
            self._end_btn.setEnabled(True)
            self._end_btn.setStyleSheet(
                "min-height: 30px; font-weight: bold; border-radius: 4px;"
                " border: none; color: #ffffff; background-color: #F44336;"
            )
            self._setup_phase = _SetupPhase.RUNNING
            self.mission_started.emit()
            self.heading_changed.emit(self._heading_deg)
            # Notify MainWindow so it can lock the Pixhawk yaw offset for this
            # mission.  Carrying the GCS plot-convention heading chosen by the
            # operator (0°=East, CCW positive).
            self.heading_setup_done.emit(self._heading_deg)

            now_str = datetime.datetime.now().strftime("%d-%b-%Y_%H-%M-%S")
            folder_path = os.path.join(os.getcwd(), "recordings", f"Misi_{now_str}")
            os.makedirs(folder_path, exist_ok=True)
            self._traj_record_path = os.path.join(folder_path, "Trajectory_Record.mp4")
            self._record_timer.start(100)
            self.recording_started.emit(folder_path)

    def _on_map_mouse_moved(self, pos: QPointF):
        if self._setup_phase == _SetupPhase.PICK_HEADING:
            x, y = self._scene_to_data(pos)
            dx = x - self._drag_origin_x
            dy = y - self._drag_origin_y
            rad = math.atan2(dy, dx)
            deg = math.degrees(rad)
            if deg < 0:
                deg += 360

            if self._heading_arrow is not None:
                self._plot.removeItem(self._heading_arrow)

            # Convert to pyqtgraph angle convention (0° = left/-X)
            pg_angle = (180.0 - deg) % 360.0
            self._heading_arrow = pg.ArrowItem(
                pos=(x, y),
                angle=pg_angle,
                tipAngle=25,
                headLen=14,
                tailLen=0,
                pen=pg.mkPen("#FFD700", width=1.5),
                brush=pg.mkBrush("#FFD700")
            )
            self._plot.addItem(self._heading_arrow)

    # ── UI setup ───────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setObjectName("trajFrame")
        self.setStyleSheet(f"""
            QFrame#trajFrame {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT: pyqtgraph plot ────────────────────────────────────────
        self._plot = pg.PlotWidget()
        self._plot.setAspectLocked(True)
        self._plot.setXRange(-0.5, POOL_SIZE_X + 0.5, padding=0)
        self._plot.setYRange(-0.5, POOL_SIZE_Y + 0.5, padding=0)
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.getAxis("bottom").setLabel("X (m)")
        self._plot.getAxis("left").setLabel("Y (m)")
        self._plot.setMouseEnabled(x=False, y=False)

        # Pool boundary
        pool_x = [0, POOL_SIZE_X, POOL_SIZE_X, 0, 0]
        pool_y = [0, 0, POOL_SIZE_Y, POOL_SIZE_Y, 0]
        self._plot.plot(
            pool_x, pool_y,
            pen=pg.mkPen(color="#0f3460", width=2, style=pg.QtCore.Qt.DashLine)
        )

        # Path line (updated dynamically)
        self._path_line = self._plot.plot(
            [], [],
            pen=pg.mkPen(color=COLOR_ACCENT, width=2),
            name="Path"
        )

        # Current position dot
        self._pos_dot = pg.ScatterPlotItem(
            size=12,
            pen=pg.mkPen(None),
            brush=pg.mkBrush("#ffffff")
        )
        self._plot.addItem(self._pos_dot)
        self._pos_dot.setData([self._rov_x], [self._rov_y])

        root.addWidget(self._plot, stretch=3)

        # ── RIGHT: Control buttons + coord label ─────────────────────────
        right = QVBoxLayout()
        right.setContentsMargins(8, 8, 8, 8)
        right.setSpacing(6)

        btn_style = (
            "min-height: 30px; font-weight: bold;"
            " border-radius: 4px; border: none; color: #ffffff;"
        )

        self._start_btn = QPushButton("START")
        self._start_btn.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self._start_btn.setStyleSheet(
            btn_style + " background-color: #4CAF50;"
        )
        self._start_btn.clicked.connect(self._on_start)
        right.addWidget(self._start_btn)

        self._pause_btn = QPushButton("PAUSE")
        self._pause_btn.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self._pause_btn.setEnabled(False)
        self._pause_btn.setStyleSheet(
            btn_style + " background-color: #424242;"
        )
        self._pause_btn.clicked.connect(self._on_pause)
        right.addWidget(self._pause_btn)

        self._end_btn = QPushButton("END")
        self._end_btn.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self._end_btn.setEnabled(False)
        self._end_btn.setStyleSheet(
            btn_style + " background-color: #424242;"
        )
        self._end_btn.clicked.connect(self._on_end)
        right.addWidget(self._end_btn)

        self._reset_btn = QPushButton("RESET")
        self._reset_btn.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self._reset_btn.setStyleSheet(
            btn_style + " background-color: #607D8B;"
        )
        self._reset_btn.clicked.connect(self._on_reset)
        right.addWidget(self._reset_btn)

        right.addSpacing(8)

        # Instruction label (hidden by default)
        self._instr_label = QLabel("")
        self._instr_label.setFont(QFont(FONT_FAMILY, 9))
        self._instr_label.setWordWrap(True)
        self._instr_label.setAlignment(Qt.AlignLeft)
        self._instr_label.setStyleSheet(
            "color: #FFD700; border: 1px solid #FFD700;"
            " border-radius: 4px; padding: 6px; background: #0D1B2A;"
        )
        self._instr_label.hide()
        right.addWidget(self._instr_label)

        right.addSpacing(4)

        # Coord label (position + heading + distance)
        self._coord_label = QLabel(
            f"X: {self._rov_x:.1f}m  Y: {self._rov_y:.1f}m"
        )
        self._coord_label.setFont(QFont(FONT_FAMILY, 10))
        self._coord_label.setAlignment(Qt.AlignLeft)
        self._coord_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; border: none;")
        right.addWidget(self._coord_label)

        # Heading label
        self._heading_label = QLabel("HDG: 000° (E)")
        self._heading_label.setFont(QFont(FONT_FAMILY, 10))
        self._heading_label.setAlignment(Qt.AlignLeft)
        self._heading_label.setStyleSheet("color: #00BFFF; border: none;")
        right.addWidget(self._heading_label)

        # Distance label
        self._dist_label = QLabel("DIST: 0.00 m")
        self._dist_label.setFont(QFont(FONT_FAMILY, 10))
        self._dist_label.setAlignment(Qt.AlignLeft)
        self._dist_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; border: none;")
        right.addWidget(self._dist_label)

        right.addStretch()

        root.addLayout(right, stretch=1)

    # ── Marker helpers ─────────────────────────────────────────────────────

    def _plot_start_marker(self, x: float, y: float):
        self._start_marker = pg.ScatterPlotItem(
            size=14,
            pen=pg.mkPen(COLOR_OK, width=2),
            brush=pg.mkBrush(None)
        )
        self._start_marker.setData([x], [y])
        self._plot.addItem(self._start_marker)
        self._start_text = pg.TextItem("S", color=COLOR_OK, anchor=(0.5, 1.2))
        self._start_text.setPos(x, y)
        self._plot.addItem(self._start_text)

    def _plot_end_marker(self, x: float, y: float):
        self._end_marker = pg.ScatterPlotItem(
            size=14,
            pen=pg.mkPen(COLOR_ACCENT, width=2),
            brush=pg.mkBrush(None)
        )
        self._end_marker.setData([x], [y])
        self._plot.addItem(self._end_marker)
        self._end_text = pg.TextItem("E", color=COLOR_ACCENT, anchor=(0.5, 1.2))
        self._end_text.setPos(x, y)
        self._plot.addItem(self._end_text)

    def _remove_start_marker(self):
        if self._start_marker is not None:
            self._plot.removeItem(self._start_marker)
            self._start_marker = None
        if self._start_text is not None:
            self._plot.removeItem(self._start_text)
            self._start_text = None

    def _remove_end_marker(self):
        if self._end_marker is not None:
            self._plot.removeItem(self._end_marker)
            self._end_marker = None
        if self._end_text is not None:
            self._plot.removeItem(self._end_text)
            self._end_text = None

    # ── Heading arrow helpers ──────────────────────────────────────────────

    def _update_rov_arrow(self):
        if self._rov_arrow is not None:
            self._plot.removeItem(self._rov_arrow)
        rad = math.radians(self._heading_deg)
        arrow_len = 0.4
        tip_x = self._rov_x + arrow_len * math.cos(rad)
        tip_y = self._rov_y + arrow_len * math.sin(rad)
        # pyqtgraph ArrowItem uses angle 0° = left (-X), but our convention
        # is 0° = right (+X, East).  Convert: pyqtgraph_angle = 180° - heading.
        pg_angle = (180.0 - self._heading_deg) % 360.0
        self._rov_arrow = pg.ArrowItem(
            pos=(tip_x, tip_y),
            angle=pg_angle,
            tipAngle=30,
            headLen=12,
            tailLen=0,
            pen=pg.mkPen("#00BFFF", width=1),
            brush=pg.mkBrush("#00BFFF")
        )
        self._plot.addItem(self._rov_arrow)

    def _remove_rov_arrow(self):
        if self._rov_arrow is not None:
            self._plot.removeItem(self._rov_arrow)
            self._rov_arrow = None

    def _remove_heading_arrow(self):
        if self._heading_arrow is not None:
            self._plot.removeItem(self._heading_arrow)
            self._heading_arrow = None

    def _remove_preview_dot(self):
        if self._preview_dot is not None:
            self._plot.removeItem(self._preview_dot)
            self._preview_dot = None

    # ── Button callbacks ──────────────────────────────────────────────────

    def _on_start(self):
        self._start_btn.setEnabled(False)
        self._instr_label.setText(
            "Click on map to set ROV start position"
        )
        self._instr_label.show()
        self._plot.setCursor(Qt.CrossCursor)
        self._setup_phase = _SetupPhase.PICK_ORIGIN

    def _on_pause(self):
        self._stop_recording()
        self._mission_active = False
        self._pause_btn.setEnabled(False)
        self._pause_btn.setStyleSheet(
            "min-height: 30px; font-weight: bold; border-radius: 4px;"
            " border: none; color: #ffffff; background-color: #424242;"
        )
        self._start_btn.setEnabled(True)
        self.mission_paused.emit()

    def _on_end(self):
        self._stop_recording()
        self._mission_active = False
        self._mission_locked = True
        self._start_btn.setEnabled(False)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setStyleSheet(
            "min-height: 30px; font-weight: bold; border-radius: 4px;"
            " border: none; color: #ffffff; background-color: #424242;"
        )
        self._end_btn.setEnabled(False)
        self._end_btn.setStyleSheet(
            "min-height: 30px; font-weight: bold; border-radius: 4px;"
            " border: none; color: #ffffff; background-color: #424242;"
        )
        self._plot_end_marker(self._rov_x, self._rov_y)
        self.mission_ended.emit()

    def _on_reset(self):
        self._stop_recording()
        self._mission_active = False
        self._mission_locked = False
        self._setup_phase = _SetupPhase.IDLE
        self._heading_deg = 0.0
        self._total_distance = 0.0

        self._remove_start_marker()
        self._remove_end_marker()
        self._remove_rov_arrow()
        self._remove_heading_arrow()
        self._remove_preview_dot()

        self._path_x.clear()
        self._path_y.clear()
        self._path_line.setData([], [])
        self._rov_x = POOL_SIZE_X / 2
        self._rov_y = POOL_SIZE_Y / 2
        self._pos_dot.setData([self._rov_x], [self._rov_y])
        self._instr_label.hide()
        self._plot.setCursor(Qt.ArrowCursor)
        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setStyleSheet(
            "min-height: 30px; font-weight: bold; border-radius: 4px;"
            " border: none; color: #ffffff; background-color: #424242;"
        )
        self._end_btn.setEnabled(False)
        self._end_btn.setStyleSheet(
            "min-height: 30px; font-weight: bold; border-radius: 4px;"
            " border: none; color: #ffffff; background-color: #424242;"
        )
        self._update_coord_label()
        self.heading_changed.emit(0.0)

    def _stop_recording(self):
        self._record_timer.stop()
        if self._traj_writer is not None:
            self._traj_writer.release()
            self._traj_writer = None

    def _record_frame(self):
        qimg = self.grab().toImage().convertToFormat(QImage.Format_RGB888)
        width, height = qimg.width(), qimg.height()
        pointer = qimg.constBits()
        pointer.setsize(height * width * 3)
        frame = np.array(pointer).reshape(height, width, 3)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        if self._traj_writer is None:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._traj_writer = cv2.VideoWriter(
                self._traj_record_path, fourcc, 10.0, (width, height)
            )
        self._traj_writer.write(frame)
        self.mission_reset.emit()

    # ── Position update ───────────────────────────────────────────────────

    @pyqtSlot(float, float)
    def update_position(self, dx: float, dy: float):
        """Update ROV position using open-loop dead reckoning.

        Parameters
        ----------
        dx : float
            Sway input (-1..+1). Positive = strafe right.
        dy : float
            Surge input (-1..+1). Positive = forward.

        Coordinate system:
            - heading_deg measured from +X axis (East), CCW positive
            - 0° = East, 90° = North on the pyqtgraph plot
            - Surge moves along the heading direction
            - Sway moves perpendicular to heading (positive = right)
        """
        if not self._mission_active:
            return
        if dx == 0.0 and dy == 0.0:
            return

        rad = math.radians(self._heading_deg)
        surge = dy
        sway = dx

        # Body-to-world rotation for sway-positive-right convention:
        #   world_x = surge * cos(θ) + sway * sin(θ)
        #   world_y = surge * sin(θ) - sway * cos(θ)
        #
        # Verification (heading = 90° = North):
        #   sway right → world_dx = +sway*sin(90°) = +sway  ✓
        #   surge fwd  → world_dy = +surge*sin(90°) = +surge ✓
        world_dx = (surge * math.cos(rad) + sway * math.sin(rad)) * self.SPEED_SURGE * self._sensitivity
        world_dy = (surge * math.sin(rad) - sway * math.cos(rad)) * self.SPEED_SWAY * self._sensitivity

        prev_x, prev_y = self._rov_x, self._rov_y
        self._rov_x = max(0.0, min(self._rov_x + world_dx, POOL_SIZE_X))
        self._rov_y = max(0.0, min(self._rov_y + world_dy, POOL_SIZE_Y))

        # Accumulate distance traveled
        step_dist = math.hypot(self._rov_x - prev_x, self._rov_y - prev_y)
        self._total_distance += step_dist

        self._path_x.append(self._rov_x)
        self._path_y.append(self._rov_y)
        self._path_line.setData(self._path_x, self._path_y)
        self._pos_dot.setData([self._rov_x], [self._rov_y])
        self._update_rov_arrow()
        self._update_coord_label()
        self.position_changed.emit(self._rov_x, self._rov_y, self._total_distance)

    @pyqtSlot(float)
    def update_heading(self, dyaw: float):
        """Update ROV heading from gamepad yaw input.

        Parameters
        ----------
        dyaw : float
            Yaw stick value (-1..+1). Positive = rotate right (CW on map).
        """
        if not self._mission_active:
            return
        YAW_RATE = 2.0   # degrees per update at full stick
        # Positive dyaw (right stick right) → clockwise → decrease heading
        self._heading_deg -= dyaw * YAW_RATE
        self._heading_deg %= 360.0
        self._update_rov_arrow()
        self._update_coord_label()
        self.heading_changed.emit(self._heading_deg)

    # ── Hybrid dead-reckoning helpers (PIXHAWK_HYBRID mode) ───────────────

    @pyqtSlot(float, float)
    def update_position_hybrid(self, world_dx: float, world_dy: float):
        """Update ROV position using pre-rotated world-frame deltas.

        Called by MainWindow when POSITION_MODE == "PIXHAWK_HYBRID".
        The body-to-world rotation has already been applied using the
        real IMU yaw, so we just integrate the deltas directly.

        Parameters
        ----------
        world_dx : float
            Displacement in the world X axis (East) in metres.
        world_dy : float
            Displacement in the world Y axis (North) in metres.
        """
        if not self._mission_active:
            return
        if world_dx == 0.0 and world_dy == 0.0:
            return

        prev_x, prev_y = self._rov_x, self._rov_y
        self._rov_x = max(0.0, min(self._rov_x + world_dx, POOL_SIZE_X))
        self._rov_y = max(0.0, min(self._rov_y + world_dy, POOL_SIZE_Y))

        # Accumulate distance traveled
        step_dist = math.hypot(self._rov_x - prev_x, self._rov_y - prev_y)
        self._total_distance += step_dist

        self._path_x.append(self._rov_x)
        self._path_y.append(self._rov_y)
        self._path_line.setData(self._path_x, self._path_y)
        self._pos_dot.setData([self._rov_x], [self._rov_y])
        self._update_rov_arrow()
        self._update_coord_label()
        self.position_changed.emit(self._rov_x, self._rov_y, self._total_distance)

    def set_heading_absolute(self, imu_yaw_deg: float):
        """Set heading directly from IMU yaw (PIXHAWK_HYBRID mode).

        Converts from NED convention (0°=North, CW positive) to the
        plot convention (0°=East, CCW positive) used by pyqtgraph.

        Parameters
        ----------
        imu_yaw_deg : float
            Yaw heading from the Pixhawk IMU in degrees (NED frame).
        """
        if not self._mission_active:
            return
        # NED → math/plot:  plot_heading = 90 - imu_yaw
        self._heading_deg = (90.0 - imu_yaw_deg) % 360.0
        self._update_rov_arrow()
        self._update_coord_label()
        self.heading_changed.emit(self._heading_deg)

    def set_heading_absolute_offsetted(self, map_heading_deg: float):
        """Set heading from a pre-computed plot-convention heading.

        Used by MainWindow._update_hybrid_dr() in PIXHAWK_HYBRID mode.
        The caller has already applied the NED→plot conversion AND the
        operator yaw offset, so we just store the value directly.

        Parameters
        ----------
        map_heading_deg : float
            Heading in plot convention (0°=East, CCW+) with operator
            offset already applied.  Range [0, 360).
        """
        if self._rov_arrow is None:
            return
        self._heading_deg = map_heading_deg % 360.0
        self._update_rov_arrow()
        self._update_coord_label()
        self.heading_changed.emit(self._heading_deg)

    def _update_coord_label(self):
        self._coord_label.setText(
            f"X: {self._rov_x:.1f}m  Y: {self._rov_y:.1f}m"
        )
        compass = _compass_label(self._heading_deg)
        self._heading_label.setText(
            f"HDG: {self._heading_deg:05.1f}° ({compass})"
        )
        self._dist_label.setText(
            f"DIST: {self._total_distance:.2f} m"
        )

    # ── Utility ───────────────────────────────────────────────────────────

    def get_heading(self) -> float:
        """Return current heading in degrees (0°=East, CCW positive)."""
        return self._heading_deg

    def clear_path(self):
        self._mission_active = False
        self._mission_locked = False
        self._setup_phase = _SetupPhase.IDLE
        self._heading_deg = 0.0
        self._total_distance = 0.0

        self._remove_start_marker()
        self._remove_end_marker()
        self._remove_rov_arrow()
        self._remove_heading_arrow()
        self._remove_preview_dot()

        self._path_x.clear()
        self._path_y.clear()
        self._path_line.setData([], [])
        self._rov_x = POOL_SIZE_X / 2
        self._rov_y = POOL_SIZE_Y / 2
        self._pos_dot.setData([self._rov_x], [self._rov_y])
        self._instr_label.hide()
        self._plot.setCursor(Qt.ArrowCursor)
        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setStyleSheet(
            "min-height: 30px; font-weight: bold; border-radius: 4px;"
            " border: none; color: #ffffff; background-color: #424242;"
        )
        self._end_btn.setEnabled(False)
        self._end_btn.setStyleSheet(
            "min-height: 30px; font-weight: bold; border-radius: 4px;"
            " border: none; color: #ffffff; background-color: #424242;"
        )
        self._update_coord_label()
        self.heading_changed.emit(0.0)
