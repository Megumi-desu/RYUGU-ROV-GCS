"""
Binary packet protocol for GCS ↔ Jetson Orin Nano communication.

Packet format:
    ┌──────┬──────┬──────┬────────────┬──────┐
    │ SYNC │ ID   │ LEN  │  PAYLOAD   │ CRC  │
    │ 2B   │ 1B   │ 2B   │ 0..1024B   │ 2B   │
    │0xAA55│      │ LE   │            │CRC16 │
    └──────┴──────┴──────┴────────────┴──────┘

- SYNC:    0xAA55 (little-endian → bytes 0x55, 0xAA)
- ID:      Packet type identifier (1 byte)
- LEN:     Payload length in bytes (little-endian u16)
- PAYLOAD: Packed with struct (little-endian)
- CRC:     CRC-16/CCITT over [ID, LEN, PAYLOAD]

This module is Qt-free and has no external dependencies beyond stdlib.
All struct formats use little-endian ('<') byte order.
"""

import struct
from typing import NamedTuple


# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

SYNC_WORD = 0xAA55
SYNC_BYTES = struct.pack("<H", SYNC_WORD)   # b'\x55\xAA'
HEADER_SIZE = 5     # SYNC(2) + ID(1) + LEN(2)
CRC_SIZE = 2
MAX_PAYLOAD = 1024

# ── Downlink packet IDs (ROV → GCS) ──────────────────────────────────────
TELEM_IMU    = 0x01
TELEM_DEPTH  = 0x02
TELEM_STATUS = 0x03
QR_RESULT    = 0x04
ACK          = 0xF0

# ── Uplink packet IDs (GCS → ROV) ────────────────────────────────────────
CMD_MOTION   = 0x81
CMD_MODE     = 0x82
CMD_GRIPPER  = 0x83
CMD_BALLAST  = 0x84
CMD_ARM      = 0x85
CMD_ESTOP    = 0x86

# Packet IDs that require ACK from the receiver
ACK_REQUIRED = {CMD_ARM, CMD_ESTOP, CMD_MODE}

# Mode ID mapping
MODE_IDS = {
    "MANUAL":     0,
    "STABILIZE":  1,
    "DEPTH HOLD": 2,
    "AUTONOMOUS": 3,
}
MODE_NAMES = {v: k for k, v in MODE_IDS.items()}

# QR zone mapping
QR_ZONES = {0: "A", 1: "B", 2: "C", 3: "D"}
QR_ZONE_IDS = {v: k for k, v in QR_ZONES.items()}


# ────────────────────────────────────────────────────────────────────────────
# CRC-16/CCITT (polynomial 0x1021, initial 0xFFFF)
# ────────────────────────────────────────────────────────────────────────────

_CRC_POLY = 0x1021
_CRC_INIT = 0xFFFF

# Pre-computed lookup table for speed
_crc_table: list[int] = []


def _build_crc_table():
    """Build CRC-16/CCITT lookup table (256 entries)."""
    for i in range(256):
        crc = i << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ _CRC_POLY
            else:
                crc <<= 1
            crc &= 0xFFFF
        _crc_table.append(crc)


_build_crc_table()


def crc16_ccitt(data: bytes, init: int = _CRC_INIT) -> int:
    """Compute CRC-16/CCITT over *data*.

    Parameters
    ----------
    data : bytes
        Input data to compute CRC over.
    init : int
        Initial CRC value (default 0xFFFF).

    Returns
    -------
    int
        16-bit CRC value.
    """
    crc = init
    for byte in data:
        idx = ((crc >> 8) ^ byte) & 0xFF
        crc = ((crc << 8) ^ _crc_table[idx]) & 0xFFFF
    return crc


# ────────────────────────────────────────────────────────────────────────────
# Parsed packet result
# ────────────────────────────────────────────────────────────────────────────

class Packet(NamedTuple):
    """Parsed packet."""
    packet_id: int
    payload: bytes


# ────────────────────────────────────────────────────────────────────────────
# Packet building
# ────────────────────────────────────────────────────────────────────────────

def build_packet(packet_id: int, payload: bytes = b"") -> bytes:
    """Build a complete binary packet ready for transmission.

    Parameters
    ----------
    packet_id : int
        Packet type ID (e.g., CMD_MOTION, TELEM_IMU).
    payload : bytes
        Packed payload data (may be empty for e.g. CMD_ESTOP).

    Returns
    -------
    bytes
        Complete packet: SYNC + ID + LEN + PAYLOAD + CRC.

    Raises
    ------
    ValueError
        If payload exceeds MAX_PAYLOAD bytes.
    """
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(
            f"Payload too large: {len(payload)} bytes (max {MAX_PAYLOAD})"
        )

    length = len(payload)
    id_len = struct.pack("<BH", packet_id, length)
    crc_data = id_len + payload
    crc = crc16_ccitt(crc_data)
    return SYNC_BYTES + crc_data + struct.pack("<H", crc)


# ────────────────────────────────────────────────────────────────────────────
# Packet parsing
# ────────────────────────────────────────────────────────────────────────────

def parse_packet(data: bytes) -> Packet | None:
    """Parse a single packet from raw bytes.

    Expects exactly one complete packet starting at byte 0.
    Validates sync word and CRC.

    Parameters
    ----------
    data : bytes
        Raw received data (must start with SYNC_BYTES).

    Returns
    -------
    Packet | None
        Parsed packet, or None if validation fails.
    """
    if len(data) < HEADER_SIZE + CRC_SIZE:
        return None

    # Verify sync word
    if data[:2] != SYNC_BYTES:
        return None

    packet_id = data[2]
    length = struct.unpack("<H", data[3:5])[0]

    total_len = HEADER_SIZE + length + CRC_SIZE
    if len(data) < total_len:
        return None

    payload = data[5:5 + length]
    received_crc = struct.unpack("<H", data[5 + length:5 + length + 2])[0]

    # Verify CRC over [ID, LEN, PAYLOAD]
    crc_data = data[2:5 + length]
    computed_crc = crc16_ccitt(crc_data)

    if received_crc != computed_crc:
        return None

    return Packet(packet_id=packet_id, payload=payload)


def find_packet(buffer: bytes) -> tuple[Packet | None, bytes]:
    """Find and parse the first valid packet in a byte buffer.

    Scans for the sync word, attempts to parse a packet, and returns
    the remaining buffer (bytes after the consumed packet).

    Parameters
    ----------
    buffer : bytes
        Accumulated receive buffer.

    Returns
    -------
    tuple[Packet | None, bytes]
        (parsed_packet_or_None, remaining_buffer)
    """
    while len(buffer) >= HEADER_SIZE + CRC_SIZE:
        # Find sync word
        idx = buffer.find(SYNC_BYTES)
        if idx < 0:
            # No sync found — discard all but last byte
            return None, buffer[-1:] if buffer else b""

        if idx > 0:
            # Discard bytes before sync
            buffer = buffer[idx:]

        if len(buffer) < HEADER_SIZE + CRC_SIZE:
            break

        # Read length
        length = struct.unpack("<H", buffer[3:5])[0]
        total_len = HEADER_SIZE + length + CRC_SIZE

        if length > MAX_PAYLOAD:
            # Corrupt length — skip this sync byte
            buffer = buffer[2:]
            continue

        if len(buffer) < total_len:
            # Incomplete packet — wait for more data
            break

        packet = parse_packet(buffer[:total_len])
        if packet is not None:
            return packet, buffer[total_len:]
        else:
            # CRC failed — skip this sync and search again
            buffer = buffer[2:]

    return None, buffer


# ────────────────────────────────────────────────────────────────────────────
# Payload builders (GCS → ROV uplink)
# ────────────────────────────────────────────────────────────────────────────

def build_motion_payload(surge: int, sway: int, heave: int,
                         yaw: int, pitch: int, roll: int) -> bytes:
    """Pack 6-DOF motion command.  All values: -1000..+1000 (int16)."""
    return struct.pack("<6h", surge, sway, heave, yaw, pitch, roll)


def build_mode_payload(mode: str) -> bytes:
    """Pack flight mode command."""
    mode_id = MODE_IDS.get(mode, 0)
    return struct.pack("<B", mode_id)


def build_gripper_payload(state: int) -> bytes:
    """Pack gripper command.  state: 0=stop, 1=open, 2=close."""
    return struct.pack("<B", state)


def build_ballast_payload(state: int) -> bytes:
    """Pack ballast command.  state: 0=stop, 1=fill, 2=drain."""
    return struct.pack("<B", state)


def build_arm_payload(arm: bool) -> bytes:
    """Pack arm/disarm command."""
    return struct.pack("<B", 1 if arm else 0)


def build_ack_payload(acked_id: int) -> bytes:
    """Pack acknowledgement for a received command."""
    return struct.pack("<B", acked_id)


# ────────────────────────────────────────────────────────────────────────────
# Payload parsers (ROV → GCS downlink)
# ────────────────────────────────────────────────────────────────────────────

def parse_imu(payload: bytes) -> tuple[float, float, float]:
    """Unpack IMU telemetry → (pitch, roll, yaw) in degrees."""
    return struct.unpack("<3f", payload)


def parse_depth(payload: bytes) -> tuple[float, float]:
    """Unpack depth telemetry → (depth_m, altitude_m)."""
    return struct.unpack("<2f", payload)


def parse_status(payload: bytes) -> dict:
    """Unpack status telemetry → dict with battery_v, arm_state, mode, thrusters."""
    fmt = "<fBB8B"
    values = struct.unpack(fmt, payload)
    return {
        "battery_v": values[0],
        "arm_state": bool(values[1]),
        "mode": MODE_NAMES.get(values[2], "MANUAL"),
        "thrusters": list(values[3:11]),
    }


def parse_qr(payload: bytes) -> tuple[int, str, bool, str]:
    """Unpack QR result → (camera_id, zone, valid, payload_string)."""
    camera_id, zone_id, valid, str_len = struct.unpack("<BBBB", payload[:4])
    qr_str = payload[4:4 + str_len].decode("ascii", errors="replace")
    return camera_id, QR_ZONES.get(zone_id, "?"), bool(valid), qr_str


def parse_ack(payload: bytes) -> int:
    """Unpack ACK → acked_packet_id."""
    return struct.unpack("<B", payload)[0]
