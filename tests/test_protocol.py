"""
Unit tests for core.protocol — packet building, parsing, CRC-16/CCITT.

Run:
    python -m pytest tests/test_protocol.py -v
"""

import struct
import pytest

# Adjust path so we can import from project root
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.protocol import (
    crc16_ccitt,
    build_packet, parse_packet, find_packet,
    SYNC_BYTES, HEADER_SIZE, CRC_SIZE,
    TELEM_IMU, TELEM_DEPTH, TELEM_STATUS, QR_RESULT, ACK,
    CMD_MOTION, CMD_MODE, CMD_GRIPPER, CMD_BALLAST, CMD_ARM, CMD_ESTOP,
    build_motion_payload, build_mode_payload,
    build_gripper_payload, build_ballast_payload,
    build_arm_payload, build_ack_payload,
    parse_imu, parse_depth, parse_status, parse_qr, parse_ack,
    MODE_IDS, QR_ZONES,
)


# ────────────────────────────────────────────────────────────────────────────
# CRC-16/CCITT tests
# ────────────────────────────────────────────────────────────────────────────

class TestCRC16:
    """Verify CRC-16/CCITT implementation against known test vectors."""

    def test_empty(self):
        assert crc16_ccitt(b"") == 0xFFFF  # init value, no data

    def test_known_vector_123456789(self):
        # Standard CRC-16/CCITT test vector: "123456789" → 0x29B1
        result = crc16_ccitt(b"123456789")
        assert result == 0x29B1, f"Expected 0x29B1, got 0x{result:04X}"

    def test_single_byte(self):
        # Should produce a deterministic result
        result = crc16_ccitt(b"\x00")
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_different_data_different_crc(self):
        crc_a = crc16_ccitt(b"hello")
        crc_b = crc16_ccitt(b"world")
        assert crc_a != crc_b


# ────────────────────────────────────────────────────────────────────────────
# Packet building tests
# ────────────────────────────────────────────────────────────────────────────

class TestBuildPacket:
    def test_empty_payload(self):
        pkt = build_packet(CMD_ESTOP)
        # SYNC(2) + ID(1) + LEN(2) + CRC(2) = 7 bytes
        assert len(pkt) == 7
        assert pkt[:2] == SYNC_BYTES
        assert pkt[2] == CMD_ESTOP
        assert struct.unpack("<H", pkt[3:5])[0] == 0  # length = 0

    def test_motion_payload(self):
        payload = build_motion_payload(500, -300, 1000, -1000, 200, -200)
        pkt = build_packet(CMD_MOTION, payload)
        assert len(pkt) == 7 + 12  # 7 header/crc + 12 payload
        assert pkt[2] == CMD_MOTION
        assert struct.unpack("<H", pkt[3:5])[0] == 12

    def test_payload_too_large(self):
        with pytest.raises(ValueError, match="Payload too large"):
            build_packet(0x01, b"\x00" * 1025)


# ────────────────────────────────────────────────────────────────────────────
# Packet parsing tests
# ────────────────────────────────────────────────────────────────────────────

class TestParsePacket:
    def test_roundtrip_empty(self):
        pkt = build_packet(CMD_ESTOP)
        parsed = parse_packet(pkt)
        assert parsed is not None
        assert parsed.packet_id == CMD_ESTOP
        assert parsed.payload == b""

    def test_roundtrip_motion(self):
        payload = build_motion_payload(100, 200, 300, 400, 500, 600)
        pkt = build_packet(CMD_MOTION, payload)
        parsed = parse_packet(pkt)
        assert parsed is not None
        assert parsed.packet_id == CMD_MOTION
        values = struct.unpack("<6h", parsed.payload)
        assert values == (100, 200, 300, 400, 500, 600)

    def test_bad_sync(self):
        pkt = build_packet(CMD_ESTOP)
        bad = b"\x00\x00" + pkt[2:]
        assert parse_packet(bad) is None

    def test_bad_crc(self):
        pkt = bytearray(build_packet(CMD_ESTOP))
        pkt[-1] ^= 0xFF  # Corrupt CRC
        assert parse_packet(bytes(pkt)) is None

    def test_truncated(self):
        pkt = build_packet(CMD_ESTOP)
        assert parse_packet(pkt[:4]) is None  # Too short

    def test_extra_bytes_ignored(self):
        """parse_packet only looks at the first packet's worth of bytes."""
        pkt = build_packet(CMD_ESTOP)
        padded = pkt + b"\x00\x00\x00"
        parsed = parse_packet(padded)
        assert parsed is not None
        assert parsed.packet_id == CMD_ESTOP


# ────────────────────────────────────────────────────────────────────────────
# find_packet (streaming buffer parser) tests
# ────────────────────────────────────────────────────────────────────────────

class TestFindPacket:
    def test_single_packet(self):
        pkt = build_packet(CMD_ESTOP)
        parsed, remaining = find_packet(pkt)
        assert parsed is not None
        assert parsed.packet_id == CMD_ESTOP
        assert remaining == b""

    def test_garbage_before_packet(self):
        pkt = build_packet(CMD_ESTOP)
        buffer = b"\x01\x02\x03" + pkt
        parsed, remaining = find_packet(buffer)
        assert parsed is not None
        assert parsed.packet_id == CMD_ESTOP

    def test_two_packets(self):
        pkt1 = build_packet(CMD_ESTOP)
        payload = build_arm_payload(True)
        pkt2 = build_packet(CMD_ARM, payload)
        buffer = pkt1 + pkt2

        p1, remaining = find_packet(buffer)
        assert p1 is not None
        assert p1.packet_id == CMD_ESTOP

        p2, remaining = find_packet(remaining)
        assert p2 is not None
        assert p2.packet_id == CMD_ARM

    def test_incomplete_packet(self):
        pkt = build_packet(CMD_ESTOP)
        # Truncate last 2 bytes
        buffer = pkt[:-2]
        parsed, remaining = find_packet(buffer)
        assert parsed is None
        assert remaining == buffer  # Buffer preserved for next recv

    def test_empty_buffer(self):
        parsed, remaining = find_packet(b"")
        assert parsed is None
        assert remaining == b""


# ────────────────────────────────────────────────────────────────────────────
# Payload builder/parser roundtrip tests
# ────────────────────────────────────────────────────────────────────────────

class TestPayloadRoundtrip:
    def test_imu(self):
        payload = struct.pack("<3f", 15.5, -3.2, 270.0)
        pkt = build_packet(TELEM_IMU, payload)
        parsed = parse_packet(pkt)
        pitch, roll, yaw = parse_imu(parsed.payload)
        assert abs(pitch - 15.5) < 0.001
        assert abs(roll - (-3.2)) < 0.001
        assert abs(yaw - 270.0) < 0.001

    def test_depth(self):
        payload = struct.pack("<2f", 0.85, 0.65)
        pkt = build_packet(TELEM_DEPTH, payload)
        parsed = parse_packet(pkt)
        depth, alt = parse_depth(parsed.payload)
        assert abs(depth - 0.85) < 0.001
        assert abs(alt - 0.65) < 0.001

    def test_status(self):
        thrusters = [80, 75, 90, 85, 70, 88, 92, 78]
        payload = struct.pack("<fBB8B", 12.6, 1, 2, *thrusters)
        pkt = build_packet(TELEM_STATUS, payload)
        parsed = parse_packet(pkt)
        status = parse_status(parsed.payload)
        assert abs(status["battery_v"] - 12.6) < 0.01
        assert status["arm_state"] is True
        assert status["mode"] == "DEPTH HOLD"
        assert status["thrusters"] == thrusters

    def test_qr(self):
        camera_id = 0
        zone_id = 1  # B
        valid = 1
        qr_str = b"KKI2026-B-OK"
        payload = struct.pack("<BBBB", camera_id, zone_id, valid, len(qr_str)) + qr_str
        pkt = build_packet(QR_RESULT, payload)
        parsed = parse_packet(pkt)
        cam_id, zone, is_valid, text = parse_qr(parsed.payload)
        assert cam_id == 0
        assert zone == "B"
        assert is_valid is True
        assert text == "KKI2026-B-OK"

    def test_mode_roundtrip(self):
        for mode_name, mode_id in MODE_IDS.items():
            payload = build_mode_payload(mode_name)
            assert struct.unpack("<B", payload)[0] == mode_id

    def test_arm_roundtrip(self):
        payload_arm = build_arm_payload(True)
        assert struct.unpack("<B", payload_arm)[0] == 1
        payload_disarm = build_arm_payload(False)
        assert struct.unpack("<B", payload_disarm)[0] == 0

    def test_ack_roundtrip(self):
        payload = build_ack_payload(CMD_ARM)
        pkt = build_packet(ACK, payload)
        parsed = parse_packet(pkt)
        assert parse_ack(parsed.payload) == CMD_ARM
