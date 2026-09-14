from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy, QProgressBar
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont

from utils.constants import (
    COLOR_PANEL, COLOR_BORDER,
    POOL_DEPTH_MAX, DEPTH_WARN_M, DEPTH_CRIT_M,
    FONT_FAMILY
)
from gui.widgets.imu_indicator import IMUIndicatorWidget



class AltitudePanel(QFrame):
    """Shows ROV altitude above pool floor from Bar30 sensor.

    Layout: vertical QProgressBar on left (52px), text labels stacked on right.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("altFrame")
        self.setStyleSheet(f"""
            QFrame#altFrame {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        # ── Center the content group (bar + labels) ─────────────────────
        root.addStretch(1)

        center = QHBoxLayout()
        center.setSpacing(12)

        # ── Vertical progress bar ───────────────────────────────────────
        self.depth_bar = QProgressBar()
        self.depth_bar.setOrientation(Qt.Vertical)
        self.depth_bar.setMinimumWidth(60)
        self.depth_bar.setMaximumWidth(60)
        self.depth_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.depth_bar.setRange(0, 150)
        self.depth_bar.setTextVisible(False)
        self.depth_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #2A4A6A;
                border-radius: 4px;
                background: #0D1B2A;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:1, x2:0, y2:0,
                    stop:0.00 #4CAF50,
                    stop:0.55 #FFC107,
                    stop:1.00 #F44336
                );
                border-radius: 3px;
            }
        """)
        center.addWidget(self.depth_bar)

        center.addSpacing(8)

        # ── MIDDLE: Depth text labels stacked, centered vertically ─────
        right_widget = QWidget()
        right_widget.setStyleSheet("border: none; background: transparent;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.setAlignment(Qt.AlignVCenter)

        self.lbl_value = QLabel("0.00 m")
        self.lbl_value.setFont(QFont(FONT_FAMILY, 20, QFont.Bold))
        self.lbl_value.setStyleSheet("color: #FFFFFF; border: none;")
        right_layout.addWidget(self.lbl_value)

        self.lbl_zone = QLabel("ZONE: SAFE")
        self.lbl_zone.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.lbl_zone.setStyleSheet("color: #4CAF50; border: none;")
        right_layout.addWidget(self.lbl_zone)

        self.lbl_warn = QLabel(f"WARN: {DEPTH_WARN_M:.2f}m")
        self.lbl_warn.setFont(QFont(FONT_FAMILY, 9))
        self.lbl_warn.setStyleSheet("color: #FF9800; border: none;")
        right_layout.addWidget(self.lbl_warn)

        self.lbl_crit = QLabel(f"CRIT: {DEPTH_CRIT_M:.2f}m")
        self.lbl_crit.setFont(QFont(FONT_FAMILY, 9))
        self.lbl_crit.setStyleSheet("color: #F44336; border: none;")
        right_layout.addWidget(self.lbl_crit)

        self.lbl_raw = QLabel("Bar30: — m")
        self.lbl_raw.setFont(QFont(FONT_FAMILY, 9))
        self.lbl_raw.setStyleSheet("color: #607D8B; border: none;")
        right_layout.addWidget(self.lbl_raw)

        center.addWidget(right_widget)

        center.addSpacing(12)

        # ── RIGHT: IMU Attitude + Heading indicator ────────────────────
        self.imu_indicator = IMUIndicatorWidget()
        center.addWidget(self.imu_indicator)

        root.addLayout(center)
        root.addStretch(1)


    @pyqtSlot(float)
    def update_depth(self, value: float) -> None:
        self.depth_bar.setValue(int(value * 100))
        self.lbl_value.setText(f"{value:.2f} m")
        self.lbl_raw.setText(f"Bar30: {value:.3f} m")

        if value < DEPTH_WARN_M:
            self.lbl_zone.setText("ZONE: SAFE")
            self.lbl_zone.setStyleSheet("color: #4CAF50; font-weight: bold; border: none;")
        elif value < DEPTH_CRIT_M:
            self.lbl_zone.setText("ZONE: WARN")
            self.lbl_zone.setStyleSheet("color: #FF9800; font-weight: bold; border: none;")
        else:
            self.lbl_zone.setText("ZONE: CRIT")
            self.lbl_zone.setStyleSheet("color: #F44336; font-weight: bold; border: none;")

    @pyqtSlot(float, float, float)
    def update_imu(self, pitch: float, roll: float, yaw: float) -> None:
        """Update attitude & heading indicator."""
        self.imu_indicator.update_imu(pitch, roll, yaw)
