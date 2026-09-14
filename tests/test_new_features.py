"""
Unit tests for the three new features:
1. QR side parsing & noise filtering (_parse_qr_side)
2. MissionProgressPanel & D-Pad advance logic
3. IMUIndicatorWidget attitude & compass rendering logic
"""

import sys
import pytest
from PyQt5.QtWidgets import QApplication

# Ensure QApplication exists for GUI widget tests
app = QApplication.instance() or QApplication(sys.argv)

from gui.main_window import _parse_qr_side
from gui.widgets.mission_panel import MissionProgressPanel
from gui.widgets.imu_indicator import IMUIndicatorWidget
from gui.widgets.altitude_panel import AltitudePanel
from gui.widgets.rov_design_panel import ROVDesignPanel
from core.gamepad_controller import GamepadController


class TestQRFilter:
    """Test suite for PR 1: Smart QR Filter & Side parsing."""

    def test_single_letter_exact(self):
        assert _parse_qr_side("A") == "A"
        assert _parse_qr_side("B") == "B"
        assert _parse_qr_side("C") == "C"
        assert _parse_qr_side("D") == "D"

    def test_single_letter_lowercase(self):
        assert _parse_qr_side("a") == "A"
        assert _parse_qr_side("b") == "B"
        assert _parse_qr_side("c") == "C"
        assert _parse_qr_side("d") == "D"

    def test_sisi_prefix(self):
        assert _parse_qr_side("SISI A") == "A"
        assert _parse_qr_side("SISI-A") == "A"
        assert _parse_qr_side("sisi a") == "A"
        assert _parse_qr_side("sisi-b") == "B"
        assert _parse_qr_side("SISI_C") == "C"
        assert _parse_qr_side("SISI:D") == "D"

    def test_side_prefix(self):
        assert _parse_qr_side("SIDE A") == "A"
        assert _parse_qr_side("SIDE-A") == "A"
        assert _parse_qr_side("side a") == "A"
        assert _parse_qr_side("side-b") == "B"
        assert _parse_qr_side("SIDE_C") == "C"
        assert _parse_qr_side("SIDE:D") == "D"

    def test_clahe_garbage_noise_returns_none(self):
        """Noise from CLAHE fallback must return None to be passed."""
        assert _parse_qr_side("84") is None
        assert _parse_qr_side("3221") is None
        assert _parse_qr_side("") is None
        assert _parse_qr_side("   ") is None
        assert _parse_qr_side(None) is None
        assert _parse_qr_side("1234567890") is None
        assert _parse_qr_side("NO_MATCH_HERE") is None


class TestMissionPanel:
    """Test suite for PR 2: Mission Progress Panel (M1-M5)."""

    def test_initial_mission(self):
        panel = MissionProgressPanel()
        assert panel.current_mission == 1
        assert panel._active_label.text() == "MISSION 1"
        assert panel._btn_prev.isEnabled() is False
        assert panel._btn_next.isEnabled() is True

    def test_advance_next_and_clamping(self):
        panel = MissionProgressPanel()
        emitted_values = []
        panel.mission_changed.connect(emitted_values.append)

        # Advance 1 -> 2
        panel.advance(1)
        assert panel.current_mission == 2
        assert panel._active_label.text() == "MISSION 2"
        assert panel._btn_prev.isEnabled() is True
        assert panel._btn_next.isEnabled() is True

        # Advance to M5
        panel.advance(1)  # 3
        panel.advance(1)  # 4
        panel.advance(1)  # 5
        assert panel.current_mission == 5
        assert panel._active_label.text() == "MISSION 5"
        assert panel._btn_next.isEnabled() is False

        # Attempt advance past 5 -> clamped at 5
        panel.advance(1)
        assert panel.current_mission == 5

        # Check emitted signals
        assert emitted_values == [2, 3, 4, 5]

    def test_advance_prev_and_clamping(self):
        panel = MissionProgressPanel()
        panel.advance(1)  # 2
        panel.advance(1)  # 3
        panel.advance(-1) # 2
        assert panel.current_mission == 2
        panel.advance(-1) # 1
        assert panel.current_mission == 1
        # Attempt prev past 1 -> clamped at 1
        panel.advance(-1)
        assert panel.current_mission == 1

    def test_rov_design_panel_embedding(self):
        rov = ROVDesignPanel()
        assert hasattr(rov, "advance_mission")
        assert hasattr(rov, "current_mission")
        assert rov.current_mission == 1

        signals = []
        rov.mission_changed.connect(signals.append)
        rov.advance_mission(1)
        assert rov.current_mission == 2
        assert signals == [2]


class TestIMUIndicator:
    """Test suite for PR 3: IMU Attitude & Heading Indicator."""

    def test_imu_indicator_widget(self):
        widget = IMUIndicatorWidget()
        widget.update_imu(15.5, -10.2, 85.0)

        assert widget._horizon._pitch == 15.5
        assert widget._horizon._roll == -10.2
        assert widget._compass._yaw == 85.0
        assert "15.5°" in widget._lbl_pr.text()
        assert "-10.2°" in widget._lbl_pr.text()
        assert "085°" in widget._lbl_hdg.text()

    def test_altitude_panel_has_imu(self):
        alt = AltitudePanel()
        assert hasattr(alt, "imu_indicator")
        assert hasattr(alt, "update_imu")
        alt.update_imu(5.0, 3.0, 180.0)
        assert alt.imu_indicator._compass._yaw == 180.0
