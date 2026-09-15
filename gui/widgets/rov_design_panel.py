import math

from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, pyqtSlot
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QPixmap, QFont,
    QBrush, QPolygon
)

from utils.constants import (
    COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT,
    COLOR_TEXT_DIM, FONT_FAMILY,
    ASSET_ROV_IMG
)
from gui.widgets.mission_panel import MissionProgressPanel


class _ROVCanvas(QFrame):
    """
    Renders the ROV photo (ASSET_ROV_IMG) with X/Y/Z axis indicator overlay.
    Falls back to a schematic if the image file is not found.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(120)
        self.setStyleSheet("background: transparent; border: none;")
        self._load_image()
        self._pitch = 0.0
        self._roll = 0.0
        self._yaw = 0.0

    def _load_image(self):
        pix = QPixmap(ASSET_ROV_IMG)
        if not pix.isNull():
            self._pix = pix

    def set_orientation(self, pitch: float, roll: float, yaw: float):
        self._pitch = pitch
        self._roll = roll
        self._yaw = yaw
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self._pix:
            # Scale to fit, max 85% width, keep aspect ratio
            pad = 10
            max_w = int(w * 0.85)
            avail_w = w - pad * 2
            scaled = self._pix.scaled(
                min(avail_w, max_w), h - pad * 2 - 4,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (w - scaled.width()) // 2
            y = (h - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            self._draw_schematic(painter, w, h)

        self._draw_axes(painter, w, h)
        painter.end()

    def _draw_schematic(self, painter: QPainter, w: int, h: int):
        cx, cy = w // 2, h // 2
        bw, bh = min(w - 80, 180), min(h - 60, 90)

        from PyQt5.QtGui import QLinearGradient
        grad = QLinearGradient(cx - bw // 2, cy, cx + bw // 2, cy)
        grad.setColorAt(0.0, QColor("#1e3a5f"))
        grad.setColorAt(1.0, QColor("#0f2040"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(COLOR_BORDER), 2))
        painter.drawRoundedRect(cx - bw // 2, cy - bh // 2, bw, bh, 8, 8)

        t_size = 18
        offsets = [(-bw // 2 - 10, -bh // 2 + 4), (bw // 2 - 8, -bh // 2 + 4),
                   (-bw // 2 - 10,  bh // 2 - 22),  (bw // 2 - 8,  bh // 2 - 22)]
        painter.setBrush(QBrush(QColor("#0f3460")))
        for ox, oy in offsets:
            painter.drawEllipse(cx + ox, cy + oy, t_size, t_size)

        painter.setBrush(QBrush(QColor(COLOR_ACCENT)))
        painter.setPen(QPen(QColor(COLOR_ACCENT), 1))
        painter.drawEllipse(cx + bw // 2 - 4, cy - 8, 16, 16)

        painter.setPen(QColor(COLOR_TEXT_DIM))
        painter.setFont(QFont(FONT_FAMILY, 9))
        painter.drawText(QRect(0, cy + bh // 2 + 6, w, 18),
                         Qt.AlignCenter, "ROV — Top View (placeholder)")

    def _draw_axes(self, painter: QPainter, w: int, h: int):
        """
        Draw X/Y/Z axis in bottom-left corner as a 3D perspective cube-corner
        to match the 3D side-view of the ROV design image.
        Positioned with 20px margin from the image area.

        Convention (ArduSub body frame, perspective projected):
          X (red)  = forward  → upper-right
          Y (green)= lateral  → lower-right
          Z (blue) = up       → straight up
        """
        ox = int(w * 0.16)
        oy = h - int(h * 0.26)
        axis_length = 36.0
        arrow_size = 7
        pitch = math.radians(self._pitch)
        roll = math.radians(self._roll)
        yaw = math.radians(self._yaw)
        cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
        cos_roll, sin_roll = math.cos(roll), math.sin(roll)
        cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
        iso_pitch = math.radians(25)
        iso_yaw = math.radians(45)
        axes = {
            "X": (1.0, 0.0, 0.0, QColor(COLOR_ACCENT)),
            "Y": (0.0, 1.0, 0.0, QColor("#4caf50")),
            "Z": (0.0, 0.0, -1.0, QColor("#2196f3")),
        }

        for label, (body_x, body_y, body_z, color) in axes.items():
            rotated_x = body_x * cos_pitch + body_z * sin_pitch
            rotated_y = body_y
            rotated_z = -body_x * sin_pitch + body_z * cos_pitch
            rolled_x = rotated_x
            rolled_y = rotated_y * cos_roll - rotated_z * sin_roll
            rolled_z = rotated_y * sin_roll + rotated_z * cos_roll
            world_x = rolled_x * cos_yaw - rolled_y * sin_yaw
            world_y = rolled_x * sin_yaw + rolled_y * cos_yaw
            world_z = rolled_z
            dx = int((world_x * math.cos(iso_yaw) - world_y * math.sin(iso_yaw)) * axis_length)
            dy = int((-(world_x * math.sin(iso_yaw) + world_y * math.cos(iso_yaw)) * math.sin(iso_pitch) - world_z * math.cos(iso_pitch)) * axis_length)
            # Axis line
            pen = QPen(color, 2, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(ox, oy, ox + dx, oy + dy)

            # Arrowhead
            tip_x, tip_y = ox + dx, oy + dy
            norm = math.hypot(dx, dy)
            if norm > 3:
                ux, uy = dx / norm, dy / norm
                px, py = -uy, ux
                pts = QPolygon([
                    QPoint(int(tip_x), int(tip_y)),
                    QPoint(int(tip_x - ux*arrow_size + px*arrow_size//2),
                           int(tip_y - uy*arrow_size + py*arrow_size//2)),
                    QPoint(int(tip_x - ux*arrow_size - px*arrow_size//2),
                           int(tip_y - uy*arrow_size - py*arrow_size//2)),
                ])
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color, 1))
                painter.drawPolygon(pts)

            # Label — offset away from tip
            painter.setPen(QPen(color))
            painter.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
            lx = tip_x + (5 if dx >= 0 else -14)
            ly = tip_y + (14 if dy >= 0 else -2)
            painter.drawText(lx, ly, label)


class ROVDesignPanel(QFrame):
    """Displays ROV photo with axis indicator and mission progress panel."""

    # Forwarded from embedded MissionProgressPanel
    mission_changed = pyqtSignal(int)   # 1-based mission index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("rovFrame")
        self.setStyleSheet(f"""
            QFrame#rovFrame {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)

        title = QLabel("  ROV DESIGN")
        title.setObjectName("panelTitle")
        title.setFixedHeight(26)
        layout.addWidget(title)

        # ROV canvas — takes remaining vertical space
        self._canvas = _ROVCanvas()
        layout.addWidget(self._canvas, stretch=1)

        # Mission progress panel — compact strip at the bottom
        self._mission_panel = MissionProgressPanel()
        self._mission_panel.mission_changed.connect(self.mission_changed)
        layout.addWidget(self._mission_panel)

    # ── Public API ────────────────────────────────────────────────────

    @pyqtSlot(float, float, float)
    def update_imu(self, pitch: float, roll: float, yaw: float):
        self._canvas.set_orientation(pitch, roll, yaw)

    @pyqtSlot(int)
    def advance_mission(self, delta: int):
        """Forward D-Pad mission step to the embedded mission panel.

        Parameters
        ----------
        delta : int
            ``+1`` to advance, ``-1`` to go back.
        """
        self._mission_panel.advance(delta)

    @property
    def current_mission(self) -> int:
        """Current active mission index (1-based)."""
        return self._mission_panel.current_mission

    def update_state(self, state: str):
        """Compatibility method for legacy callers."""
        pass

