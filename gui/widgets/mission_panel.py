"""
MissionProgressPanel — compact mission step indicator for the ROV GCS.

Displays M1–M5 mission progress with:
- A row of indicator boxes (active mission highlighted in accent color)
- A large label showing the current mission name
- PREV / NEXT GUI buttons for manual navigation
- Responds to gamepad D-Pad UP/DOWN via the ``advance(delta)`` slot

Signals
-------
mission_changed : int
    Emitted whenever the active mission index changes (1-based, 1..MISSION_COUNT).
"""

from PyQt5.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout,
    QPushButton, QWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont

from utils.constants import (
    COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT,
    COLOR_TEXT, COLOR_TEXT_DIM,
    FONT_FAMILY,
    MISSION_LABELS, MISSION_COUNT,
)


class MissionProgressPanel(QFrame):
    """Compact mission step indicator — M1 through M5."""

    mission_changed = pyqtSignal(int)   # 1-based mission index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 1   # 1-based index
        self._setup_ui()
        self._refresh()

    # ── UI construction ───────────────────────────────────────────────

    def _setup_ui(self):
        self.setObjectName("missionFrame")
        self.setStyleSheet(f"""
            QFrame#missionFrame {{
                background-color: transparent;
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        # ── Title ─────────────────────────────────────────────────────
        title = QLabel("MISSION PROGRESS")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont(FONT_FAMILY, 8, QFont.Bold))
        title.setStyleSheet(f"color: {COLOR_TEXT_DIM}; border: none;")
        root.addWidget(title)

        # ── Indicator row (M1…M5 boxes) ───────────────────────────────
        indicator_row = QHBoxLayout()
        indicator_row.setSpacing(5)
        indicator_row.addStretch(1)

        self._indicators: list[QLabel] = []
        for label in MISSION_LABELS:
            box = QLabel(label)
            box.setFixedSize(34, 26)
            box.setAlignment(Qt.AlignCenter)
            box.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
            box.setStyleSheet(self._inactive_style())
            self._indicators.append(box)
            indicator_row.addWidget(box)

        indicator_row.addStretch(1)
        root.addLayout(indicator_row)

        # ── Active mission label ───────────────────────────────────────
        self._active_label = QLabel("MISSION 1")
        self._active_label.setAlignment(Qt.AlignCenter)
        self._active_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self._active_label.setStyleSheet(f"color: {COLOR_ACCENT}; border: none;")
        root.addWidget(self._active_label)

        # ── PREV / NEXT buttons ───────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._btn_prev = QPushButton("◀  PREV")
        self._btn_next = QPushButton("NEXT  ▶")
        for btn in (self._btn_prev, self._btn_next):
            btn.setFixedHeight(24)
            btn.setFont(QFont(FONT_FAMILY, 8, QFont.Bold))
            btn.setStyleSheet(self._btn_style())
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._btn_prev.clicked.connect(lambda: self.advance(-1))
        self._btn_next.clicked.connect(lambda: self.advance(+1))

        btn_row.addWidget(self._btn_prev)
        btn_row.addWidget(self._btn_next)
        root.addLayout(btn_row)

    # ── Styles ────────────────────────────────────────────────────────

    @staticmethod
    def _inactive_style() -> str:
        return (
            f"color: {COLOR_TEXT_DIM};"
            f"border: 1px solid {COLOR_BORDER};"
            "border-radius: 4px;"
            "background-color: transparent;"
        )

    @staticmethod
    def _active_style() -> str:
        return (
            "color: #ffffff;"
            f"background-color: {COLOR_ACCENT};"
            "border: none;"
            "border-radius: 4px;"
        )

    @staticmethod
    def _btn_style() -> str:
        return (
            f"QPushButton {{"
            f"  color: {COLOR_TEXT};"
            f"  background-color: #1a2a3a;"
            f"  border: 1px solid {COLOR_BORDER};"
            f"  border-radius: 4px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #0f3460;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {COLOR_ACCENT};"
            f"  color: #ffffff;"
            f"}}"
            f"QPushButton:disabled {{"
            f"  color: #3a4a5a;"
            f"  border-color: #1a2a3a;"
            f"}}"
        )

    # ── Internal refresh ──────────────────────────────────────────────

    def _refresh(self):
        """Redraw all indicator boxes and the active label."""
        for i, box in enumerate(self._indicators):
            if (i + 1) == self._current:
                box.setStyleSheet(self._active_style())
            else:
                box.setStyleSheet(self._inactive_style())

        self._active_label.setText(f"MISSION {self._current}")

        # Disable PREV on M1, NEXT on M5
        self._btn_prev.setEnabled(self._current > 1)
        self._btn_next.setEnabled(self._current < MISSION_COUNT)

    # ── Public API ────────────────────────────────────────────────────

    @pyqtSlot(int)
    def advance(self, delta: int):
        """Move mission index by +1 (next) or -1 (prev), clamped to [1, 5].

        Parameters
        ----------
        delta : int
            ``+1`` to advance to the next mission, ``-1`` to go back.
        """
        new = max(1, min(MISSION_COUNT, self._current + delta))
        if new != self._current:
            self._current = new
            self._refresh()
            self.mission_changed.emit(self._current)

    @property
    def current_mission(self) -> int:
        """Current active mission index (1-based)."""
        return self._current
