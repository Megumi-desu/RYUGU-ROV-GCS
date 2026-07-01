import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QPixmap

from utils.constants import (
    COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT,
    COLOR_OK, COLOR_ERROR, COLOR_TEXT_DIM, COLOR_TEXT,
    FONT_FAMILY, ASSET_LOGO_TEAM
)

# Resolve logo path relative to project root (robust against CWD changes)
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LOGO_PATH = os.path.join(_BASE, ASSET_LOGO_TEAM)


class QRResultPanel(QFrame):
    """
    Displays QR code results + team logo + Emergency Stop button.
      - Side indicator: A / B / C / D
      - Validity: Valid / Invalid
      - Last scan timestamp
      - Raw decoded text
      - EMERGENCY STOP button
    """

    SIDES = ["A", "B", "C", "D"]

    emergency_stop = pyqtSignal()   # connected to MAVLink disarm in production

    def __init__(self, parent=None):
        super().__init__(parent)
        self._estop_active = False
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("qrFrame")
        self.setStyleSheet(f"""
            QFrame#qrFrame {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title = QLabel("  QR CODE & STATUS")
        title.setObjectName("panelTitle")
        title.setFixedHeight(26)
        layout.addWidget(title)

        # ── Content ───────────────────────────────────────────────────
        content = QFrame()
        content.setStyleSheet("QFrame { border: none; background-color: transparent; }")
        inner = QVBoxLayout(content)
        inner.setContentsMargins(10, 6, 10, 8)
        inner.setSpacing(5)

        # ── Team logo ─────────────────────────────────────────────────
        self._logo_lbl = QLabel()
        self._logo_lbl.setAlignment(Qt.AlignCenter)
        self._logo_lbl.setFixedHeight(130)
        self._logo_lbl.setStyleSheet("border: none;")
        self._load_team_logo()
        inner.addWidget(self._logo_lbl)

        # ── SIDE label + value ────────────────────────────────────────
        side_lbl = QLabel("SIDE")
        side_lbl.setObjectName("dimLabel")
        side_lbl.setAlignment(Qt.AlignCenter)
        inner.addWidget(side_lbl)

        self._side_value = QLabel("—")
        self._side_value.setAlignment(Qt.AlignCenter)
        self._side_value.setFont(QFont(FONT_FAMILY, 32, QFont.Bold))
        self._side_value.setStyleSheet(f"color: {COLOR_ACCENT}; border: none;")
        inner.addWidget(self._side_value)

        # ── Valid / Invalid ───────────────────────────────────────────
        self._status_label = QLabel("AWAITING SCAN")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        self._status_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; border: none;")
        inner.addWidget(self._status_label)

        # ── A / B / C / D indicator row ───────────────────────────────
        side_row = QHBoxLayout()
        side_row.setSpacing(8)
        self._side_indicators: dict[str, QLabel] = {}
        for s in self.SIDES:
            lbl = QLabel(s)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(50, 50)
            lbl.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
            lbl.setStyleSheet(
                f"color: {COLOR_TEXT_DIM}; border: 1px solid {COLOR_BORDER};"
                "border-radius: 6px;"
            )
            self._side_indicators[s] = lbl
            side_row.addWidget(lbl)
        inner.addLayout(side_row)

        inner.addSpacing(4)

        # ── Raw QR text ───────────────────────────────────────────────
        raw_lbl = QLabel("LAST RAW DATA")
        raw_lbl.setObjectName("dimLabel")
        inner.addWidget(raw_lbl)

        self._raw_text = QLabel("—")
        self._raw_text.setAlignment(Qt.AlignCenter)
        self._raw_text.setWordWrap(True)
        self._raw_text.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-family: Consolas; font-size: 10px; border: none;"
        )
        self._raw_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        inner.addWidget(self._raw_text)

        inner.addSpacing(4)

        # ── Scan log ──────────────────────────────────────────────────
        log_header = QLabel("SCAN LOG")
        log_header.setObjectName("dimLabel")
        inner.addWidget(log_header)

        log_frame = QFrame()
        log_frame.setStyleSheet(
            f"QFrame {{ background-color: #0d1b2a; border: 1px solid {COLOR_BORDER}; border-radius: 4px; }}"
        )
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(6, 4, 6, 4)
        log_layout.setSpacing(2)

        self._log_entries: list[str] = []
        self._log_labels: list[QLabel] = []
        for _ in range(5):
            entry_lbl = QLabel("—")
            entry_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_DIM}; font-family: Consolas; font-size: 9px; border: none;"
            )
            log_layout.addWidget(entry_lbl)
            self._log_labels.append(entry_lbl)

        inner.addWidget(log_frame)

        inner.addStretch()

        # ── Emergency Stop button (circular) ─────────────────────────
        self._estop_btn = QPushButton("EMERGENCY\nSTOP")
        self._estop_btn.setFixedSize(110, 110)
        self._estop_btn.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self._estop_btn.setStyleSheet(self._estop_style_idle())
        self._estop_btn.clicked.connect(self._on_estop_clicked)
        inner.addWidget(self._estop_btn, 0, Qt.AlignCenter)

        layout.addWidget(content)

    # ── Logo loader ───────────────────────────────────────────────────

    def _load_team_logo(self):
        pix = QPixmap(_LOGO_PATH)
        if not pix.isNull():
            self._logo_lbl.setPixmap(
                pix.scaledToHeight(124, Qt.SmoothTransformation)
            )
        else:
            # Fallback text if logo file missing
            self._logo_lbl.setText("RYUGU")
            self._logo_lbl.setFont(QFont(FONT_FAMILY, 22, QFont.Bold))
            self._logo_lbl.setStyleSheet(f"color: {COLOR_ACCENT}; border: none;")

    # ── E-STOP logic ──────────────────────────────────────────────────

    @staticmethod
    def _estop_style_idle() -> str:
        return (
            "QPushButton {"
            "  background-color: #7f0000;"
            "  color: #ffffff;"
            "  border: 3px solid #c62828;"
            "  border-radius: 55px;"
            "  letter-spacing: 1px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #c62828;"
            "  border-color: #ef5350;"
            "}"
            "QPushButton:pressed {"
            "  background-color: #b71c1c;"
            "}"
        )

    @staticmethod
    def _estop_style_active() -> str:
        return (
            "QPushButton {"
            "  background-color: #c62828;"
            "  color: #ffffff;"
            "  border: 3px solid #ff5252;"
            "  border-radius: 55px;"
            "  letter-spacing: 1px;"
            "}"
        )

    def _on_estop_clicked(self):
        if not self._estop_active:
            self._estop_active = True
            self._estop_btn.setText("■\nSTOPPED")
            self._estop_btn.setStyleSheet(self._estop_style_active())
            self.emergency_stop.emit()
        else:
            # Second click — disarm the E-STOP (reset)
            self._estop_active = False
            self._estop_btn.setText("EMERGENCY\nSTOP")
            self._estop_btn.setStyleSheet(self._estop_style_idle())

    # ── Public update slots ───────────────────────────────────────────

    @pyqtSlot(str, bool, str)
    def update_qr(self, side: str, valid: bool, raw: str):
        self._side_value.setText(side if side else "—")

        for s, lbl in self._side_indicators.items():
            if s == side:
                lbl.setStyleSheet(
                    f"color: #ffffff; background-color: {COLOR_ACCENT};"
                    "border-radius: 6px; border: none;"
                )
            else:
                lbl.setStyleSheet(
                    f"color: {COLOR_TEXT_DIM}; border: 1px solid {COLOR_BORDER};"
                    "border-radius: 6px;"
                )

        if valid:
            self._status_label.setText("VALID")
            self._status_label.setStyleSheet(
                f"color: {COLOR_OK}; font-size: 14px; font-weight: bold; border: none;"
            )
        else:
            self._status_label.setText("INVALID")
            self._status_label.setStyleSheet(
                f"color: {COLOR_ERROR}; font-size: 14px; font-weight: bold; border: none;"
            )

        now_str = datetime.now().strftime("%H:%M:%S")
        display_raw = raw[:38] + "…" if len(raw) > 38 else raw
        self._raw_text.setText(display_raw or "—")

        # Prepend new entry to log (max 5)
        status_str = "OK" if valid else "NG"
        color = COLOR_OK if valid else COLOR_ERROR
        entry_text = f"{now_str}  SIDE-{side}  {status_str}"
        self._log_entries.insert(0, (entry_text, color))
        if len(self._log_entries) > 5:
            self._log_entries.pop()

        for i, lbl in enumerate(self._log_labels):
            if i < len(self._log_entries):
                text, col = self._log_entries[i]
                lbl.setText(text)
                lbl.setStyleSheet(
                    f"color: {col}; font-family: Consolas; font-size: 9px; border: none;"
                )
            else:
                lbl.setText("—")
                lbl.setStyleSheet(
                    f"color: {COLOR_TEXT_DIM}; font-family: Consolas; font-size: 9px; border: none;"
                )

    def reset(self):
        self._side_value.setText("—")
        self._status_label.setText("AWAITING SCAN")
        self._status_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 14px; font-weight: bold; border: none;"
        )
        self._raw_text.setText("—")
        self._log_entries.clear()
        for lbl in self._log_labels:
            lbl.setText("—")
            lbl.setStyleSheet(
                f"color: {COLOR_TEXT_DIM}; font-family: Consolas; font-size: 9px; border: none;"
            )
        for lbl in self._side_indicators.values():
            lbl.setStyleSheet(
                f"color: {COLOR_TEXT_DIM}; border: 1px solid {COLOR_BORDER}; border-radius: 6px;"
            )
