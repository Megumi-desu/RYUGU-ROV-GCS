"""
IMUIndicatorWidget — dual-canvas attitude and heading display.

Renders two side-by-side custom paint widgets:
  1. Artificial Horizon: pitch (vertical shift) + roll (rotation) bubble indicator
  2. Compass Rose:       yaw heading as a rotating dial with degree readout

Data source: IMU pitch / roll / yaw from Pixhawk via EthernetWorker.

Usage::

    imu = IMUIndicatorWidget()
    imu.update_imu(pitch_deg, roll_deg, yaw_deg)

Or wire directly::

    ethernet_worker.imu_updated.connect(imu.update_imu)
"""

import math

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSlot, QPoint, QRect
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QLinearGradient, QPolygon,
)

from utils.constants import (
    COLOR_PANEL_DARK, COLOR_BORDER, COLOR_ACCENT,
    COLOR_TEXT, COLOR_TEXT_DIM,
    FONT_FAMILY,
)


# ── Artificial Horizon Canvas ─────────────────────────────────────────────────

class _HorizonCanvas(QWidget):
    """Draws an artificial horizon (attitude ball) for pitch and roll.

    - Pitch shifts the horizon line vertically (positive pitch = nose up = line moves down)
    - Roll rotates the entire horizon around the center
    - A fixed center reticle dot stays on top
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pitch = 0.0
        self._roll = 0.0
        self.setMinimumSize(90, 90)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(90, 90)

    def set_attitude(self, pitch: float, roll: float):
        self._pitch = pitch
        self._roll = roll
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(cx, cy) - 4

        # ── Clip to circle ────────────────────────────────────────────
        from PyQt5.QtGui import QPainterPath
        clip_path = QPainterPath()
        clip_path.addEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.setClipPath(clip_path)

        # ── Save & rotate canvas by roll angle ────────────────────────
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._roll)

        # Pitch offset: each degree shifts horizon by (radius / 45) pixels
        pitch_px = self._pitch * (radius / 45.0)
        pitch_px = max(-radius, min(radius, pitch_px))

        # Sky (above horizon) — dark blue
        sky_grad = QLinearGradient(0, -radius, 0, pitch_px)
        sky_grad.setColorAt(0.0, QColor("#0d3a6e"))
        sky_grad.setColorAt(1.0, QColor("#1565c0"))
        painter.fillRect(-radius, -radius, radius * 2, int(radius + pitch_px), QBrush(sky_grad))

        # Ground (below horizon) — dark brown/olive
        gnd_grad = QLinearGradient(0, pitch_px, 0, radius)
        gnd_grad.setColorAt(0.0, QColor("#4e342e"))
        gnd_grad.setColorAt(1.0, QColor("#2e1a10"))
        painter.fillRect(-radius, int(pitch_px), radius * 2, int(radius - pitch_px) + 1, QBrush(gnd_grad))

        # Horizon line
        pen = QPen(QColor("#ffffff"), 2)
        painter.setPen(pen)
        painter.drawLine(-radius, int(pitch_px), radius, int(pitch_px))

        # Pitch tick marks (every 10°)
        painter.setPen(QPen(QColor("#ffffffaa"), 1))
        for deg in range(-30, 31, 10):
            if deg == 0:
                continue
            y = int(pitch_px - deg * (radius / 45.0))
            tick_w = radius // 3 if deg % 20 == 0 else radius // 5
            painter.drawLine(-tick_w, y, tick_w, y)

        painter.restore()

        # ── Remove clip for overlay elements ──────────────────────────
        painter.setClipping(False)

        # ── Circle border ─────────────────────────────────────────────
        painter.setPen(QPen(QColor(COLOR_BORDER), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # ── Fixed center reticle (stays horizontal, always visible) ───
        painter.setPen(QPen(QColor("#00bcd4"), 2))
        rl = radius // 3
        # Left arm
        painter.drawLine(cx - rl, cy, cx - rl // 2, cy)
        # Right arm
        painter.drawLine(cx + rl // 2, cy, cx + rl, cy)
        # Center dot
        painter.setBrush(QBrush(QColor("#00bcd4")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(cx - 3, cy - 3, 6, 6)

        painter.end()


# ── Compass Rose Canvas ───────────────────────────────────────────────────────

class _CompassCanvas(QWidget):
    """Draws a compass rose with a rotating needle indicating yaw heading.

    Displays current heading in degrees at the center.
    Cardinal/intercardinal labels are shown at 0°/90°/180°/270°.
    """

    _CARDINALS = {0: "N", 90: "E", 180: "S", 270: "W"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._yaw = 0.0
        self.setFixedSize(90, 90)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_yaw(self, yaw: float):
        self._yaw = yaw % 360.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(cx, cy) - 4

        # ── Outer ring background ─────────────────────────────────────
        painter.setPen(QPen(QColor(COLOR_BORDER), 2))
        painter.setBrush(QBrush(QColor(COLOR_PANEL_DARK)))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # ── Tick marks every 45° ──────────────────────────────────────
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._yaw)   # rotate dial, needle stays up

        for angle_deg in range(0, 360, 45):
            rad = math.radians(angle_deg)
            is_cardinal = angle_deg % 90 == 0
            tick_inner = radius - (9 if is_cardinal else 5)
            tick_outer = radius - 1

            x1 = int(math.sin(rad) * tick_inner)
            y1 = int(-math.cos(rad) * tick_inner)
            x2 = int(math.sin(rad) * tick_outer)
            y2 = int(-math.cos(rad) * tick_outer)

            painter.setPen(QPen(QColor("#ffffff" if is_cardinal else "#607d8b"), 1))
            painter.drawLine(x1, y1, x2, y2)

            # Cardinal labels
            if is_cardinal:
                label = self._CARDINALS.get(angle_deg, "")
                lx = int(math.sin(rad) * (radius - 16))
                ly = int(-math.cos(rad) * (radius - 16))
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont(FONT_FAMILY, 6, QFont.Bold))
                painter.drawText(QRect(lx - 8, ly - 6, 16, 12), Qt.AlignCenter, label)

        painter.restore()

        # ── Heading needle (always points up) ─────────────────────────
        needle_len = radius - 14
        painter.setPen(Qt.NoPen)

        # North tip (up, red/accent)
        tip_pts = QPolygon([
            QPoint(cx, cy - needle_len),
            QPoint(cx - 4, cy),
            QPoint(cx + 4, cy),
        ])
        painter.setBrush(QBrush(QColor(COLOR_ACCENT)))
        painter.drawPolygon(tip_pts)

        # South tail (grey)
        tail_pts = QPolygon([
            QPoint(cx, cy + needle_len // 2),
            QPoint(cx - 3, cy),
            QPoint(cx + 3, cy),
        ])
        painter.setBrush(QBrush(QColor("#607d8b")))
        painter.drawPolygon(tail_pts)

        # Center pivot
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(cx - 3, cy - 3, 6, 6)

        # ── Degree readout in center ───────────────────────────────────
        painter.setPen(QPen(QColor("#00bcd4")))
        painter.setFont(QFont(FONT_FAMILY, 8, QFont.Bold))
        heading_txt = f"{int(self._yaw):03d}°"
        painter.drawText(QRect(cx - 20, cy + needle_len // 2 + 2, 40, 14),
                         Qt.AlignCenter, heading_txt)

        painter.end()


# ── Combined IMU Indicator Widget ─────────────────────────────────────────────

class IMUIndicatorWidget(QWidget):
    """Horizontal container: [Artificial Horizon] [Compass Rose].

    Layout::

        ┌───────────────────────────────────────┐
        │  [Horizon canvas]  [Compass canvas]   │
        │  P: 0.0°  R: 0.0°    HDG: 000°       │
        └───────────────────────────────────────┘

    Public slots
    ------------
    update_imu(pitch, roll, yaw)
        Call with fresh IMU values (degrees). Works with Qt signal/slot wiring.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)
        root.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        # ── Title ─────────────────────────────────────────────────────
        title = QLabel("ATTITUDE && HEADING")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont(FONT_FAMILY, 8, QFont.Bold))
        title.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        root.addWidget(title)

        # ── Two canvas widgets side by side ───────────────────────────
        canvas_row = QHBoxLayout()
        canvas_row.setSpacing(10)
        canvas_row.setAlignment(Qt.AlignCenter)

        self._horizon = _HorizonCanvas()
        self._compass = _CompassCanvas()
        canvas_row.addWidget(self._horizon)
        canvas_row.addWidget(self._compass)
        root.addLayout(canvas_row)

        # ── Numeric labels below canvases ─────────────────────────────
        label_row = QHBoxLayout()
        label_row.setSpacing(10)
        label_row.setAlignment(Qt.AlignCenter)

        self._lbl_pr = QLabel("P: 0.0°   R: 0.0°")
        self._lbl_pr.setFont(QFont(FONT_FAMILY, 8))
        self._lbl_pr.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        self._lbl_pr.setAlignment(Qt.AlignCenter)

        self._lbl_hdg = QLabel("HDG: 000°")
        self._lbl_hdg.setFont(QFont(FONT_FAMILY, 8))
        self._lbl_hdg.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        self._lbl_hdg.setAlignment(Qt.AlignCenter)

        label_row.addWidget(self._lbl_pr)
        label_row.addWidget(self._lbl_hdg)
        root.addLayout(label_row)

    # ── Public slot ───────────────────────────────────────────────────

    @pyqtSlot(float, float, float)
    def update_imu(self, pitch: float, roll: float, yaw: float):
        """Update both canvases with fresh IMU orientation data.

        Parameters
        ----------
        pitch : float  Nose-up positive (degrees)
        roll  : float  Right-wing-down positive (degrees)
        yaw   : float  Clockwise from north (degrees, 0–360)
        """
        self._horizon.set_attitude(pitch, roll)
        self._compass.set_yaw(yaw)
        self._lbl_pr.setText(f"P: {pitch:.1f}°   R: {roll:.1f}°")
        self._lbl_hdg.setText(f"HDG: {int(yaw % 360):03d}°")
