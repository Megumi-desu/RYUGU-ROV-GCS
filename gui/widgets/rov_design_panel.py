from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QPixmap, QFont,
    QBrush, QPolygon
)

from utils.constants import (
    COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT,
    COLOR_TEXT_DIM, FONT_FAMILY,
    ASSET_ROV_IMG
)


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

    def _load_image(self):
        pix = QPixmap(ASSET_ROV_IMG)
        if not pix.isNull():
            self._pix = pix

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
        ox  = int(w * 0.08)
        oy  = h - int(h * 0.18)
        L          = 34
        arrow_size = 7

        axes = [
            # X forward: projected upper-right at 30° above horizontal
            ("X",  int(L * 0.87), -int(L * 0.5),  QColor(COLOR_ACCENT)),
            # Y lateral: projected lower-right at 30° below horizontal
            ("Y",  int(L * 0.87),  int(L * 0.5),  QColor("#4caf50")),
            # Z up: straight up
            ("Z",  0,             -L,             QColor("#2196f3")),
        ]

        for label, dx, dy, color in axes:
            # Axis line
            pen = QPen(color, 2, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(ox, oy, ox + dx, oy + dy)

            # Arrowhead
            tip_x, tip_y = ox + dx, oy + dy
            norm = (dx**2 + dy**2) ** 0.5
            if norm > 0:
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
    """Displays ROV photo with axis indicator and mission state badge."""

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
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(0)

        title = QLabel("  ROV DESIGN")
        title.setObjectName("panelTitle")
        title.setFixedHeight(26)
        layout.addWidget(title)

        self._canvas = _ROVCanvas()
        layout.addWidget(self._canvas, stretch=1)

        self._state_badge = QLabel("STATE: IDLE")
        self._state_badge.setObjectName("stateBadge")
        self._state_badge.setAlignment(Qt.AlignCenter)
        self._state_badge.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; border: none;"
        )
        self._state_badge.setFont(QFont(FONT_FAMILY, 10))
        layout.addWidget(self._state_badge)

    def update_state(self, state: str):
        self._state_badge.setText(f"STATE: {state}")
