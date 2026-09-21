"""Scan-quality scoring: a composite 0-100 score (position, lighting,
distance, sharpness, and an approximate face-angle signal) computed for
every captured photo, plus the live single-line guidance shown on the
camera preview before capture.

None of this claims true 3D head-pose estimation -- the engine only has a
Haar-cascade bounding box, not facial landmarks -- so "angle" is a coarse
proxy from box aspect ratio and left/right symmetry, not a real yaw/pitch/
roll measurement. It's good enough to nudge "turn to face the camera" but
should not be sold as precise.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

IDEAL_FACE_AREA_RATIO = (0.10, 0.30)  # sweet spot, inside face_detection's hard min/max
IDEAL_BRIGHTNESS = (110.0, 190.0)
IDEAL_ASPECT_RATIO = (0.78, 1.05)  # typical frontal Haar-cascade face box w/h
CENTER_TOLERANCE = 0.10  # normalized offset from frame center considered "centered"
SHARPNESS_CEILING = 600.0  # Laplacian variance mapped to 100 at/above this


@dataclass
class QualityResult:
    position_score: int
    lighting_score: int
    distance_score: int
    sharpness_score: int
    angle_score: int
    overall: int
    tips: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "position_score": self.position_score,
            "lighting_score": self.lighting_score,
            "distance_score": self.distance_score,
            "sharpness_score": self.sharpness_score,
            "angle_score": self.angle_score,
            "overall": self.overall,
        }

    @staticmethod
    def from_dict(d: dict) -> "QualityResult":
        return QualityResult(
            position_score=d.get("position_score", 0),
            lighting_score=d.get("lighting_score", 0),
            distance_score=d.get("distance_score", 0),
            sharpness_score=d.get("sharpness_score", 0),
            angle_score=d.get("angle_score", 0),
            overall=d.get("overall", 0),
            tips=[],
        )


def _band_score(value: float, ideal: Tuple[float, float], tolerance: float) -> float:
    """1.0 inside the ideal band, falling off linearly outside it by `tolerance`
    (in the same units as `value`/`ideal`), floored at 0."""
    lo, hi = ideal
    if lo <= value <= hi:
        return 1.0
    edge = lo - value if value < lo else value - hi
    return max(0.0, 1.0 - edge / tolerance)


def shadow_asymmetry(image_bgr: np.ndarray, box: Tuple[int, int, int, int]) -> float:
    """Mean brightness difference between the left and right halves of the
    face box (right half mirrored before comparing). 0 = perfectly
    symmetric lighting; higher = more one-sided shadow/lighting. A cheap,
    landmark-free proxy -- not true shadow segmentation."""
    x, y, w, h = box
    face_crop = image_bgr[max(0, y):y + h, max(0, x):x + w]
    if not face_crop.size:
        return 0.0
    half = face_crop.shape[1] // 2
    if half <= 0:
        return 0.0
    left_half = cv2.cvtColor(face_crop[:, :half], cv2.COLOR_BGR2GRAY)
    right_half = cv2.cvtColor(cv2.flip(face_crop[:, half:], 1), cv2.COLOR_BGR2GRAY)
    min_w = min(left_half.shape[1], right_half.shape[1])
    if min_w <= 0:
        return 0.0
    return float(np.mean(np.abs(
        left_half[:, :min_w].astype(np.float32) - right_half[:, :min_w].astype(np.float32)
    )))


def compute_quality(image_bgr: np.ndarray, box: Tuple[int, int, int, int]) -> QualityResult:
    x, y, w, h = box
    img_h, img_w = image_bgr.shape[:2]
    tips: List[str] = []

    # --- position ---
    cx, cy = x + w / 2, y + h / 2
    dx = (cx - img_w / 2) / img_w
    dy = (cy - img_h / 2) / img_h
    offset = (dx ** 2 + dy ** 2) ** 0.5
    position_score = round(max(0.0, 1.0 - max(0.0, offset - CENTER_TOLERANCE) / 0.35) * 100)
    if abs(dx) > CENTER_TOLERANCE:
        tips.append("Move slightly left" if dx > 0 else "Move slightly right")
    if abs(dy) > CENTER_TOLERANCE:
        tips.append("Move slightly down" if dy < 0 else "Move slightly up")

    # --- distance (via face area ratio) ---
    area_ratio = (w * h) / (img_w * img_h)
    distance_score = round(_band_score(area_ratio, IDEAL_FACE_AREA_RATIO, 0.12) * 100)
    if area_ratio < IDEAL_FACE_AREA_RATIO[0]:
        tips.append("Move closer to the camera")
    elif area_ratio > IDEAL_FACE_AREA_RATIO[1]:
        tips.append("Move back slightly")

    # --- lighting ---
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    brightness = float(np.mean(hsv[:, :, 2]))
    lighting_score = round(_band_score(brightness, IDEAL_BRIGHTNESS, 60.0) * 100)
    if brightness < IDEAL_BRIGHTNESS[0]:
        tips.append("Move to a brighter, more evenly lit area")
    elif brightness > IDEAL_BRIGHTNESS[1]:
        tips.append("Reduce strong backlight or direct light on your face")

    # --- sharpness ---
    face_crop = image_bgr[max(0, y):y + h, max(0, x):x + w]
    if face_crop.size:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    else:
        variance = 0.0
    sharpness_score = round(min(1.0, variance / SHARPNESS_CEILING) * 100)
    if sharpness_score < 55:
        tips.append("Hold the camera steady for a sharper capture")

    # --- angle (approximate: box aspect ratio + left/right symmetry) ---
    aspect = w / h if h else 0.0
    aspect_component = _band_score(aspect, IDEAL_ASPECT_RATIO, 0.25)
    diff = shadow_asymmetry(image_bgr, box)
    symmetry_component = max(0.0, 1.0 - diff / 60.0)
    angle_score = round(((aspect_component + symmetry_component) / 2) * 100)
    if angle_score < 55:
        tips.append("Face the camera directly, keeping your head straight")

    overall = round(
        0.25 * sharpness_score + 0.20 * lighting_score + 0.20 * distance_score
        + 0.20 * position_score + 0.15 * angle_score
    )

    if not tips:
        tips.append("Great capture quality — well positioned, lit, and sharp.")

    return QualityResult(
        position_score=position_score, lighting_score=lighting_score,
        distance_score=distance_score, sharpness_score=sharpness_score,
        angle_score=angle_score, overall=overall, tips=tips[:2],
    )


@dataclass
class FrameStatus:
    """Everything the live camera preview needs about one checked frame,
    bundled so it can travel across the worker-thread signal as a single
    object instead of a growing list of positional bool/float/str args."""
    face_detected: bool
    brightness: float
    guidance: str
    box: Optional[Tuple[int, int, int, int]]
    shadow: float
    exposure_stable: bool
    img_w: int
    img_h: int

    def checklist(self) -> List[Tuple[str, bool]]:
        """Pass/fail booleans for Standardised Scan Mode's checklist."""
        if not self.face_detected or self.box is None:
            return [
                ("Face centered", False), ("Distance consistent", False),
                ("Brightness in range", False), ("Low shadow", False),
                ("Exposure stable", False),
            ]
        x, y, w, h = self.box
        cx, cy = x + w / 2, y + h / 2
        dx = (cx - self.img_w / 2) / self.img_w
        dy = (cy - self.img_h / 2) / self.img_h
        centered = (dx ** 2 + dy ** 2) ** 0.5 <= CENTER_TOLERANCE
        area_ratio = (w * h) / (self.img_w * self.img_h)
        distance_ok = IDEAL_FACE_AREA_RATIO[0] <= area_ratio <= IDEAL_FACE_AREA_RATIO[1]
        brightness_ok = IDEAL_BRIGHTNESS[0] <= self.brightness <= IDEAL_BRIGHTNESS[1]
        low_shadow = self.shadow <= 18.0
        return [
            ("Face centered", centered), ("Distance consistent", distance_ok),
            ("Brightness in range", brightness_ok), ("Low shadow", low_shadow),
            ("Exposure stable", self.exposure_stable),
        ]

    @property
    def all_standardised_checks_pass(self) -> bool:
        return all(ok for _, ok in self.checklist())


def live_guidance(box: Optional[Tuple[int, int, int, int]], img_w: int, img_h: int, brightness: float) -> str:
    """A single, most-relevant instruction for the live camera overlay --
    prioritized distance > position > lighting so only one thing is asked
    of the user at a time, matching how the capture-quality tips work."""
    if box is None:
        return "Position your face inside the frame"

    x, y, w, h = box
    area_ratio = (w * h) / (img_w * img_h)
    if area_ratio < IDEAL_FACE_AREA_RATIO[0]:
        return "Move closer"
    if area_ratio > IDEAL_FACE_AREA_RATIO[1]:
        return "Move back"

    cx, cy = x + w / 2, y + h / 2
    dx = (cx - img_w / 2) / img_w
    dy = (cy - img_h / 2) / img_h
    if abs(dx) > CENTER_TOLERANCE:
        return "Move slightly left" if dx > 0 else "Move slightly right"
    if abs(dy) > CENTER_TOLERANCE:
        return "Move slightly down" if dy < 0 else "Move slightly up"

    if brightness < IDEAL_BRIGHTNESS[0]:
        return "Improve lighting"
    if brightness > IDEAL_BRIGHTNESS[1]:
        return "Reduce strong light on your face"

    return "Face detected — hold still"
