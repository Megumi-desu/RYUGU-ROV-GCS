"""
Ethernet UDP worker for GCS ↔ Jetson Orin Nano communication.

Runs in a separate QThread.  Handles:
  - Receiving telemetry datagrams (downlink) from the Jetson on TELEM_PORT
  - Sending command packets (uplink) to the Jetson on CMD_PORT
  - Application-level ACK for critical commands (ARM, E-STOP, MODE)

Architecture:
  - The worker owns two UDP sockets:
      1. telem_sock: bound to GCS_IP:TELEM_PORT — receives telemetry
      2. cmd_sock:   sends commands to JETSON_IP:CMD_PORT
  - The main loop select()s on telem_sock for incoming data.
  - Outgoing commands are queued from the GUI thread via thread-safe methods
    and sent during the main loop iteration.

Threading model:
  - GUI thread calls send_*() methods → enqueues bytes into _cmd_queue
  - Worker thread dequeues and sends via cmd_sock
  - Parsed telemetry emitted as Qt signals (received by GUI thread)
"""

import socket
import struct
import time
import logging
from queue import Queue, Empty

from PyQt5.QtCore import QThread, pyqtSignal

from core.protocol import (
    build_packet, find_packet,
    TELEM_IMU, TELEM_DEPTH, TELEM_STATUS, QR_RESULT, ACK,
    CMD_MOTION, CMD_MODE, CMD_GRIPPER, CMD_BALLAST, CMD_ARM, CMD_ESTOP,
    ACK_REQUIRED,
    parse_imu, parse_depth, parse_status, parse_qr, parse_ack,
    build_motion_payload, build_mode_payload,
    build_gripper_payload, build_ballast_payload,
    build_arm_payload,
)
from utils.constants import (
    GCS_IP, JETSON_IP, CMD_PORT, TELEM_PORT,
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Pending ACK tracker
# ────────────────────────────────────────────────────────────────────────────

class _PendingAck:
    """Tracks a command that requires acknowledgement."""

    def __init__(self, packet_id: int, packet_data: bytes,
                 max_retries: int = 3, timeout_s: float = 0.1):
        self.packet_id = packet_id
        self.packet_data = packet_data
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        self.retries = 0
        self.sent_time = time.monotonic()

    @property
    def timed_out(self) -> bool:
        return (time.monotonic() - self.sent_time) >= self.timeout_s

    def retry(self) -> bool:
        """Increment retry counter and reset timer.  Returns False if exhausted."""
        self.retries += 1
        if self.retries > self.max_retries:
            return False
        self.sent_time = time.monotonic()
        return True


# ────────────────────────────────────────────────────────────────────────────
# Ethernet worker
# ────────────────────────────────────────────────────────────────────────────

class EthernetWorker(QThread):
    """UDP communication worker for GCS ↔ Jetson Orin Nano.

    Signals (downlink — ROV → GCS)
    --------------------------------
    imu_updated : float, float, float
        pitch, roll, yaw in degrees.
    depth_updated : float, float
        depth_m, altitude_m.
    status_updated : dict
        Keys: battery_v (float), arm_state (bool), mode (str),
        thrusters (list[int]).
    qr_detected : str, bool, str
        zone letter, is_valid, payload string.

    Signals (connection)
    ---------------------
    connection_changed : bool
        True when telemetry is being received, False on timeout.
    command_acked : int
        Packet ID of a successfully acknowledged command.
    command_timeout : int
        Packet ID of a command whose ACK retries were exhausted.
    """

    # ── Qt signals ─────────────────────────────────────────────────────────

    imu_updated = pyqtSignal(float, float, float)
    depth_updated = pyqtSignal(float, float)
    status_updated = pyqtSignal(dict)
    qr_detected = pyqtSignal(str, bool, str)

    connection_changed = pyqtSignal(bool)
    command_acked = pyqtSignal(int)
    command_timeout = pyqtSignal(int)

    # ── Constants ──────────────────────────────────────────────────────────

    RECV_TIMEOUT_S = 0.05       # select timeout per loop iteration
    CONNECTION_TIMEOUT_S = 3.0  # no telemetry → disconnected
    RECV_BUF_SIZE = 4096

    # ── Init ───────────────────────────────────────────────────────────────

    def __init__(self, gcs_ip: str = GCS_IP, jetson_ip: str = JETSON_IP,
                 telem_port: int = TELEM_PORT, cmd_port: int = CMD_PORT):
        super().__init__()
        self._gcs_ip = gcs_ip
        self._jetson_ip = jetson_ip
        self._telem_port = telem_port
        self._cmd_port = cmd_port

        self._running = False
        self._connected = False
        self._last_telem_time: float = 0.0

        # Thread-safe command queue (GUI thread → worker thread)
        self._cmd_queue: Queue[bytes] = Queue()

        # Pending ACKs keyed by packet_id
        self._pending_acks: dict[int, _PendingAck] = {}

        # Receive buffer for stream reassembly
        self._recv_buffer = b""

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def run(self):
        self._running = True

        # Create sockets
        self._telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._telem_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._telem_sock.settimeout(self.RECV_TIMEOUT_S)

        self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            self._telem_sock.bind((self._gcs_ip, self._telem_port))
            logger.info(
                "EthernetWorker: listening on %s:%d",
                self._gcs_ip, self._telem_port,
            )
        except OSError as e:
            logger.error("EthernetWorker: failed to bind — %s", e)
            # Try binding to any interface as fallback
            try:
                self._telem_sock.bind(("0.0.0.0", self._telem_port))
                logger.warning(
                    "EthernetWorker: bound to 0.0.0.0:%d (fallback)",
                    self._telem_port,
                )
            except OSError as e2:
                logger.error("EthernetWorker: bind fallback failed — %s", e2)
                self._running = False

        while self._running:
            # 1. Receive telemetry
            self._recv_telemetry()

            # 2. Send queued commands
            self._flush_cmd_queue()

            # 3. Check pending ACKs for timeouts
            self._check_ack_timeouts()

            # 4. Check connection status
            self._check_connection()

        # Cleanup
        self._telem_sock.close()
        self._cmd_sock.close()

    def stop(self):
        self._running = False
        self.quit()
        self.wait(2000)

    # ── Receive telemetry ──────────────────────────────────────────────────

    def _recv_telemetry(self):
        try:
            data, addr = self._telem_sock.recvfrom(self.RECV_BUF_SIZE)
        except socket.timeout:
            return
        except OSError:
            return

        self._last_telem_time = time.monotonic()
        self._recv_buffer += data

        # Parse all complete packets in the buffer
        while True:
            packet, self._recv_buffer = find_packet(self._recv_buffer)
            if packet is None:
                break
            self._dispatch_packet(packet.packet_id, packet.payload)

    def _dispatch_packet(self, packet_id: int, payload: bytes):
        """Route a parsed packet to the appropriate signal."""
        try:
            if packet_id == TELEM_IMU:
                pitch, roll, yaw = parse_imu(payload)
                self.imu_updated.emit(pitch, roll, yaw)

            elif packet_id == TELEM_DEPTH:
                depth, altitude = parse_depth(payload)
                self.depth_updated.emit(depth, altitude)

            elif packet_id == TELEM_STATUS:
                status = parse_status(payload)
                self.status_updated.emit(status)

            elif packet_id == QR_RESULT:
                zone, valid, text = parse_qr(payload)
                self.qr_detected.emit(zone, valid, text)

            elif packet_id == ACK:
                acked_id = parse_ack(payload)
                self._handle_ack(acked_id)

        except struct.error as e:
            logger.warning("Packet parse error (id=0x%02X): %s", packet_id, e)

    # ── ACK handling ───────────────────────────────────────────────────────

    def _handle_ack(self, acked_id: int):
        """Process an ACK received from the Jetson."""
        if acked_id in self._pending_acks:
            del self._pending_acks[acked_id]
            self.command_acked.emit(acked_id)
            logger.debug("ACK received for packet 0x%02X", acked_id)

    def _check_ack_timeouts(self):
        """Retry or fail commands whose ACKs have timed out."""
        expired = []
        for pid, pending in self._pending_acks.items():
            if pending.timed_out:
                if pending.retry():
                    # Resend
                    self._raw_send(pending.packet_data)
                    logger.debug(
                        "Retrying packet 0x%02X (attempt %d/%d)",
                        pid, pending.retries, pending.max_retries,
                    )
                else:
                    expired.append(pid)

        for pid in expired:
            del self._pending_acks[pid]
            self.command_timeout.emit(pid)
            logger.warning("ACK timeout for packet 0x%02X", pid)

    # ── Send commands ──────────────────────────────────────────────────────

    def _flush_cmd_queue(self):
        """Send all queued command packets."""
        while True:
            try:
                data = self._cmd_queue.get_nowait()
            except Empty:
                break
            self._raw_send(data)

    def _raw_send(self, data: bytes):
        """Send raw bytes to the Jetson via UDP."""
        try:
            self._cmd_sock.sendto(data, (self._jetson_ip, self._cmd_port))
        except OSError as e:
            logger.error("Send error: %s", e)

    def _enqueue_command(self, packet_id: int, payload: bytes = b""):
        """Build packet and enqueue for sending.  Thread-safe."""
        packet = build_packet(packet_id, payload)
        self._cmd_queue.put(packet)

        # Register ACK expectation for critical commands
        if packet_id in ACK_REQUIRED:
            self._pending_acks[packet_id] = _PendingAck(packet_id, packet)

    # ── Public API (called from GUI thread) ────────────────────────────────

    def send_motion(self, axes: dict):
        """Send 6-DOF motion command.

        Parameters
        ----------
        axes : dict
            Keys: surge, sway, heave, yaw, pitch, roll.
            Values: int in -1000..+1000.
        """
        payload = build_motion_payload(
            axes.get("surge", 0),
            axes.get("sway", 0),
            axes.get("heave", 0),
            axes.get("yaw", 0),
            axes.get("pitch", 0),
            axes.get("roll", 0),
        )
        self._enqueue_command(CMD_MOTION, payload)

    def send_mode(self, mode: str):
        """Send flight mode selection."""
        self._enqueue_command(CMD_MODE, build_mode_payload(mode))

    def send_gripper(self, state: int):
        """Send gripper command.  state: 0=stop, 1=open, 2=close."""
        self._enqueue_command(CMD_GRIPPER, build_gripper_payload(state))

    def send_ballast(self, state: int):
        """Send ballast pump command.  state: 0=stop, 1=fill, 2=drain."""
        self._enqueue_command(CMD_BALLAST, build_ballast_payload(state))

    def send_arm(self, arm: bool):
        """Send arm/disarm command.  Requires ACK."""
        self._enqueue_command(CMD_ARM, build_arm_payload(arm))

    def send_estop(self):
        """Send emergency stop.  Requires ACK."""
        self._enqueue_command(CMD_ESTOP)

    # ── Connection monitoring ──────────────────────────────────────────────

    def _check_connection(self):
        """Emit connection_changed if telemetry stream starts or stops."""
        now = time.monotonic()
        is_connected = (now - self._last_telem_time) < self.CONNECTION_TIMEOUT_S

        if is_connected != self._connected:
            self._connected = is_connected
            self.connection_changed.emit(is_connected)
