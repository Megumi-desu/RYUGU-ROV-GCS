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

# ── Flight Modes ─────────────────────────────────────────────────────────
FLIGHT_MODES = ["MANUAL", "STABILIZE", "DEPTH HOLD", "AUTONOMOUS"]

# ── Gamepad Tuning ───────────────────────────────────────────────────────
DPAD_RAMP_RATE     = 100     # units per second (in -1000..+1000 scale)
DPAD_MAX_VALUE     = 1000    # accumulator cap
TRIGGER_GRIP_THRESH = 0.5    # trigger axis threshold for gripper activation

# ── Network (GCS ↔ Jetson Orin Nano) ─────────────────────────────────────
GCS_IP      = "192.168.1.100"
JETSON_IP   = "192.168.1.10"
SUBNET_MASK = "255.255.255.0"
CMD_PORT    = 5001    # UDP — uplink commands (GCS → Jetson)
TELEM_PORT  = 5002    # UDP — downlink telemetry (Jetson → GCS)

# ── Camera Streams ───────────────────────────────────────────────────────
STREAM_URL_FRONT  = f"rtsp://{JETSON_IP}:8554/front"
STREAM_URL_BOTTOM = f"rtsp://{JETSON_IP}:8554/bottom"
CAMERA_RECONNECT_S = 1.5  # seconds between reconnection attempts

# ── Asset paths (relative to project root) ───────────────────────────────
ASSET_LOGO_UB    = "assets/logo_ub.png"
ASSET_LOGO_KKI   = "assets/logo_kki.png"
ASSET_LOGO_TEAM  = "assets/logo_team.png"
ASSET_ROV_IMG    = "assets/rov_design.png"
ASSET_FRONT_CAM  = "assets/front_cam.jpg"
ASSET_BOTTOM_CAM = "assets/bottom_cam.jpg"
