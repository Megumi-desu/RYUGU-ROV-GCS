"""
Unit tests for TelemetryBroadcaster — payload schema, state, online logic.

Run:
    python -m pytest tests/test_telemetry_broadcaster.py -v
"""

import json
import time

import pytest

# Adjust path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.telemetry_broadcaster import TelemetryBroadcaster


class TestBuildPayload:
    """Verify _build_payload() schema matches the PRD spec."""

    def test_schema_keys(self):
        b = TelemetryBroadcaster(
            supabase_url="https://example.co",
            anon_key="test",
        )
        payload = b._build_payload()

        # Top-level
        assert set(payload.keys()) == {"event", "timestamp", "status", "metrics"}

        # Status
        assert set(payload["status"].keys()) == {"online", "armed", "mode"}

        # Metrics
        assert set(payload["metrics"].keys()) == {
            "depth", "depth_raw", "altitude",
            "heading", "pitch", "roll", "yaw",
            "voltage", "temp_internal",
        }

    def test_schema_types(self):
        b = TelemetryBroadcaster(supabase_url="https://x.co", anon_key="k")
        p = b._build_payload()

        assert isinstance(p["event"], str)
        assert isinstance(p["timestamp"], float)
        assert isinstance(p["status"]["online"], bool)
        assert isinstance(p["status"]["armed"], bool)
        assert isinstance(p["status"]["mode"], str)
        assert isinstance(p["metrics"]["depth"], float)
        assert isinstance(p["metrics"]["voltage"], float)
        assert p["metrics"]["temp_internal"] is None

    def test_initial_state_offline(self):
        b = TelemetryBroadcaster(supabase_url="https://x.co", anon_key="k")
        p = b._build_payload()
        assert p["status"]["online"] is False
        assert p["status"]["armed"] is False
        assert p["status"]["mode"] == "MANUAL"
        assert p["metrics"]["depth"] == 0.0

    def test_online_after_data(self):
        b = TelemetryBroadcaster(supabase_url="https://x.co", anon_key="k")
        # Simulate jetson connected + data arrives
        b.on_connection(True)
        b.on_imu(5.0, 2.0, 180.0)
        p = b._build_payload()
        assert p["status"]["online"] is True
        assert p["metrics"]["pitch"] == 5.0
        assert p["metrics"]["roll"] == 2.0
        assert p["metrics"]["heading"] == 180.0

    def test_online_false_no_jetson(self):
        b = TelemetryBroadcaster(supabase_url="https://x.co", anon_key="k")
        # IMU data arrives but connection_changed never fired
        b.on_imu(1.0, 2.0, 3.0)
        p = b._build_payload()
        assert p["status"]["online"] is False  # _jetson_connected is still False

    def test_online_false_stale_data(self, monkeypatch):
        b = TelemetryBroadcaster(supabase_url="https://x.co", anon_key="k", timeout_s=3.0)
        b.on_connection(True)
        b.on_imu(1.0, 2.0, 3.0)

        # Advance time beyond timeout
        fake_now = time.monotonic() + 5.0
        monkeypatch.setattr(time, "monotonic", lambda: fake_now)

        p = b._build_payload()
        assert p["status"]["online"] is False

    def test_depth_simulated_mode(self):
        b = TelemetryBroadcaster(
            supabase_url="https://x.co", anon_key="k",
            use_simulated_depth=True,
        )
        b.on_depth(2.5, 1.0)
        b.on_simulated_depth(0.75)
        p = b._build_payload()
        assert p["metrics"]["depth"] == 0.75    # simulated
        assert p["metrics"]["depth_raw"] == 2.5
        assert p["metrics"]["altitude"] == 1.0

    def test_depth_raw_mode(self):
        b = TelemetryBroadcaster(
            supabase_url="https://x.co", anon_key="k",
            use_simulated_depth=False,
        )
        b.on_depth(2.5, 1.0)
        b.on_simulated_depth(0.75)
        p = b._build_payload()
        assert p["metrics"]["depth"] == 2.5  # raw, not simulated

    def test_status_update(self):
        b = TelemetryBroadcaster(supabase_url="https://x.co", anon_key="k")
        b.on_status({
            "battery_v": 14.8,
            "arm_state": True,
            "mode": "DEPTH HOLD",
            "thrusters": [80, 75, 90, 85, 70, 88, 92, 78],
        })
        p = b._build_payload()
        assert p["status"]["armed"] is True
        assert p["status"]["mode"] == "DEPTH HOLD"
        assert p["metrics"]["voltage"] == 14.8

    def test_json_serializable(self):
        """Payload must survive json.dumps (no NaN, Infinity, etc.)."""
        b = TelemetryBroadcaster(supabase_url="https://x.co", anon_key="k")
        b.on_connection(True)
        b.on_imu(0.0, 0.0, 0.0)
        p = b._build_payload()
        encoded = json.dumps(p)
        assert len(encoded) > 0
        roundtrip = json.loads(encoded)
        assert roundtrip["status"]["online"] is True
