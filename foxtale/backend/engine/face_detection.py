"""Local face detection.

Primary detector is OpenCV's YuNet (a small CNN, `assets/models/face_detection_yunet_2023mar.onnx`,
~230 KB, from opencv_zoo) run through `cv2.FaceDetectorYN` -- it handles tilted faces, partial
profiles and dim light far better than the old Haar cascade. If the model file is missing or
fails to load, it falls back to the Haar cascade so the app keeps working.
"""

import os
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


MIN_FACE_AREA_RATIO = 0.04
MAX_FACE_AREA_RATIO = 0.70

YUNET_MODEL_PATH = os.environ.get(
    "FACE_MODEL_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "assets", "models", "face_detection_yunet_2023mar.onnx"),
)
YUNET_SCORE_THRESHOLD = float(os.environ.get("FACE_SCORE_THRESHOLD", "0.75"))
# A second detected face only counts as "multiple faces" if it is at least this fraction of the
# largest face's area -- a tiny face far in the background shouldn't block the scan.
SECONDARY_FACE_AREA_RATIO = 0.25

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

_yunet = None
_yunet_lock = threading.Lock()  # FaceDetectorYN keeps per-call state (input size); not thread-safe
if hasattr(cv2, "FaceDetectorYN") and os.path.exists(YUNET_MODEL_PATH):
    try:
        _yunet = cv2.FaceDetectorYN.create(YUNET_MODEL_PATH, "", (320, 320), YUNET_SCORE_THRESHOLD, 0.3, 5000)
    except cv2.error:
        _yunet = None

DETECTOR_NAME = "yunet" if _yunet is not None else "haar"

Box = Tuple[int, int, int, int]


@dataclass
class FaceDetectionResult:
    ok: bool
    error: Optional[str] = None
    message: Optional[str] = None
    box: Optional[Box] = None
    confidence: Optional[float] = None
    # Five YuNet landmarks: right eye, left eye, nose tip, right mouth corner, left mouth corner.
    landmarks: Optional[List[Tuple[int, int]]] = None


def _detect_yunet(image: np.ndarray) -> List[Tuple[Box, float, List[Tuple[int, int]]]]:
    h, w = image.shape[:2]
    with _yunet_lock:
        _yunet.setInputSize((w, h))
        _, faces = _yunet.detect(image)
    if faces is None:
        return []
    out = []
    for f in faces:
        # YuNet's box is tall (brow-to-chin); the region geometry downstream (features.py zones,
        # quality.py aspect check) is tuned to the square Haar box. Convert: side ~= 1.2 x YuNet
        # width, centred, nudged up 3% of its height -- fitted against Haar on real scans (~5% error).
        side = 1.2 * f[2]
        cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2 - 0.03 * f[3]
        x, y = int(round(cx - side / 2)), int(round(cy - side / 2))
        bw = bh = int(round(side))
        x0, y0 = max(0, x), max(0, y)
        bw, bh = min(bw - (x0 - x), w - x0), min(bh - (y0 - y), h - y0)
        x, y = x0, y0
        if bw <= 0 or bh <= 0:
            continue
        lms = [(int(round(f[4 + 2 * i])), int(round(f[5 + 2 * i]))) for i in range(5)]
        out.append(((x, y, bw, bh), float(f[14]), lms))
    out.sort(key=lambda d: d[0][2] * d[0][3], reverse=True)
    return out


def _detect_haar(gray: np.ndarray, scale: float, neighbors: int, min_size: int) -> List[Box]:
    faces = _face_cascade.detectMultiScale(gray, scaleFactor=scale, minNeighbors=neighbors,
                                           minSize=(min_size, min_size))
    return sorted(((int(x), int(y), int(w), int(h)) for x, y, w, h in faces),
                  key=lambda b: b[2] * b[3], reverse=True)


def quick_face_check(image: np.ndarray) -> Tuple[bool, Optional[Box]]:
    """Fast single-face check for the live camera preview overlay (throttled,
    not run on every frame). Returns (found, box) without the stricter quality
    checks used by detect_face()."""
    small = cv2.resize(image, (0, 0), fx=0.5, fy=0.5)
    if _yunet is not None:
        faces = [d[0] for d in _detect_yunet(small)]
    else:
        faces = _detect_haar(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.15, 5, 40)
    if not faces:
        return False, None
    x, y, w, h = faces[0]
    return True, (x * 2, y * 2, w * 2, h * 2)


def detect_face(image: np.ndarray) -> FaceDetectionResult:
    """Authoritative detection + quality checks, run once on the captured photo."""

    confidence: Optional[float] = None
    landmarks: Optional[List[Tuple[int, int]]] = None
    if _yunet is not None:
        detections = _detect_yunet(image)
        faces = [d[0] for d in detections]
        if detections:
            _, confidence, landmarks = detections[0]
    else:
        faces = _detect_haar(cv2.equalizeHist(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)), 1.1, 6, 60)

    if len(faces) == 0:
        return FaceDetectionResult(
            ok=False, error="no_face",
            message="No face detected. Please position your face inside the scanning area.",
        )

    largest_area = faces[0][2] * faces[0][3]
    significant = [f for f in faces if f[2] * f[3] >= SECONDARY_FACE_AREA_RATIO * largest_area]
    if len(significant) > 1:
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

    return FaceDetectionResult(ok=True, box=(x, y, w, h), confidence=confidence, landmarks=landmarks)
