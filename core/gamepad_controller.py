"""
Logitech F310 Gamepad Controller — XInput mode (switch on back set to X)

Reads Logitech F310 gamepad input and emits Qt signals for ROV control.
Runs in a separate QThread to avoid blocking the main GUI thread.

## F310 XInput axis/button indices (pygame)

    Axes:
      0 = Left Stick X  (-1.0 left  → +1.0 right)
      1 = Left Stick Y  (-1.0 up    → +1.0 down)   ← Y is inverted in pygame
      2 = Right Stick X (-1.0 left  → +1.0 right)
      3 = Right Stick Y (-1.0 up    → +1.0 down)
      4 = Left Trigger  (0.0 released → 1.0 full)
      5 = Right Trigger (0.0 released → 1.0 full)

    Buttons:
      0 = A, 1 = B, 2 = X, 3 = Y
      4 = LB, 5 = RB
      6 = Back, 7 = Start
      8 = Left Stick Click, 9 = Right Stick Click

    Hat (D-Pad): get_hat(0) → (x, y)
      (-1,0)=Left  (1,0)=Right  (0,1)=Up  (0,-1)=Down

## ROV control mapping (KKI 2026)

    ┌──────────────────────┬──────────────────┬──────────────────┐
    │ DOF / Action         │ Source           │ Output           │
    ├──────────────────────┼──────────────────┼──────────────────┤
    │ Surge (fwd/back)     │ Left Stick Y     │ ±1000            │
    │ Sway (strafe L/R)    │ Left Stick X     │ ±1000            │
    │ Heave (ascend/desc.) │ Right Stick Y    │ ±1000            │
    │ Yaw (rotate L/R)     │ Right Stick X    │ ±1000            │
    │ Pitch (tilt fwd/back)│ D-Pad UP / DOWN  │ ramp ±1000       │
    │ Roll (tilt L/R)      │ D-Pad LEFT/RIGHT │ ramp ±1000       │
    ├──────────────────────┼──────────────────┼──────────────────┤
    │ Mode: MANUAL         │ X  (Button 2)    │ mode_changed     │
    │ Mode: STABILIZE      │ Y  (Button 3)    │ mode_changed     │
    │ Mode: DEPTH HOLD     │ B  (Button 1)    │ mode_changed     │
    │ Mode: AUTONOMOUS     │ A  (Button 0)    │ mode_changed     │
    ├──────────────────────┼──────────────────┼──────────────────┤
    │ Gripper OPEN         │ LT (Axis 4)      │ button_event     │
    │ Gripper CLOSE        │ RT (Axis 5)      │ button_event     │
    │ Speed: SLOW (35%)    │ LB (Button 4)    │ button_event     │
    │ Speed: FAST (100%)   │ RB (Button 5)    │ button_event     │
    │ ARM                  │ Start (1.5s)     │ arm_event        │
    │ DISARM               │ Back  (1.5s)     │ arm_event        │
    └──────────────────────┴──────────────────┴──────────────────┘

## Deadzone
    Sticks:   ±0.12   (rescaled to full range after deadzone)
    Triggers:  0.08   (rescaled to [0, 1] after deadzone)

## D-Pad Ramp Accumulator
    Rate: 100 units/sec (configurable via DPAD_RAMP_RATE)
    Cap:  ±1000 (configurable via DPAD_MAX_VALUE)
    Resets to 0 on D-Pad release.
"""

import time
import pygame
from PyQt5.QtCore import QThread, pyqtSignal

from utils.constants import (
    DPAD_RAMP_RATE, DPAD_MAX_VALUE, TRIGGER_GRIP_THRESH,
    FLIGHT_MODES,
)


# ────────────────────────────────────────────────────────────────────────────
# Standalone helpers (unit-testable)
# ────────────────────────────────────────────────────────────────────────────


def deadzone_rescale(value: float, dz: float) -> float:
    """Apply deadzone then rescale so the output spans the full [-1, 1] range.

    Parameters
    ----------
    value : float
        Raw input in [-1, 1] (or [0, 1] for triggers).
    dz : float
        Deadzone threshold (positive). Values inside [-dz, +dz] snap to 0.

    Returns
    -------
    float
        Rescaled value in [-1, 1] (or [0, 1]), or 0 if inside deadzone.
    """
    if abs(value) <= dz:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) - dz) / (1.0 - dz)


def deadzone_rescale_trigger(value: float, dz: float) -> float:
    """Deadzone + rescale for trigger axes that range [0, 1]."""
    if value <= dz:
        return 0.0
    return (value - dz) / (1.0 - dz)


# ────────────────────────────────────────────────────────────────────────────
# Hold detection helper
# ────────────────────────────────────────────────────────────────────────────


class _HoldDetector:
    """Tracks whether a control has been held continuously for a duration.

    Call ``update(is_active)`` each poll frame.  Returns one of:
        "idle"      — not pressed
        "pressing"  — just started being pressed this frame
        "holding"   — pressed but not yet past the threshold
        "triggered" — held past threshold (fires once per press)
        "released"  — was pressed last frame, released this frame
    """

    def __init__(self, duration: float = 1.5):
        self._duration = duration
        self._start: float | None = None
        self._was_active = False
        self._fired = False

    def update(self, is_active: bool) -> str:
        now = time.monotonic()
        if is_active:
            if not self._was_active:
                # Just pressed
                self._start = now
                self._fired = False
                self._was_active = True
                return "pressing"
            # Still held
            if not self._fired and (now - self._start) >= self._duration:
                self._fired = True
                return "triggered"
            return "holding"
        # Not active
        if self._was_active:
            self._start = None
            self._was_active = False
            self._fired = False
            return "released"
        return "idle"

    def reset(self):
        self._start = None
        self._was_active = False
        self._fired = False


# ────────────────────────────────────────────────────────────────────────────
# D-Pad ramp accumulator
# ────────────────────────────────────────────────────────────────────────────


class _DPadAccumulator:
    """Ramps an internal value while a D-Pad direction is held.

    - Positive direction (UP or RIGHT) → value increases at ``rate`` per second
    - Negative direction (DOWN or LEFT) → value decreases at ``rate`` per second
    - Neutral (no D-Pad) → value resets to 0
    - Value is clamped to [-max_val, +max_val]
    """

    def __init__(self, rate: float = DPAD_RAMP_RATE,
                 max_val: float = DPAD_MAX_VALUE):
        self._rate = rate
        self._max_val = max_val
        self._value = 0.0
        self._last_time: float | None = None

    def update(self, direction: int) -> int:
        """Update accumulator.

        Parameters
        ----------
        direction : int
            +1 (positive D-Pad), -1 (negative D-Pad), or 0 (neutral).

        Returns
        -------
        int
            Current accumulated value, clamped and rounded.
        """
        now = time.monotonic()

        if direction == 0:
            # D-Pad released → reset to 0
            self._value = 0.0
            self._last_time = None
            return 0

        if self._last_time is None:
            # First frame of this hold
            self._last_time = now
            return int(round(self._value))

        dt = now - self._last_time
        self._last_time = now
        self._value += direction * self._rate * dt
        self._value = max(-self._max_val, min(self._max_val, self._value))
        return int(round(self._value))

    def reset(self):
        self._value = 0.0
        self._last_time = None


# ────────────────────────────────────────────────────────────────────────────
# Gamepad controller
# ────────────────────────────────────────────────────────────────────────────


class GamepadController(QThread):
    """Reads Logitech F310 (XInput mode) at 50 Hz and emits Qt signals.

    Signals
    -------
    axes_updated : dict[str, int]
        Keys: ``surge``, ``sway``, ``heave``, ``yaw``, ``pitch``, ``roll``.
        All values are ints in **-1000..+1000**.
    button_event : str, bool
        ``(action_name, is_pressed)``.
        Actions: ``gripper_open``, ``gripper_close``,
                 ``speed_slow``, ``speed_fast``.
    mode_changed : str
        One of: ``"MANUAL"``, ``"STABILIZE"``, ``"DEPTH HOLD"``,
        ``"AUTONOMOUS"`` — emitted on single button press.
    arm_event : bool
        ``True`` (ARM) or ``False`` (DISARM) — emitted after 1.5 s hold.
    position_delta : float, float
        ``(dx, dy)`` from left stick, normalized **-1.0..+1.0**
        (deadzone-filtered, Y inverted).
        Emitted in all modes except AUTONOMOUS.
    connection_lost
        Emitted when the gamepad is disconnected.
    connection_restored
        Emitted when the gamepad reconnects.
    """

    # ── Qt signals ─────────────────────────────────────────────────────────

    axes_updated = pyqtSignal(dict)
    button_event = pyqtSignal(str, bool)
    mode_changed = pyqtSignal(str)
    arm_event = pyqtSignal(bool)
    position_delta = pyqtSignal(float, float)
    connection_lost = pyqtSignal()
    connection_restored = pyqtSignal()

    # ── Constants ──────────────────────────────────────────────────────────

    POLL_INTERVAL_S = 0.02           # 50 Hz
    STICK_DEADZONE = 0.12
    TRIGGER_DEADZONE = 0.08
    HOLD_SECONDS = 1.5
    RECONNECT_INTERVAL_S = 2.0

    # ── Init ───────────────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self._running = False
        self._connected = False
        self._joystick: pygame.joystick.Joystick | None = None
        self._last_reconnect_attempt: float = 0.0

        self._current_mode = "MANUAL"
        self._prev_buttons: dict[int, bool] = {}
        self._prev_hat: tuple[int, int] = (0, 0)

        # Hold detectors for arm/disarm (Start / Back)
        self._hold_start = _HoldDetector(self.HOLD_SECONDS)
        self._hold_back = _HoldDetector(self.HOLD_SECONDS)

        # D-Pad ramp accumulators for pitch and roll
        self._pitch_accum = _DPadAccumulator()
        self._roll_accum = _DPadAccumulator()

        # Trigger-based gripper edge detection
        self._prev_lt_pressed = False
        self._prev_rt_pressed = False

        # Flag to fire connection_lost only once per disconnect
        self._disconnect_emitted = False

        pygame.init()
        pygame.joystick.init()

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        self._try_connect()

        while self._running:
            if not self._connected:
                self._try_reconnect()
                if not self._connected:
                    self._sleep(self.POLL_INTERVAL_S)
                    continue

            try:
                self._poll()
            except pygame.error:
                self._handle_disconnect()
            except Exception:
                self._handle_disconnect()

            self._sleep(self.POLL_INTERVAL_S)

    def stop(self):
        self._running = False
        self.quit()
        self.wait(2000)

    # ── Connection helpers ─────────────────────────────────────────────────

    def _try_connect(self):
        """Init first joystick if available."""
        pygame.event.pump()
        if pygame.joystick.get_count() == 0:
            self._connected = False
            if not self._disconnect_emitted:
                self.connection_lost.emit()
                self._disconnect_emitted = True
            return
        try:
            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            self._connected = True
            self._prev_buttons = {
                i: False for i in range(self._joystick.get_numbuttons())
            }
            self._disconnect_emitted = False
            self.connection_restored.emit()
        except pygame.error:
            self._connected = False
            if not self._disconnect_emitted:
                self.connection_lost.emit()
                self._disconnect_emitted = True

    def _try_reconnect(self):
        if time.monotonic() - self._last_reconnect_attempt < self.RECONNECT_INTERVAL_S:
            return
        self._last_reconnect_attempt = time.monotonic()
        pygame.joystick.quit()
        pygame.joystick.init()
        self._try_connect()

    def _handle_disconnect(self):
        self._connected = False
        self._joystick = None
        if not self._disconnect_emitted:
            self.connection_lost.emit()
            self._disconnect_emitted = True
        # Reset accumulators and hold detectors
        self._hold_start.reset()
        self._hold_back.reset()
        self._pitch_accum.reset()
        self._roll_accum.reset()
        self._prev_lt_pressed = False
        self._prev_rt_pressed = False

    # ── Polling ─────────────────────────────────────────────────────────────

    def _poll(self):
        pygame.event.pump()

        # Quick health check — if joystick vanished, bail
        if pygame.joystick.get_count() == 0:
            self._handle_disconnect()
            return

        # ── Read axes ──────────────────────────────────────────────────────
        lx = self._joystick.get_axis(0)   # Left Stick X
        ly = self._joystick.get_axis(1)   # Left Stick Y
        rx = self._joystick.get_axis(2)   # Right Stick X
        ry = self._joystick.get_axis(3)   # Right Stick Y
        lt = self._joystick.get_axis(4)   # Left Trigger
        rt = self._joystick.get_axis(5)   # Right Trigger

        # ── Apply deadzone + rescale for sticks ────────────────────────────
        surge_norm = deadzone_rescale(-ly, self.STICK_DEADZONE)   # invert Y
        sway_norm  = deadzone_rescale(lx, self.STICK_DEADZONE)
        heave_norm = deadzone_rescale(-ry, self.STICK_DEADZONE)   # invert Y, ascend = positive
        yaw_norm   = deadzone_rescale(rx, self.STICK_DEADZONE)

        # ── D-Pad → Pitch & Roll via ramp accumulator ─────────────────────
        hat = (
            self._joystick.get_hat(0)
            if self._joystick.get_numhats() > 0
            else (0, 0)
        )

        # Pitch: D-Pad UP (+1) = pitch forward, DOWN (-1) = pitch backward
        pitch_int = self._pitch_accum.update(hat[1])
        # Roll: D-Pad RIGHT (+1) = roll right, LEFT (-1) = roll left
        roll_int = self._roll_accum.update(hat[0])

        # ── Emit axes as ints (-1000 .. +1000) ─────────────────────────────
        axes = {
            "surge": self._to_thousand(surge_norm),
            "sway":  self._to_thousand(sway_norm),
            "heave": self._to_thousand(heave_norm),
            "yaw":   self._to_thousand(yaw_norm),
            "pitch": int(max(-DPAD_MAX_VALUE, min(DPAD_MAX_VALUE, pitch_int))),
            "roll":  int(max(-DPAD_MAX_VALUE, min(DPAD_MAX_VALUE, roll_int))),
        }
        self.axes_updated.emit(axes)

        # ── Position delta for trajectory (all modes except AUTONOMOUS) ───
        if self._current_mode != "AUTONOMOUS":
            dx = sway_norm
            dy = surge_norm   # surge_norm already inverts pygame's Y axis
            self.position_delta.emit(dx, dy)

        # ── Face buttons → Flight mode selection ──────────────────────────
        self._poll_mode_buttons()

        # ── Bumper buttons → Speed mode ────────────────────────────────────
        self._poll_bumper_buttons()

        # ── Triggers → Gripper (edge detection on analog axis) ────────────
        self._poll_trigger_gripper(lt, rt)

        # ── Hold detection: ARM (Start) / DISARM (Back) ───────────────────
        is_start = bool(self._joystick.get_button(7))
        is_back = bool(self._joystick.get_button(6))
        self._check_hold("arm", is_start, self._hold_start)
        self._check_hold("disarm", is_back, self._hold_back)

    # ── Flight mode buttons ────────────────────────────────────────────────

    # Button → mode mapping
    _MODE_BUTTONS: dict[int, str] = {
        2: "MANUAL",       # X
        3: "STABILIZE",    # Y
        1: "DEPTH HOLD",   # B
        0: "AUTONOMOUS",   # A
    }

    def _poll_mode_buttons(self):
        """Check face buttons for flight mode selection (single press)."""
        for btn_idx, mode in self._MODE_BUTTONS.items():
            pressed = bool(self._joystick.get_button(btn_idx))
            prev = self._prev_buttons.get(btn_idx, False)
            if pressed and not prev:
                # Rising edge → select this mode
                if self._current_mode != mode:
                    self._current_mode = mode
                    self.mode_changed.emit(mode)
            self._prev_buttons[btn_idx] = pressed

    # ── Bumper buttons (speed mode) ────────────────────────────────────────

    def _poll_bumper_buttons(self):
        """LB (4) = speed slow (35%), RB (5) = speed fast (100%)."""
        for btn_idx, action in ((4, "speed_slow"), (5, "speed_fast")):
            pressed = bool(self._joystick.get_button(btn_idx))
            prev = self._prev_buttons.get(btn_idx, False)
            if pressed and not prev:
                # Rising edge only — single press to switch speed mode
                self.button_event.emit(action, True)
            self._prev_buttons[btn_idx] = pressed

    # ── Trigger-based gripper ──────────────────────────────────────────────

    def _poll_trigger_gripper(self, lt_raw: float, rt_raw: float):
        """Treat analog triggers as digital gripper buttons (threshold)."""
        lt_pressed = lt_raw > TRIGGER_GRIP_THRESH
        rt_pressed = rt_raw > TRIGGER_GRIP_THRESH

        if lt_pressed != self._prev_lt_pressed:
            self._prev_lt_pressed = lt_pressed
            self.button_event.emit("gripper_open", lt_pressed)

        if rt_pressed != self._prev_rt_pressed:
            self._prev_rt_pressed = rt_pressed
            self.button_event.emit("gripper_close", rt_pressed)

    # ── Hold dispatch ──────────────────────────────────────────────────────

    def _check_hold(self, name: str, is_active: bool, detector: _HoldDetector):
        status = detector.update(is_active)
        if status == "triggered":
            if name == "arm":
                self.arm_event.emit(True)
            elif name == "disarm":
                self.arm_event.emit(False)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_thousand(norm: float) -> int:
        """Convert [-1.0, 1.0] to int in [-1000, 1000]."""
        return int(max(-1000, min(1000, round(norm * 1000))))

    @staticmethod
    def _sleep(seconds: float):
        time.sleep(seconds)
