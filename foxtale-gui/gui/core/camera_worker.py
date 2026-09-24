"""QThread wrapping cv2.VideoCapture so the UI never blocks on frame reads.

Emits live frames plus a throttled face-lock/brightness status, and supports
listing available camera devices and a "burst capture" that grabs several
frames and keeps the sharpest one.
"""

import logging
from collections import deque
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from engine.face_detection import quick_face_check
from engine.image_utils import mean_brightness, sharpness_score
from engine.quality import FrameStatus, live_guidance, shadow_asymmetry

logger = logging.getLogger(f"foxtale.{__name__}")

FACE_CHECK_EVERY_N_FRAMES = 6
EXPOSURE_STABILITY_WINDOW = 8
EXPOSURE_STABLE_STD_THRESHOLD = 8.0


def list_camera_indices(max_probe: int = 5) -> List[int]:
    """Probe the first few device indices and return the ones that open."""
    found = []
    for i in range(max_probe):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            found.append(i)
        cap.release()
    return found or [0]


class CameraWorker(QThread):
    frame_ready = Signal(np.ndarray)
    status_ready = Signal(object)  # FrameStatus
    error = Signal(str)

    def __init__(self, camera_index: int = 0, width: int = 1280, height: int = 720, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self._running = False
        self._cap: Optional[cv2.VideoCapture] = None
        self._burst_request = 0
        self._burst_frames: List[np.ndarray] = []
        self._burst_result: Optional[np.ndarray] = None
        self._brightness_history: deque = deque(maxlen=EXPOSURE_STABILITY_WINDOW)

    def run(self) -> None:
        try:
            self._run_loop()
        except Exception:
            logger.exception("Camera worker crashed")
            self.error.emit(
                "The camera feed stopped unexpectedly. Try restarting the scan, or check "
                "that no other app is using the camera."
            )
        finally:
            if self._cap:
                self._cap.release()

    def _run_loop(self) -> None:
        self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        if not self._cap.isOpened():
            self.error.emit(
                "Camera permission is required for face scanning. Please enable camera "
                "access in your system settings, or check that no other app is using the camera."
            )
            return

        self._running = True
        frame_count = 0

        while self._running:
            ok, frame = self._cap.read()
            if not ok or frame is None:
                continue

            frame = cv2.flip(frame, 1)  # mirror, feels natural for a selfie-style scanner
            self.frame_ready.emit(frame)

            frame_count += 1
            if frame_count % FACE_CHECK_EVERY_N_FRAMES == 0:
                found, box = quick_face_check(frame)
                brightness = mean_brightness(frame)
                h, w = frame.shape[:2]
                guidance = live_guidance(box, w, h, brightness)
                shadow = shadow_asymmetry(frame, box) if box else 0.0

                self._brightness_history.append(brightness)
                exposure_stable = (
                    len(self._brightness_history) >= 3
                    and float(np.std(self._brightness_history)) <= EXPOSURE_STABLE_STD_THRESHOLD
                )

                self.status_ready.emit(FrameStatus(
                    face_detected=found, brightness=brightness, guidance=guidance, box=box,
                    shadow=shadow, exposure_stable=exposure_stable, img_w=w, img_h=h,
                ))

            if self._burst_request > 0:
                self._burst_frames.append(frame.copy())
                self._burst_request -= 1
                if self._burst_request == 0:
                    self._burst_result = max(self._burst_frames, key=sharpness_score)
                    self._burst_frames = []

    def request_capture(self, burst_count: int = 5) -> None:
        """Ask the running loop to grab `burst_count` frames and keep the sharpest."""
        self._burst_result = None
        self._burst_frames = []
        self._burst_request = burst_count

    def take_burst_result(self) -> Optional[np.ndarray]:
        result, self._burst_result = self._burst_result, None
        return result

    def stop(self) -> None:
        self._running = False
        self.wait(2000)
