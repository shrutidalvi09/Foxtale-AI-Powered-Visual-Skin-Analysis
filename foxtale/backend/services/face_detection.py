"""Lightweight, local face detection using OpenCV Haar cascades.

This intentionally avoids any external model downloads or GPU dependencies so
the MVP runs anywhere `opencv-python-headless` installs. See the README for
notes on swapping this out for MediaPipe / RetinaFace in a production build.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from utils.image_utils import mean_brightness

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# Tunable thresholds for guidance heuristics.
MIN_BRIGHTNESS = 60.0
MIN_FACE_AREA_RATIO = 0.04  # face too far if smaller than this fraction of image area
MAX_FACE_AREA_RATIO = 0.70  # face too close if larger than this fraction of image area


@dataclass
class FaceDetectionResult:
    ok: bool
    error: Optional[str] = None  # no_face | multiple_faces | poor_lighting | too_close | too_far
    message: Optional[str] = None
    box: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h


def detect_face(image: np.ndarray) -> FaceDetectionResult:
    """Run face detection plus basic quality checks and return one authoritative result."""

    brightness = mean_brightness(image)
    if brightness < MIN_BRIGHTNESS:
        return FaceDetectionResult(
            ok=False,
            error="poor_lighting",
            message="Lighting is insufficient. Move to a well-lit area and try again.",
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    faces: List[Tuple[int, int, int, int]] = list(
        _face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=6, minSize=(60, 60)
        )
    )

    if len(faces) == 0:
        return FaceDetectionResult(
            ok=False,
            error="no_face",
            message="No face detected. Please position your face inside the scanning area.",
        )

    if len(faces) > 1:
        return FaceDetectionResult(
            ok=False,
            error="multiple_faces",
            message="Multiple faces detected. Please make sure only one person is visible.",
        )

    x, y, w, h = faces[0]
    image_area = image.shape[0] * image.shape[1]
    face_area_ratio = (w * h) / image_area

    if face_area_ratio < MIN_FACE_AREA_RATIO:
        return FaceDetectionResult(
            ok=False, error="too_far", message="Move closer to the camera."
        )

    if face_area_ratio > MAX_FACE_AREA_RATIO:
        return FaceDetectionResult(
            ok=False, error="too_close", message="Move slightly farther away."
        )

    return FaceDetectionResult(ok=True, box=(int(x), int(y), int(w), int(h)))
