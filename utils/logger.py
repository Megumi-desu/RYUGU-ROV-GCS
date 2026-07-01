"""
Data logger — writes session telemetry to logs/session_YYYYMMDD_HHMMSS.csv

Columns: timestamp, type, data
Types: DEPTH, POSITION, QR, STATE, EVENT
"""

import os
import csv
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


class DataLogger:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = os.path.join(LOG_DIR, f"session_{ts}.csv")
        self._file   = open(self.filepath, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(["timestamp", "type", "data"])
        self._file.flush()
        print(f"[Logger] Logging to: {self.filepath}")

    # ── Slot-compatible methods (called via Qt signal or direct) ──────

    def log_depth(self, depth: float):
        self._write("DEPTH", f"{depth:.3f}")

    def log_position(self, x: float, y: float):
        self._write("POSITION", f"{x:.3f},{y:.3f}")

    def log_qr(self, side: str, valid: bool, raw: str):
        self._write("QR", f"{side},{valid},{raw}")

    def log_state(self, state: str):
        self._write("STATE", state)

    def log_event(self, msg: str):
        self._write("EVENT", msg)

    def _write(self, type_: str, data: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._writer.writerow([ts, type_, data])
        self._file.flush()

    def close(self):
        self.log_event("SESSION_END")
        self._file.close()
