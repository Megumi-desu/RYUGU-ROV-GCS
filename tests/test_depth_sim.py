import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_right_stick_dummy_depth(qapp):
    window = MainWindow()
    assert window._simulated_depth == 0.0

    # Simulate right stick pushed DOWN (heave_norm < 0, axes heave < 0)
    # Right stick Y in pygame: DOWN gives positive axis value, which gets negated in deadzone_rescale -> heave_norm < 0
    # In axes dict passed from gamepad: heave = -1000 (full down)
    axes_down = {"surge": 0, "sway": 0, "heave": -1000, "yaw": 0}
    
    import time
    for _ in range(5):
        time.sleep(0.02)
        window.on_axes_updated(axes_down)

    assert window._simulated_depth > 0.0
    assert window.alt_panel.lbl_value.text() != "0.00 m"

    # Simulate right stick pushed UP (heave_norm > 0, axes heave > 0)
    axes_up = {"surge": 0, "sway": 0, "heave": 1000, "yaw": 0}
    current_depth = window._simulated_depth
    for _ in range(5):
        time.sleep(0.02)
        window.on_axes_updated(axes_up)

    assert window._simulated_depth < current_depth


def test_hybrid_surge_follows_map_heading(qapp):
    window = MainWindow()
    window._imu_yaw_deg = 30.0
    window.set_yaw_offset(90.0)
    window.traj_panel._mission_active = True

    start_x = window.traj_panel._rov_x
    start_y = window.traj_panel._rov_y
    window._update_hybrid_dr(1.0, 0.0, 0.0, 0.0, 1.0)

    assert window._map_heading_from_imu(30.0) == pytest.approx(90.0)
    assert window.traj_panel._rov_x == pytest.approx(start_x, abs=1e-6)
    assert window.traj_panel._rov_y > start_y
