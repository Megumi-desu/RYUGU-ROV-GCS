"""
Gamepad Tester Utility

Simple utility to test the Logitech F310 gamepad controller in real-time.
Prints all input events to the console without requiring a full GUI.

Usage:
    python test_gamepad.py

Connect your Logitech F310 controller (XInput mode) before running.
Press Ctrl+C to exit.
"""

import sys
import time
from core.gamepad_controller import GamepadController
from PyQt5.QtWidgets import QApplication


def test_gamepad():
    """Test gamepad input with console output."""
    app = QApplication(sys.argv)

    print("=" * 70)
    print("LOGITECH F310 GAMEPAD TESTER (KKI 2026 Mapping)")
    print("=" * 70)
    print()

    gamepad = GamepadController()

    # ── Connect signals to test callbacks ──────────────────────────────

    def on_axes(axes: dict):
        line = (
            f"S={axes['surge']:+5d} Sw={axes['sway']:+5d} "
            f"H={axes['heave']:+5d} Y={axes['yaw']:+5d} "
            f"P={axes['pitch']:+5d} R={axes['roll']:+5d}"
        )
        # Only print when there's actual input
        if any(abs(v) > 50 for v in axes.values()):
            print(f"[AXES] {line}")

    def on_position(dx, dy):
        if abs(dx) > 0.05 or abs(dy) > 0.05:
            print(f"[POS DELTA] dx={dx:+5.2f}  dy={dy:+5.2f}")

    def on_mode(mode):
        print(f"[MODE] → {mode}")

    def on_button(action, pressed):
        state = "PRESSED" if pressed else "RELEASED"
        print(f"[BUTTON] {action:16s} {state}")

    def on_arm(armed):
        print(f"[ARM] {'ARMED' if armed else 'DISARMED'}")

    def on_disconnect():
        print("[CONN] ✗ Gamepad disconnected!")

    def on_reconnect():
        print("[CONN] ✓ Gamepad connected!")

    gamepad.axes_updated.connect(on_axes)
    gamepad.position_delta.connect(on_position)
    gamepad.mode_changed.connect(on_mode)
    gamepad.button_event.connect(on_button)
    gamepad.arm_event.connect(on_arm)
    gamepad.connection_lost.connect(on_disconnect)
    gamepad.connection_restored.connect(on_reconnect)

    print("[INFO] Starting gamepad thread...")
    gamepad.start()

    time.sleep(1)

    print()
    print("BUTTON MAPPING (KKI 2026):")
    print("─" * 70)
    print("Left Stick:   Surge (Y-axis) / Sway (X-axis)")
    print("Right Stick:  Heave (Y-axis) / Yaw (X-axis)")
    print("D-Pad:        UP/DOWN = Pitch ramp    LEFT/RIGHT = Roll ramp")
    print("Face Buttons: A = AUTONOMOUS    B = DEPTH HOLD")
    print("              X = MANUAL        Y = STABILIZE")
    print("Bumpers:      LB = Ballast Fill    RB = Ballast Drain")
    print("Triggers:     LT = Gripper Open    RT = Gripper Close")
    print("Start/Back:   Start (hold 1.5s) = ARM")
    print("              Back  (hold 1.5s) = DISARM")
    print("─" * 70)
    print()
    print("Testing... (Press Ctrl+C to exit)")
    print()

    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
        gamepad.stop()
        print("[INFO] Done.")


if __name__ == "__main__":
    test_gamepad()
