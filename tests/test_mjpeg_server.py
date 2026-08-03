"""
Unit tests for MjpegStreamServer — status endpoint and frame injection.

Run:
    python -m pytest tests/test_mjpeg_server.py -v
"""

import json
import time
import urllib.request

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.mjpeg_server import MjpegStreamServer


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_fake_jpeg() -> bytes:
    import numpy as np
    import cv2
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    frame[:, :] = (0, 0, 255)  # BGR red
    ok, jpg = cv2.imencode(".jpg", frame)
    return jpg.tobytes()


# ── Tests ────────────────────────────────────────────────────────────────────

class TestMjpegServer:
    """Verify the MJPEG HTTP server endpoints."""

    def test_status_endpoint(self):
        """The / endpoint returns JSON camera status."""
        port = _find_free_port()
        server = MjpegStreamServer(
            urls={"cam1": "", "cam2": ""},
            port=port,
        )
        server.start()
        time.sleep(0.5)  # let server bind

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert set(data.keys()) == {"cam1", "cam2"}
        finally:
            server.stop()

    def test_cam_endpoint_content_type(self):
        """cam1 returns multipart/x-mixed-replace with correct headers."""
        port = _find_free_port()
        server = MjpegStreamServer(
            urls={"cam1": "", "cam2": ""},
            port=port,
        )

        # Inject a fake JPEG frame before starting
        fake = _make_fake_jpeg()
        server._latest["cam1"] = fake

        server.start()
        time.sleep(0.5)

        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/cam1", timeout=2)
            content_type = resp.headers.get("Content-Type", "")
            assert "multipart/x-mixed-replace" in content_type

            # Read enough for at least one frame
            chunk = resp.read(4096)
            assert b"Content-Type: image/jpeg" in chunk
            assert b"Content-Length:" in chunk
            # Close the connection (the server loop sends frames forever otherwise)
            resp.close()
        finally:
            server.stop()

    def test_port_freed_after_stop(self):
        """After stop(), the port should be available again."""
        port = _find_free_port()
        server = MjpegStreamServer(
            urls={"cam1": "", "cam2": ""},
            port=port,
        )
        server.start()
        time.sleep(0.3)
        server.stop()
        time.sleep(0.2)

        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
        except OSError:
            pytest.fail(f"Port {port} still in use after stop()")

    def test_cors_headers(self):
        """All responses include Access-Control-Allow-Origin: *."""
        port = _find_free_port()
        server = MjpegStreamServer(urls={"cam1": ""}, port=port)
        server.start()
        time.sleep(0.3)

        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/")
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        finally:
            server.stop()
