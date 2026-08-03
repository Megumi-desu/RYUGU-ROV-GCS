"""
MJPEG Stream Server — serves ROV camera feeds to the web spectator.

Runs in a dedicated QThread.  Hosts a stdlib ThreadingHTTPServer on the
configured port (default 8080), serving:

    /cam1   — front camera   (multipart/x-mixed-replace MJPEG stream)
    /cam2   — bottom camera  (multipart/x-mixed-replace MJPEG stream)
    /       — JSON status    {cam1: bool, cam2: bool}

A daemon threading.Thread spawned inside run() grabs frames from both
cv2.VideoCapture sources at ~10 fps, encodes to JPEG, and stores the
latest frame.  HTTP handlers serve the most recent frame on demand —
one capture per camera, shared by all connected spectators.

Threading model:
  - GUI thread calls start() / stop().
  - The HTTP server runs on the QThread's event-loop thread.
  - The frame-grab thread is a plain daemon threading.Thread (no Qt deps).
  - stop() calls server.shutdown() from the GUI thread (the server socket
    is not bound to a specific thread, so this is safe).

Documented limitation:
  Video is LAN-only.  A Vercel-hosted HTTPS page cannot embed
  http://192.168.1.100:8080 (mixed-content blocking).  The web client
  shows a "NO VIDEO — LAN only" placeholder when the stream is
  unreachable.  For remote access, tunnel via cloudflared / ngrok.
"""

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
from PyQt5.QtCore import QThread

from utils.constants import (
    CAMERA_RECONNECT_S, MJPEG_FPS, MJPEG_JPEG_QUALITY,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_BOUNDARY = b"frame"


# ── HTTP Request Handler ─────────────────────────────────────────────────────

def _make_handler(latest: dict[str, bytes | None]):
    """Return a BaseHTTPRequestHandler subclass with access to the frame dict.

    Parameters
    ----------
    latest : dict[str, bytes | None]
        Per-endpoint latest JPEG frame bytes (``{"cam1": b"...", "cam2": b"..."}``).
        None means no frame received yet.
    """

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Suppress default stderr logging (use our logger at debug level)
            logger.debug("MJPEG %s", fmt % args)

        def _send_mjpeg(self, endpoint: str):
            """Stream MJPEG for the given endpoint."""
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={_BOUNDARY.decode()}")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            try:
                while True:
                    frame = latest.get(endpoint)
                    if frame is None:
                        # No frame yet — send a tiny black placeholder
                        placeholder = np.zeros((90, 160, 3), dtype=np.uint8)
                        _, jpg = cv2.imencode(".jpg", placeholder, [cv2.IMWRITE_JPEG_QUALITY, 30])
                        frame = jpg.tobytes()

                    self.wfile.write(b"--%b\r\n" % _BOUNDARY)
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(b"Content-Length: %d\r\n\r\n" % len(frame))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    time.sleep(1.0 / max(MJPEG_FPS, 1))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def _send_status(self):
            """Return JSON status of both cameras."""
            status = {
                ep: (latest.get(ep) is not None)
                for ep in ("cam1", "cam2")
            }
            body = json.dumps(status).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/cam1", "/cam2"):
                self._send_mjpeg(self.path.lstrip("/"))
            elif self.path == "/" or self.path == "/status":
                self._send_status()
            else:
                self.send_response(404)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

        def do_OPTIONS(self):
            # CORS preflight
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

    return _Handler


# ──────────────────────────────────────────────────────────────────────────────
# MJPEG Stream Server
# ──────────────────────────────────────────────────────────────────────────────

class MjpegStreamServer(QThread):
    """Serves MJPEG streams of both ROV cameras over HTTP.

    Parameters
    ----------
    urls : dict[str, str]
        Mapping ``{"cam1": url_front, "cam2": url_bottom}``.
    port : int
        HTTP server port (default 8080).
    fps : int
        Frame grab rate per camera (default 10).
    jpeg_quality : int
        JPEG compression quality 1–100 (default 70).
    """

    def __init__(self, urls: dict[str, str], port: int = 8080,
                 fps: int = MJPEG_FPS, jpeg_quality: int = MJPEG_JPEG_QUALITY,
                 parent=None):
        super().__init__(parent)
        self._urls = urls
        self._port = port
        self._fps = fps
        self._jpeg_quality = jpeg_quality
        self._running = False
        self._server: ThreadingHTTPServer | None = None

        # Thread-safe frame storage — bytes are atomic under the GIL
        self._latest: dict[str, bytes | None] = {
            ep: None for ep in urls
        }

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def run(self):
        self._running = True

        # Spawn the frame-grab thread (daemon — dies with the QThread)
        grabber = threading.Thread(target=self._grab_frames, daemon=True)
        grabber.start()

        # Start HTTP server (blocks until shutdown)
        handler_cls = _make_handler(self._latest)
        self._server = ThreadingHTTPServer(("0.0.0.0", self._port), handler_cls)
        self._server.daemon_threads = True
        logger.info(
            "MjpegStreamServer: serving on 0.0.0.0:%d  (cam1, cam2)",
            self._port,
        )

        # serve_forever blocks until shutdown() is called from another thread.
        # shutdown() is called by stop() on the GUI thread — this is safe
        # because shutdown() uses a flag that serve_forever checks each poll.
        try:
            self._server.serve_forever(poll_interval=0.2)
        except Exception:
            pass

        self._server.server_close()
        logger.info("MjpegStreamServer: stopped")

    def stop(self):
        """Request stop and wait up to 3 s."""
        self._running = False
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
        self.quit()
        self.wait(3000)

    # ── Frame grabber ────────────────────────────────────────────────────────

    def _grab_frames(self):
        """Open both camera streams and continuously grab/encode frames.

        Runs on a daemon threading.Thread.  Handles reconnection per
        the same pattern as CameraStreamWorker._open_stream.
        """
        caps: dict[str, cv2.VideoCapture | None] = {
            ep: None for ep in self._urls
        }
        interval = 1.0 / max(self._fps, 1)

        while self._running:
            for endpoint, url in self._urls.items():
                cap = caps[endpoint]

                # ── Open / reconnect if needed ───────────────────────────
                if cap is None:
                    cap = self._open_stream(url)
                    if cap is None:
                        self._latest[endpoint] = None
                        continue
                    caps[endpoint] = cap

                # ── Read frame ───────────────────────────────────────────
                ret, frame = cap.read()
                if not ret or frame is None:
                    logger.warning(
                        "MjpegStreamServer: %s frame read failed, reconnecting",
                        endpoint,
                    )
                    cap.release()
                    caps[endpoint] = None
                    self._latest[endpoint] = None
                    continue

                # ── Encode JPEG ──────────────────────────────────────────
                ok, jpg = cv2.imencode(
                    ".jpg", frame,
                    [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
                )
                if ok:
                    self._latest[endpoint] = jpg.tobytes()

            self._interruptible_sleep(interval)

        # Cleanup
        for cap in caps.values():
            if cap is not None:
                cap.release()

    @staticmethod
    def _open_stream(url: str) -> cv2.VideoCapture | None:
        """Try to open a video stream with low-latency settings.

        Same approach as CameraStreamWorker._open_stream.
        """
        if not url:
            return None
        try:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                return None

            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Test read to confirm connectivity
            ret, _ = cap.read()
            if not ret:
                cap.release()
                return None

            return cap
        except Exception:
            logger.exception("MjpegStreamServer: open failed for %s", url)
            return None

    def _interruptible_sleep(self, seconds: float):
        """Sleep in small increments so stop() takes effect promptly."""
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(0.1)
