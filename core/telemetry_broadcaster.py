"""
Telemetry Broadcaster — publishes GCS telemetry to Supabase Realtime Broadcast.

Runs in a dedicated QThread.  Taps *already-parsed* telemetry from the
EthernetWorker's Qt signals — does NOT duplicate UDP or protocol parsing.

Architecture:
  - The broadcaster owns an asyncio loop (hosted inside the QThread).
  - Telemetry slots (@pyqtSlot) update internal state as values arrive from
    the EthernetWorker.  These execute in the broadcaster's own thread via
    Qt's queued connection mechanism.
  - A timed loop publishes the latest state snapshot to Supabase Realtime
    Broadcast at the configured rate (default 5 Hz).

Supabase Realtime notes:
  - The sync client's Realtime is a stub; must use the async client.
  - The broadcaster calls ``asyncio.run(self._async_main())`` inside run().
  - Auto-reconnect is enabled by default on the async realtime client.

Threading model:
  - GUI thread calls start() / stop().
  - Qt signals from EthernetWorker (imu_updated, depth_updated, etc.)
    arrive via queued connections → slots execute in this worker's thread.
  - asyncio loop runs entirely within this QThread.

Fails open: if SUPABASE_URL is empty, logs a warning and no-ops.
"""

import asyncio
import logging
import os
import time

from PyQt5.QtCore import QThread, pyqtSlot

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_BROADCAST_HZ = 5.0
MIN_HZ = 1.0
MAX_HZ = 10.0
DATA_TIMEOUT_S = 3.0       # match EthernetWorker.CONNECTION_TIMEOUT_S
REALTIME_CHANNEL = "realtime"    # must match web-spectator channel name
REALTIME_EVENT = "telemetry"


# ── Helper ───────────────────────────────────────────────────────────────────

def _env_float(name: str, default: float) -> float:
    val = os.getenv(name, "").strip()
    if not val:
        return default
    try:
        return max(MIN_HZ, min(MAX_HZ, float(val)))
    except ValueError:
        logger.warning("%s=%s is not a valid float; using %s Hz", name, val, default)
        return default


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry Broadcaster
# ──────────────────────────────────────────────────────────────────────────────

class TelemetryBroadcaster(QThread):
    """Publishes GCS telemetry state to Supabase Realtime Broadcast.

    Slots (queued — execute in this worker's thread)
    ------------------------------------------------
    on_imu : float, float, float
        pitch, roll, yaw in degrees (from EthernetWorker.imu_updated).
    on_depth : float, float
        depth_m, altitude_m (from EthernetWorker.depth_updated).
    on_status : dict
        Keys: battery_v, arm_state, mode, thrusters (from status_updated).
    on_connection : bool
        Jetson UDP link status (from connection_changed).
    on_simulated_depth : float
        GCS-computed depth in metres (from MainWindow.simulated_depth_changed).
    on_speed_multiplier : float
        Current speed multiplier (from MainWindow).
    """

    def __init__(self, supabase_url: str = "", anon_key: str = "",
                 channel: str = REALTIME_CHANNEL,
                 event: str = REALTIME_EVENT,
                 hz: float = DEFAULT_BROADCAST_HZ,
                 timeout_s: float = DATA_TIMEOUT_S,
                 use_simulated_depth: bool = True,
                 parent=None):
        super().__init__(parent)
        self._url = supabase_url.strip()
        self._key = anon_key.strip()
        self._channel = channel
        self._event = event
        self._hz = max(MIN_HZ, min(MAX_HZ, hz))
        self._timeout_s = timeout_s
        self._use_simulated_depth = use_simulated_depth
        self._running = False

        # ── Telemetry state (updated by slots, read by publish loop) ────
        self._last_data_time: float = 0.0

        # IMU (degrees)
        self._pitch: float = 0.0
        self._roll: float = 0.0
        self._yaw: float = 0.0

        # Depth / altitude (metres, from real sensor)
        self._depth_raw: float = 0.0
        self._altitude: float = 0.0

        # Simulated depth (GCS-computed, from MainWindow)
        self._depth_sim: float = 0.0

        # Status
        self._armed: bool = False
        self._mode: str = "MANUAL"
        self._battery_v: float = 0.0

        # Connection (Jetson UDP link)
        self._jetson_connected: bool = False

        # Position (dead reckoning)
        self._pos_x: float = 0.0
        self._pos_y: float = 0.0
        self._pos_dist: float = 0.0

        # QR
        self._qr_side: str = ""
        self._qr_valid: bool = False
        self._qr_text: str = ""
        self._qr_logs: list[str] = []

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def run(self):
        """Start the broadcaster.  Called by QThread.start()."""
        self._running = True

        if not self._url:
            logger.warning(
                "TelemetryBroadcaster: SUPABASE_URL not set — "
                "broadcasting disabled.  Create a .env file or set the "
                "environment variable."
            )
            # No-op — run() returns immediately
            return

        if not self._key:
            logger.warning(
                "TelemetryBroadcaster: SUPABASE_ANON_KEY not set — "
                "broadcasting disabled."
            )
            return

        logger.info(
            "TelemetryBroadcaster: starting — %s @ %.0f Hz (channel=%r, event=%r)",
            self._url, self._hz, self._channel, self._event,
        )
        asyncio.run(self._async_main())

    def stop(self):
        """Request stop and wait up to 3 s for the asyncio loop to unwind."""
        self._running = False
        self.quit()
        self.wait(3000)

    # ── Async main loop ──────────────────────────────────────────────────────

    async def _async_main(self):
        """Create async Supabase client, subscribe, and publish in a loop."""
        try:
            from supabase import create_async_client
        except ImportError:
            logger.error(
                "TelemetryBroadcaster: supabase package not installed. "
                "Run: pip install supabase>=2.31.0"
            )
            return

        try:
            client = await create_async_client(self._url, self._key)
        except Exception:
            logger.exception("TelemetryBroadcaster: failed to create async client")
            return

        try:
            channel = client.realtime.channel(self._channel)
            await channel.subscribe()
            logger.info("TelemetryBroadcaster: subscribed to channel %r", self._channel)
        except Exception:
            logger.exception("TelemetryBroadcaster: failed to subscribe")
            await client.realtime.close()
            return

        interval = 1.0 / self._hz
        try:
            while self._running:
                loop_start = time.monotonic()
                try:
                    payload = self._build_payload()
                    await channel.send_broadcast(self._event, payload)
                except Exception:
                    logger.warning(
                        "TelemetryBroadcaster: send_broadcast failed "
                        "(auto-reconnect is enabled)"
                    )
                elapsed = time.monotonic() - loop_start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
        finally:
            try:
                await client.realtime.close()
            except Exception:
                pass
            logger.info("TelemetryBroadcaster: stopped")

    # ── Payload builder ──────────────────────────────────────────────────────

    def _build_payload(self) -> dict:
        """Build the JSON payload matching the expanded schema.

        Returns
        -------
        dict
            Keys: event, timestamp, status {online, armed, mode},
            metrics {depth, depth_raw, altitude, heading, pitch, roll,
                     yaw, voltage, pos_x, pos_y, pos_dist},
            qr {side, valid, text, logs}.
        """
        online = (
            self._jetson_connected
            and (time.monotonic() - self._last_data_time) < self._timeout_s
        )
        depth = self._depth_sim if self._use_simulated_depth else self._depth_raw

        return {
            "event": self._event,
            "timestamp": time.time(),
            "status": {
                "online": online,
                "armed": self._armed,
                "mode": self._mode,
            },
            "metrics": {
                "depth": depth,
                "depth_raw": self._depth_raw,
                "altitude": self._altitude,
                "heading": self._yaw,
                "pitch": self._pitch,
                "roll": self._roll,
                "yaw": self._yaw,
                "voltage": self._battery_v,
                "pos_x": self._pos_x,
                "pos_y": self._pos_y,
                "pos_dist": self._pos_dist,
            },
            "qr": {
                "side": self._qr_side,
                "valid": self._qr_valid,
                "text": self._qr_text,
                "logs": list(self._qr_logs),
            },
        }

    # ── Qt slots (queued — execute in this worker's thread) ──────────────────

    @pyqtSlot(float, float, float)
    def on_imu(self, pitch: float, roll: float, yaw: float):
        self._pitch = pitch
        self._roll = roll
        self._yaw = yaw
        self._last_data_time = time.monotonic()

    @pyqtSlot(float, float)
    def on_depth(self, depth_m: float, altitude_m: float):
        self._depth_raw = depth_m
        self._altitude = altitude_m
        self._last_data_time = time.monotonic()

    @pyqtSlot(dict)
    def on_status(self, status: dict):
        self._battery_v = status.get("battery_v", 0.0)
        self._armed = status.get("arm_state", False)
        self._mode = status.get("mode", "MANUAL")
        self._last_data_time = time.monotonic()

    @pyqtSlot(bool)
    def on_connection(self, connected: bool):
        self._jetson_connected = connected
        if connected:
            self._last_data_time = time.monotonic()

    @pyqtSlot(float)
    def on_simulated_depth(self, depth_m: float):
        self._depth_sim = depth_m

    @pyqtSlot(float, float, float)
    def on_position(self, x: float, y: float, dist: float):
        """Update position state from trajectory panel.

        Parameters
        ----------
        x : float
            World X position in metres.
        y : float
            World Y position in metres.
        dist : float
            Total distance travelled in metres.
        """
        self._pos_x = x
        self._pos_y = y
        self._pos_dist = dist

    @pyqtSlot(str, bool, str, list)
    def on_qr(self, side: str, valid: bool, text: str, logs: list):
        """Update QR state from QR panel.

        Parameters
        ----------
        side : str
            Detected QR side label (A, B, C, D).
        valid : bool
            Whether the QR was validated successfully.
        text : str
            Raw decoded QR text.
        logs : list of str
            Recent status log entries.
        """
        self._qr_side = side
        self._qr_valid = valid
        self._qr_text = text
        self._qr_logs = logs

