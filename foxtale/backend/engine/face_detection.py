"""Lightweight, local face detection using OpenCV Haar cascades.

Same approach as the Foxtale web backend: no external model downloads, runs
anywhere opencv-python installs. See README for notes on swapping this for
MediaPipe / RetinaFace in a production build.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

MIN_FACE_AREA_RATIO = 0.04
MAX_FACE_AREA_RATIO = 0.70


@dataclass
class FaceDetectionResult:
    ok: bool
    error: Optional[str] = None
    message: Optional[str] = None
    box: Optional[Tuple[int, int, int, int]] = None


def quick_face_check(image: np.ndarray) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
    """Fast single-face check for the live camera preview overlay (throttled,
    not run on every frame). Returns (found, box) without the stricter quality
    checks used by detect_face()."""
    small = cv2.resize(image, (0, 0), fx=0.5, fy=0.5)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(40, 40))
    if len(faces) == 0:
        return False, None
    x, y, w, h = faces[0]
    return True, (int(x * 2), int(y * 2), int(w * 2), int(h * 2))


def detect_face(image: np.ndarray) -> FaceDetectionResult:
    """Authoritative detection + quality checks, run once on the captured photo."""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    faces: List[Tuple[int, int, int, int]] = list(
        _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(60, 60))
    )

    if len(faces) == 0:
        return FaceDetectionResult(
            ok=False, error="no_face",
            message="No face detected. Please position your face inside the scanning area.",
        )

    if len(faces) > 1:
        return FaceDetectionResult(
            ok=False, error="multiple_faces",
            message="Multiple faces detected. Please make sure only one person is visible.",
        )

    x, y, w, h = faces[0]
    image_area = image.shape[0] * image.shape[1]
    face_area_ratio = (w * h) / image_area

    if face_area_ratio < MIN_FACE_AREA_RATIO:
        return FaceDetectionResult(ok=False, error="too_far", message="Move closer to the camera.")

    if face_area_ratio > MAX_FACE_AREA_RATIO:
        return FaceDetectionResult(ok=False, error="too_close", message="Move slightly farther away.")

    return FaceDetectionResult(ok=True, box=(int(x), int(y), int(w), int(h)))
