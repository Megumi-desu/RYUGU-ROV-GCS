"""
Camera Stream Worker — RTSP / HTTP MJPEG video reader in a QThread.

Reads a network video stream (RTSP or HTTP/MJPEG) from the Jetson Orin Nano
using OpenCV and emits QImage frames via a Qt Signal for the GUI to display.

One instance per camera feed.  Handles graceful reconnection if the stream
is unavailable or temporarily interrupted.

Low-latency tuning:
    - cv2.CAP_PROP_BUFFERSIZE = 1 (minimize decode-to-display lag)
    - RTSP forced to TCP transport via OPENCV_FFMPEG_CAPTURE_OPTIONS env var
    - Frame dropped if the previous one hasn't been consumed yet (optional)
"""

import os
import time
import logging

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

from utils.constants import CAMERA_RECONNECT_S

logger = logging.getLogger(__name__)

# Force RTSP over TCP globally for ffmpeg backend (avoids UDP fragmentation).
# Must be set before any cv2.VideoCapture() call.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"
)


class CameraStreamWorker(QThread):
    """Reads a video stream and emits QImage frames at capture rate.

    Parameters
    ----------
    stream_url : str
        RTSP URL (e.g. ``rtsp://192.168.1.10:8554/front``) or
        HTTP MJPEG URL (e.g. ``http://192.168.1.10:8080/video``).
    label : str
        Human-readable name for logging (e.g. ``"FRONT CAM"``).

    Signals
    -------
    frame_ready : QImage
        Emitted each time a valid frame is decoded.  The QImage is in
        ``Format_RGB888`` and can be directly painted by the GUI thread.
    connection_status : bool
        ``True`` when the stream is opened successfully,
        ``False`` when it disconnects or fails to open.
    """

    frame_ready = pyqtSignal(QImage)
    connection_status = pyqtSignal(bool)

    def __init__(self, stream_url: str, label: str = "CAM",
                 parent=None):
        super().__init__(parent)
        self._url = stream_url
        self._label = label
        self._running = False
        self._cap: cv2.VideoCapture | None = None

    # ── Lifecycle ───────────────────────────────────────────────────────

    def run(self):
        self._running = True
        logger.info("%s: worker started, url=%s", self._label, self._url)

        while self._running:
            # ── Try to open the stream ─────────────────────────────────
            cap = self._open_stream()
            if cap is None:
                # Connection failed — signal and retry
                self.connection_status.emit(False)
                logger.warning(
                    "%s: connection failed, retrying in %.1fs",
                    self._label, CAMERA_RECONNECT_S,
                )
                self._interruptible_sleep(CAMERA_RECONNECT_S)
                continue

            # ── Stream opened successfully ─────────────────────────────
            self.connection_status.emit(True)
            logger.info("%s: stream opened", self._label)

            # ── Read loop ──────────────────────────────────────────────
            while self._running:
                ret, frame = cap.read()

                if not ret or frame is None:
                    logger.warning("%s: frame read failed, reconnecting", self._label)
                    break

                # Convert BGR → RGB and build QImage
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                qimg = QImage(
                    rgb.data, w, h, bytes_per_line, QImage.Format_RGB888
                ).copy()  # .copy() detaches from numpy buffer

                self.frame_ready.emit(qimg)

            # ── Stream dropped ─────────────────────────────────────────
            cap.release()
            self._cap = None
            if self._running:
                self.connection_status.emit(False)
                logger.info(
                    "%s: stream lost, retrying in %.1fs",
                    self._label, CAMERA_RECONNECT_S,
                )
                self._interruptible_sleep(CAMERA_RECONNECT_S)

        # Final cleanup
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("%s: worker stopped", self._label)

    def stop(self):
        """Request the worker to stop.  Non-blocking; call wait() after."""
        self._running = False
        self.quit()
        self.wait(3000)

    # ── Stream open helper ─────────────────────────────────────────────

    def _open_stream(self) -> cv2.VideoCapture | None:
        """Try to open the video stream with low-latency settings.

        Returns
        -------
        cv2.VideoCapture | None
            Opened capture object, or None if it failed.
        """
        try:
            cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)

            if not cap.isOpened():
                cap.release()
                return None

            # Low-latency tuning
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Attempt to read one test frame to confirm connectivity
            ret, _ = cap.read()
            if not ret:
                cap.release()
                return None

            self._cap = cap
            return cap

        except Exception as e:
            logger.error("%s: open failed — %s", self._label, e)
            return None

    # ── Helpers ────────────────────────────────────────────────────────

    def _interruptible_sleep(self, seconds: float):
        """Sleep in small increments so stop() takes effect promptly."""
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(0.1)

    @property
    def stream_url(self) -> str:
        return self._url

    @stream_url.setter
    def stream_url(self, url: str):
        """Change the URL.  Takes effect on next reconnection cycle."""
        self._url = url
