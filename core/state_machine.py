"""
ROV mission state machine using the `transitions` library.
States mirror the 5 KKI 2026 missions + IDLE + AUTONOMOUS.
"""

from transitions import Machine


class ROVStateMachine:
    """
    States:
      IDLE       → before mission starts
      DIVING     → Mission 1: descend to floor
      SCANNING   → Mission 1: QR code scan
      GRIPPING   → Mission 2: gripper payload
      DOCKING    → Mission 3+4: payload to hook, surface docking
      AUTONOMOUS → Mission 5: autonomous payload release

    Transitions are intentionally linear for competition simplicity.
    """

    STATES = ["IDLE", "DIVING", "SCANNING", "GRIPPING", "DOCKING", "AUTONOMOUS"]

    def __init__(self):
        self.machine = Machine(
            model=self,
            states=self.STATES,
            initial="IDLE",
            auto_transitions=False,
        )

        self.machine.add_transition("start_dive",    "IDLE",       "DIVING")
        self.machine.add_transition("start_scan",    "DIVING",     "SCANNING")
        self.machine.add_transition("start_grip",    "SCANNING",   "GRIPPING")
        self.machine.add_transition("start_dock",    "GRIPPING",   "DOCKING")
        self.machine.add_transition("start_auto",    "DOCKING",    "AUTONOMOUS")
        self.machine.add_transition("reset",         "*",          "IDLE")

    @property
    def current_state(self) -> str:
        return self.state

    def is_autonomous(self) -> bool:
        return self.state == "AUTONOMOUS"
