"""
Centralized constants: colors, sizes, labels.
Change color values here to restyle the entire app.
"""

# ── Window ────────────────────────────────────────────────────────────────
WINDOW_TITLE   = "ROV GCS — Tim ROV Universitas Brawijaya | KKI 2026"
WINDOW_WIDTH   = 1920
WINDOW_HEIGHT  = 1080
WINDOW_MIN_W   = 1366
WINDOW_MIN_H   = 768

# ── Team Info ─────────────────────────────────────────────────────────────
TEAM_NAME       = "RYUGU"
UNIVERSITY_NAME = "Universitas Brawijaya"
COMPETITION     = "KKI 2026"

# ── Color Palette (dark maritime theme) ──────────────────────────────────
COLOR_BG         = "#1a1a2e"   # Main background
COLOR_PANEL      = "#16213e"   # Panel background
COLOR_PANEL_DARK = "#0d1b2a"   # Slightly darker panels
COLOR_BORDER     = "#0f3460"   # Panel border / accent blue
COLOR_ACCENT     = "#e94560"   # Red accent (ROV brand)
COLOR_TEXT       = "#eaeaea"   # Primary text
COLOR_TEXT_DIM   = "#7a8a99"   # Secondary / label text
COLOR_TEXT_TITLE = "#ffffff"   # Panel titles

COLOR_OK      = "#4caf50"   # Green — nominal
COLOR_WARN    = "#ff9800"   # Orange — warning
COLOR_ERROR   = "#f44336"   # Red — critical
COLOR_NEUTRAL = "#607d8b"   # Grey — unknown / disconnected

COLOR_CAM_BG_FRONT  = "#0d1b2a"  # Camera placeholder background
COLOR_CAM_BG_BOTTOM = "#0a1628"

# ── Font ──────────────────────────────────────────────────────────────────
FONT_FAMILY     = "Segoe UI"
FONT_MONO       = "Consolas"
FONT_SIZE_SMALL  = 9
FONT_SIZE_NORMAL = 11
FONT_SIZE_LARGE  = 14
FONT_SIZE_XL     = 20
FONT_SIZE_XXL    = 28

# ── Depth / Altitude ──────────────────────────────────────────────────────
POOL_DEPTH_MAX   = 1.5    # meters — gauge upper bound
DEPTH_WARN_M     = 0.70   # yellow zone starts
DEPTH_CRIT_M     = 0.85   # red zone starts

# ── Trajectory (pool) ─────────────────────────────────────────────────────
POOL_SIZE_X = 5.0   # meters
POOL_SIZE_Y = 5.0   # meters

# ── State Machine States ──────────────────────────────────────────────────
SM_STATES = ["IDLE", "DIVING", "SCANNING", "GRIPPING", "DOCKING", "AUTONOMOUS"]

# ── Mission Progress ──────────────────────────────────────────────────
MISSION_LABELS = ["M1", "M2", "M3", "M4", "M5"]
MISSION_COUNT  = 5

# ── Flight Modes ─────────────────────────────────────────────────────────
FLIGHT_MODES = ["MANUAL", "STABILIZE", "DEPTH HOLD", "AUTONOMOUS"]

# ── Gamepad Tuning ───────────────────────────────────────────────────────
DPAD_RAMP_RATE     = 100     # units per second (in -1000..+1000 scale)
DPAD_MAX_VALUE     = 1000    # accumulator cap
TRIGGER_GRIP_THRESH = 0.5    # trigger axis threshold for gripper activation

# ── Speed Modes (LB / RB) ───────────────────────────────────────────
SPEED_MULT_FAST = 1.0        # 100% thrust — normal operations
SPEED_MULT_SLOW = 0.35       # 35% thrust — precision / inspection

# ── Position Estimation Mode ─────────────────────────────────────────
# "GAMEPAD_ONLY"    — original open-loop dead reckoning (gamepad sticks only)
# "PIXHAWK_HYBRID"  — uses real IMU orientation + gamepad thrust for DR
POSITION_MODE = "PIXHAWK_HYBRID"

# ── Hybrid Dead Reckoning Tuning ─────────────────────────────────────
# Speed constants measured from physical pool trials (full stick = ±1000).
# All values in metres per second (m/s).
#
# ┌─────────┬──────────────────────────────┬─────────────────────────────────────┐
# │  Axis   │   3S Measured (11.1 V nom.)  │   4S Estimated (14.8 V nom., ×1.33) │
# ├─────────┼──────────────────────────────┼─────────────────────────────────────┤
# │  Surge  │  18 cm/s  →  0.180 m/s      │  ~0.240 m/s  (×14.8/11.1)          │
# │  Sway   │  2 m / 16.25 s → 0.123 m/s  │  ~0.164 m/s                         │
# │  Heave  │  1 m / 8.74 s  → 0.114 m/s  │  ~0.153 m/s                         │
# └─────────┴──────────────────────────────┴─────────────────────────────────────┘
#
# NOTE: 4S estimates assume terminal speed ∝ voltage (V_4S/V_3S ≈ 1.333).
# Actual 4S values MUST be verified with a real pool trial before competition.
#
# Change HYBRID_SPEED_* below to switch between 3S and 4S profiles.

# ── Active profile: 3S (measured) ────────────────────────────────────
HYBRID_SPEED_SURGE = 0.180   # m/s at ±1000 stick | 3S measured: 18.0 cm/s
HYBRID_SPEED_SWAY  = 0.123   # m/s at ±1000 stick | 3S measured: 2 m / 16.25 s = 12.3 cm/s
HYBRID_SPEED_HEAVE = 0.114   # m/s at ±1000 stick | 3S measured: 1 m / 8.74 s  = 11.4 cm/s

# ── Estimated 4S profile (uncomment to use) ──────────────────────────
# HYBRID_SPEED_SURGE = 0.240  # m/s | estimated 4S: 3S × (14.8/11.1)
# HYBRID_SPEED_SWAY  = 0.164  # m/s | estimated 4S: 3S × (14.8/11.1)
# HYBRID_SPEED_HEAVE = 0.153  # m/s | estimated 4S: 3S × (14.8/11.1)

# ── Network (GCS ↔ Jetson Orin Nano) ─────────────────────────────────────
GCS_IP      = "192.168.1.100"
JETSON_IP   = "192.168.1.10"
SUBNET_MASK = "255.255.255.0"
CMD_PORT    = 5001    # UDP — uplink commands (GCS → Jetson)
TELEM_PORT  = 5002    # UDP — downlink telemetry (Jetson → GCS)

# ── Camera Streams ───────────────────────────────────────────────────────
STREAM_URL_FRONT  = f"http://{JETSON_IP}:8555/video"
STREAM_URL_BOTTOM = f"http://{JETSON_IP}:8554/video"
CAMERA_RECONNECT_S = 1.5  # seconds between reconnection attempts

# ── Camera ID Mapping (matches camera_id in QR_RESULT 0x04 packet) ────────
# Which camera_id from Jetson corresponds to FRONT and BOTTOM.
# 0 = Front Cam, 1 = Bottom Cam (flip if Jetson camera indices are swapped)
CAM_ID_FRONT  = 0
CAM_ID_BOTTOM = 1

# ── MJPEG Spectator Server ─────────────────────────────────────────────
MJPEG_PORT         = 8080   # HTTP server for web spectator video streams
MJPEG_JPEG_QUALITY = 70     # JPEG compression quality (1-100)
MJPEG_FPS          = 10     # frame grab rate per camera

# ── Asset paths (relative to project root) ───────────────────────────────
ASSET_LOGO_UB    = "assets/logo_ub.png"
ASSET_LOGO_KKI   = "assets/logo_kki.png"
ASSET_LOGO_TEAM  = "assets/logo_team.png"
ASSET_ROV_IMG    = "assets/rov_design.png"
ASSET_FRONT_CAM  = "assets/front_cam.jpg"
ASSET_BOTTOM_CAM = "assets/bottom_cam.jpg"
