from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont

from utils.constants import (
    COLOR_TEXT_DIM, COLOR_OK, COLOR_WARN, COLOR_ERROR, COLOR_NEUTRAL,
    FONT_FAMILY
)


def _make_led(name: str) -> QLabel:
    lbl = QLabel()
    lbl.setObjectName(name)
    lbl.setFixedSize(10, 10)
    return lbl


def _make_sep() -> QLabel:
    sep = QLabel("|")
    sep.setObjectName("footerSep")
    sep.setFixedWidth(12)
    sep.setAlignment(Qt.AlignCenter)
    sep.setStyleSheet(f"color: #0f3460; font-size: 16px;")
    return sep


class FooterStatusBar(QWidget):
    """
    Custom status bar: Mode | Connection | BATT | GAMEPAD | IMU | Logging
    Each section has a colored LED indicator + text label.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("footerBar")
        self.setFixedHeight(36)
        self.setStyleSheet(
            "QWidget#footerBar {"
            "  background-color: #0d1b2a;"
            "  border-top: 1px solid #0f3460;"
            "}"
            "QLabel { border: none; }"
        )
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        font = QFont(FONT_FAMILY, 10)

        def _item(led_name: str, text: str) -> tuple[QLabel, QLabel]:
            led = _make_led(led_name)
            lbl = QLabel(text)
            lbl.setObjectName("footerItem")
            lbl.setFont(font)
            lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; padding: 0 6px;")
            return led, lbl

        # Mode
        self._led_mode, self._lbl_mode = _item("ledNeutral", "MODE: MANUAL")
        # Connection
        self._led_conn, self._lbl_conn = _item("ledError", "CONNECTION: OFFLINE")
        # BATT (Battery)
        self._led_batt, self._lbl_batt = _item("ledNeutral", "BATT: OFFLINE")
        # GAMEPAD (Logitech F310)
        self._led_gamepad, self._lbl_gamepad = _item("ledNeutral", "GAMEPAD: OFFLINE")
        # IMU (Orientation)
        self._led_imu, self._lbl_imu = _item("ledNeutral", "IMU: OFFLINE")
        # Logging
        self._led_log,  self._lbl_log  = _item("ledNeutral", "LOG: IDLE")

        sections = [
            (self._led_mode, self._lbl_mode),
            (self._led_conn, self._lbl_conn),
            (self._led_batt, self._lbl_batt),
            (self._led_gamepad, self._lbl_gamepad),
            (self._led_imu, self._lbl_imu),
            (self._led_log,  self._lbl_log),
        ]
        for i, (led, lbl) in enumerate(sections):
            layout.addWidget(led)
            layout.addWidget(lbl)
            if i < len(sections) - 1:
                layout.addWidget(_make_sep())

        layout.addStretch()

    # ── Public update methods ─────────────────────────────────────────

    def set_mode(self, mode: str):
        """mode: 'MANUAL', 'STABILIZE', 'DEPTH HOLD', 'AUTONOMOUS', or 'E-STOP'"""
        self._lbl_mode.setText(f"MODE: {mode}")
        color_map = {
            "MANUAL":     COLOR_OK,       # green
            "STABILIZE":  "#2196F3",      # blue
            "DEPTH HOLD": "#00BCD4",      # cyan
            "AUTONOMOUS": COLOR_WARN,     # orange
            "E-STOP":     COLOR_ERROR,    # red
        }
        self._set_led(self._led_mode, color_map.get(mode, COLOR_NEUTRAL))

    def set_connection(self, connected: bool):
        self._lbl_conn.setText("CONNECTION: ONLINE" if connected else "CONNECTION: OFFLINE")
        self._set_led(self._led_conn, COLOR_OK if connected else COLOR_ERROR)


    def set_battery_status(self, ok: bool, detail: str = ""):
        """Update battery status indicator."""
        text = f"BATT: {detail}" if detail else ("BATT: OK" if ok else "BATT: OFFLINE")
        self._lbl_batt.setText(text)
        self._set_led(self._led_batt, COLOR_OK if ok else COLOR_ERROR)

    def set_gamepad_status(self, ok: bool, detail: str = ""):
        """Update gamepad connection indicator."""
        text = f"GAMEPAD: {detail}" if detail else ("GAMEPAD: OK" if ok else "GAMEPAD: OFFLINE")
        self._lbl_gamepad.setText(text)
        self._set_led(self._led_gamepad, COLOR_OK if ok else COLOR_ERROR)

    def set_imu_status(self, ok: bool, detail: str = ""):
        """Update IMU orientation sensor indicator."""
        text = f"IMU: {detail}" if detail else ("IMU: OK" if ok else "IMU: OFFLINE")
        self._lbl_imu.setText(text)
        self._set_led(self._led_imu, COLOR_OK if ok else COLOR_ERROR)

    def set_logging(self, active: bool):
        self._lbl_log.setText("LOG: RECORDING" if active else "LOG: IDLE")
        self._set_led(self._led_log, COLOR_OK if active else COLOR_NEUTRAL)

    @staticmethod
    def _set_led(led: QLabel, color: str):
        led.setStyleSheet(
            f"background-color: {color}; border-radius: 5px;"
            "min-width:10px; max-width:10px; min-height:10px; max-height:10px;"
        )
