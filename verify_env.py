"""
Run this script FIRST after setting up your venv.
It checks all imports and opens a small test window.
Usage: python verify_env.py
"""

import sys

print("=" * 50)
print("ROV 2026 — Environment Verification")
print("=" * 50)

errors = []

def check(label, fn):
    try:
        fn()
        print(f"  [OK]  {label}")
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        errors.append(label)

check("Python >= 3.10", lambda: (
    None if sys.version_info >= (3, 10)
    else (_ for _ in ()).throw(RuntimeError(f"Got {sys.version}"))
))
check("PyQt5",        lambda: __import__("PyQt5.QtWidgets", fromlist=["QApplication"]))
check("pyqtgraph",    lambda: __import__("pyqtgraph"))
check("numpy",        lambda: __import__("numpy"))
check("cv2 (OpenCV)", lambda: __import__("cv2"))
check("pymavlink",    lambda: __import__("pymavlink"))
check("transitions",  lambda: __import__("transitions"))

try:
    check("pyzbar", lambda: __import__("pyzbar.pyzbar", fromlist=["decode"]))
except Exception:
    pass  # pyzbar needs zbar DLL; warn only

print()

if errors:
    print(f"[!] {len(errors)} dependency(s) missing: {', '.join(errors)}")
    print("    Run:  pip install -r requirements.txt")
    sys.exit(1)

print("[OK] All core dependencies found. Opening test window...")
print()

# ── Open a minimal PyQt5 window to verify display works ──────────────────
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass  # Non-Windows or already set

from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

app = QApplication(sys.argv)
app.setStyle("Fusion")

win = QWidget()
win.setWindowTitle("ROV 2026 — Env Verify")
win.setFixedSize(400, 200)
win.setStyleSheet("background-color: #1a1a2e; color: #eaeaea;")

layout = QVBoxLayout(win)
layout.setAlignment(Qt.AlignCenter)

title = QLabel("Environment OK")
title.setFont(QFont("Segoe UI", 18, QFont.Bold))
title.setAlignment(Qt.AlignCenter)
title.setStyleSheet("color: #4caf50;")

sub = QLabel("PyQt5 + all dependencies verified\nClose this window to finish.")
sub.setAlignment(Qt.AlignCenter)
sub.setStyleSheet("color: #aaaaaa; font-size: 12px;")

layout.addWidget(title)
layout.addWidget(sub)

win.show()
print("Test window opened. Close it to exit.")
sys.exit(app.exec_())
