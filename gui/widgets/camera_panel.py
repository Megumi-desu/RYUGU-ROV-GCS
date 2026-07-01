import numpy as np
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPen

from utils.constants import (
    COLOR_PANEL, COLOR_BORDER, COLOR_TEXT_DIM,
    COLOR_OK, COLOR_WARN, COLOR_ERROR,
    FONT_FAMILY, FONT_SIZE_LARGE
)


class CameraPanel(QFrame):
    """Displays a single camera feed with a live/connecting status overlay.

    Accepts frames as either QImage (from CameraStreamWorker) or
    numpy.ndarray BGR (legacy compatibility).
    """

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._has_frame = False
        self._stream_connected = False
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("cameraFrame")
        self.setStyleSheet(f"""
            QFrame#cameraFrame {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        self._title = QLabel(f"  {self._label}")
        self._title.setObjectName("panelTitle")
        self._title.setFixedHeight(26)
        layout.addWidget(self._title)

        # Video display area
        self._feed = QLabel()
        self._feed.setObjectName("cameraFeed")
        self._feed.setAlignment(Qt.AlignCenter)
        self._feed.setMinimumSize(480, 270)
        self._feed.setSizePolicy(
            self._feed.sizePolicy().horizontalPolicy(),
            self._feed.sizePolicy().verticalPolicy()
        )
        self._draw_placeholder()
        layout.addWidget(self._feed)

        # Bottom info strip
        self._info = QLabel("  No Signal — waiting for stream")
        self._info.setObjectName("dimLabel")
        self._info.setFixedHeight(20)
        layout.addWidget(self._info)

        # Status indicator (overlaid on top-right of feed)
        self._status_dot = QLabel(self._feed)
        self._status_dot.setFixedSize(12, 12)
        self._status_dot.move(8, 8)
        self._set_status_indicator("disconnected")

    # ── Status indicator ──────────────────────────────────────────────

    def _set_status_indicator(self, state: str):
        """Update the overlay dot: 'live', 'connecting', 'disconnected'."""
        colors = {
            "live":         COLOR_OK,      # green
            "connecting":   COLOR_WARN,    # orange
            "disconnected": COLOR_ERROR,   # red
        }
        color = colors.get(state, COLOR_ERROR)
        self._status_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 6px;"
            " border: 1px solid rgba(255,255,255,80);"
        )
        self._status_dot.setToolTip(state.upper())

    # ── Placeholder ───────────────────────────────────────────────────

    def _draw_placeholder(self):
        """Render a 'no signal' placeholder with camera name."""
        w = max(self._feed.width(), 480)
        h = max(self._feed.height(), 270)
        img = QImage(w, h, QImage.Format_RGB888)
        img.fill(QColor("#0d1b2a"))

        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)

        # Diagonal stripes (subtle)
        pen = QPen(QColor("#0f2040"), 1)
        painter.setPen(pen)
        for i in range(0, w + h, 20):
            painter.drawLine(i, 0, 0, i)

        # Center text
        painter.setPen(QColor(COLOR_TEXT_DIM))
        painter.setFont(QFont(FONT_FAMILY, FONT_SIZE_LARGE, QFont.Bold))
        painter.drawText(img.rect(), Qt.AlignCenter, f"[ {self._label} ]\nNo Signal")

        painter.end()
        self._feed.setPixmap(QPixmap.fromImage(img))

    # ── Frame update (QImage — from CameraStreamWorker) ───────────────

    @pyqtSlot(QImage)
    def update_frame_qimage(self, qimg: QImage):
        """Display a QImage frame from the camera stream worker.

        Scales to fit the feed label while preserving aspect ratio.
        """
        if qimg.isNull():
            return

        pix = QPixmap.fromImage(qimg).scaled(
            self._feed.width(), self._feed.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._feed.setPixmap(pix)

        if not self._has_frame:
            self._has_frame = True
            self._info.setText(
                f"  {self._label}  —  {qimg.width()}×{qimg.height()}  LIVE"
            )
            self._set_status_indicator("live")

    # ── Frame update (ndarray — legacy compatibility) ─────────────────

    @pyqtSlot(np.ndarray)
    def update_frame(self, bgr_frame: np.ndarray):
        """Display an OpenCV BGR frame (legacy/direct numpy path).

        Called by threads that emit raw numpy arrays instead of QImage.
        """
        h, w, ch = bgr_frame.shape
        # Convert BGR → RGB for Qt
        rgb = bgr_frame[..., ::-1].copy()
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self._feed.width(), self._feed.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._feed.setPixmap(pix)
        if not self._has_frame:
            self._has_frame = True
            self._info.setText(f"  {self._label}  —  {w}×{h}  LIVE")
            self._set_status_indicator("live")

    # ── Connection status ─────────────────────────────────────────────

    @pyqtSlot(bool)
    def set_stream_status(self, connected: bool):
        """Update overlay and info text based on stream connection state."""
        self._stream_connected = connected
        if connected:
            self._set_status_indicator("live")
            # Info text will be updated on first frame
        else:
            self._has_frame = False
            self._set_status_indicator("connecting")
            self._info.setText(f"  {self._label}  —  CONNECTING...")
            self._draw_connecting_placeholder()

    def _draw_connecting_placeholder(self):
        """Render a 'connecting...' placeholder."""
        w = max(self._feed.width(), 480)
        h = max(self._feed.height(), 270)
        img = QImage(w, h, QImage.Format_RGB888)
        img.fill(QColor("#0d1b2a"))

        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)

        # Subtle crosshatch
        pen = QPen(QColor("#0f2040"), 1)
        painter.setPen(pen)
        for i in range(0, w + h, 30):
            painter.drawLine(i, 0, 0, i)
            painter.drawLine(w - i, 0, w, i)

        # Center text
        painter.setPen(QColor(COLOR_WARN))
        painter.setFont(QFont(FONT_FAMILY, FONT_SIZE_LARGE, QFont.Bold))
        painter.drawText(
            img.rect(), Qt.AlignCenter,
            f"[ {self._label} ]\nConnecting..."
        )

        painter.end()
        self._feed.setPixmap(QPixmap.fromImage(img))

    # ── Static image (demo mode) ──────────────────────────────────────

    def set_static_image(self, path: str):
        """Show a static image file (demo / proposal mode)."""
        self._static_path = path
        self._has_frame = True
        self._load_static()

    def _load_static(self):
        if not getattr(self, "_static_path", None):
            return
        pix = QPixmap(self._static_path)
        if pix.isNull():
            return
        w = max(self._feed.width(), 480)
        h = max(self._feed.height(), 270)
        self._feed.setPixmap(
            pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self._info.setText(f"  {self._label}  —  DEMO IMAGE")
        self._set_status_indicator("disconnected")

    # ── No signal reset ───────────────────────────────────────────────

    def set_no_signal(self):
        """Reset to placeholder when stream drops."""
        self._has_frame = False
        self._stream_connected = False
        self._static_path = ""
        self._draw_placeholder()
        self._info.setText("  No Signal — waiting for stream")
        self._set_status_indicator("disconnected")

    # ── Resize handling ───────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "_static_path", None):
            self._load_static()
        elif not self._has_frame:
            if self._stream_connected:
                self._draw_connecting_placeholder()
            else:
                self._draw_placeholder()
