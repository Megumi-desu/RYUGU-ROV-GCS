"""
Mock Jetson Orin Nano — UDP server for integration testing.

Simulates the Jetson-side ROS2 bridge node:
  - Sends telemetry packets (IMU, depth, status, QR) at 50 Hz on TELEM_PORT
  - Receives command packets on CMD_PORT
  - Sends ACK for critical commands (ARM, E-STOP, MODE)

Usage:
    python tests/mock_jetson.py [--gcs-ip 192.168.1.100]

This runs on the same machine as the GCS for testing. For real hardware,
this code would run on the Jetson Orin Nano.
"""

import argparse
import math
import socket
import struct
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.protocol import (
    build_packet, find_packet,
    TELEM_IMU, TELEM_DEPTH, TELEM_STATUS, QR_RESULT, ACK,
    CMD_MOTION, CMD_MODE, CMD_GRIPPER, CMD_BALLAST, CMD_ARM, CMD_ESTOP,
    ACK_REQUIRED,
    build_ack_payload,
    MODE_NAMES,
)
from utils.constants import GCS_IP, JETSON_IP, CMD_PORT, TELEM_PORT


def main():
    parser = argparse.ArgumentParser(description="Mock Jetson Orin Nano")
    parser.add_argument("--gcs-ip", default=GCS_IP,
                        help=f"GCS IP address (default: {GCS_IP})")
    parser.add_argument("--bind-ip", default="0.0.0.0",
                        help="IP to bind the command receiver to (default: 0.0.0.0)")
    parser.add_argument("--telem-rate", type=float, default=50.0,
                        help="Telemetry send rate in Hz (default: 50)")
    args = parser.parse_args()

    gcs_addr = (args.gcs_ip, TELEM_PORT)
    telem_interval = 1.0 / args.telem_rate

    # ── Create sockets ────────────────────────────────────────────────
    # Send telemetry to GCS
    telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Receive commands from GCS
    cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    cmd_sock.bind((args.bind_ip, CMD_PORT))
    cmd_sock.settimeout(0.001)  # Non-blocking-ish

    print(f"Mock Jetson started")
    print(f"  Sending telemetry → {gcs_addr} at {args.telem_rate} Hz")
    print(f"  Listening for commands on :{CMD_PORT}")
    print(f"  Press Ctrl+C to stop\n")

    # ── Simulated state ───────────────────────────────────────────────
    t = 0.0
    armed = False
    mode_id = 0  # MANUAL
    qr_timer = 0.0
    qr_idx = 0

    try:
        while True:
            loop_start = time.monotonic()

            # ── Generate telemetry ────────────────────────────────────
            # IMU: gentle oscillation
            pitch = 5.0 * math.sin(t * 0.5)
            roll = 3.0 * math.cos(t * 0.3)
            yaw = (t * 10.0) % 360.0

            imu_payload = struct.pack("<3f", pitch, roll, yaw)
            telem_sock.sendto(
                build_packet(TELEM_IMU, imu_payload), gcs_addr
            )

            # Depth: slow oscillation 0.3 – 0.8 m
            depth = 0.55 + 0.25 * math.sin(t * 0.4)
            altitude = 1.5 - depth
            depth_payload = struct.pack("<2f", depth, altitude)
            telem_sock.sendto(
                build_packet(TELEM_DEPTH, depth_payload), gcs_addr
            )

            # Status: battery slowly dropping
            battery = 12.6 - (t * 0.001)
            thrusters = [80, 75, 90, 85, 70, 88, 92, 78]
            status_payload = struct.pack(
                "<fBB8B", battery, int(armed), mode_id, *thrusters
            )
            telem_sock.sendto(
                build_packet(TELEM_STATUS, status_payload), gcs_addr
            )

            # QR: every 5 seconds
            qr_timer += telem_interval
            if qr_timer >= 5.0:
                qr_timer = 0.0
                zones = [b"A", b"B", b"C", b"D"]
                zone_id = qr_idx % 4
                valid = 1 if (qr_idx % 5 != 3) else 0
                qr_str = f"KKI2026-SIDE-{zones[zone_id].decode()}-{'OK' if valid else 'ERR'}-{qr_idx:04d}".encode()
                qr_payload = struct.pack("<BBB", zone_id, valid, len(qr_str)) + qr_str
                telem_sock.sendto(
                    build_packet(QR_RESULT, qr_payload), gcs_addr
                )
                qr_idx += 1

            # ── Receive commands ──────────────────────────────────────
            try:
                data, addr = cmd_sock.recvfrom(4096)
                recv_buf = data
                while recv_buf:
                    packet, recv_buf = find_packet(recv_buf)
                    if packet is None:
                        break

                    pid = packet.packet_id
                    _handle_command(pid, packet.payload, cmd_sock, addr)

                    # Update local state
                    if pid == CMD_ARM:
                        armed = bool(struct.unpack("<B", packet.payload)[0])
                        print(f"  {'ARMED' if armed else 'DISARMED'}")
                    elif pid == CMD_MODE:
                        mode_id = struct.unpack("<B", packet.payload)[0]
                        print(f"  Mode → {MODE_NAMES.get(mode_id, '?')}")
                    elif pid == CMD_ESTOP:
                        armed = False
                        print("  !! E-STOP !!")
                    elif pid == CMD_MOTION:
                        vals = struct.unpack("<6h", packet.payload)
                        # Print only when significant input
                        if any(abs(v) > 50 for v in vals):
                            print(
                                f"  Motion: S={vals[0]:+5d} Sw={vals[1]:+5d}"
                                f" H={vals[2]:+5d} Y={vals[3]:+5d}"
                                f" P={vals[4]:+5d} R={vals[5]:+5d}"
                            )
                    elif pid == CMD_GRIPPER:
                        state = struct.unpack("<B", packet.payload)[0]
                        names = {0: "STOP", 1: "OPEN", 2: "CLOSE"}
                        print(f"  Gripper → {names.get(state, '?')}")
                    elif pid == CMD_BALLAST:
                        state = struct.unpack("<B", packet.payload)[0]
                        names = {0: "STOP", 1: "FILL", 2: "DRAIN"}
                        print(f"  Ballast → {names.get(state, '?')}")

            except socket.timeout:
                pass

            t += telem_interval

            # ── Rate limit ────────────────────────────────────────────
            elapsed = time.monotonic() - loop_start
            sleep_time = telem_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nMock Jetson stopped.")
    finally:
        telem_sock.close()
        cmd_sock.close()


def _handle_command(packet_id: int, payload: bytes,
                    sock: socket.socket, addr: tuple):
    """Process a received command and send ACK if required."""
    if packet_id in ACK_REQUIRED:
        ack_pkt = build_packet(ACK, build_ack_payload(packet_id))
        sock.sendto(ack_pkt, addr)


if __name__ == "__main__":
    main()
