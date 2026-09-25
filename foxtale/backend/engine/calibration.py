"""Optional per-user skin-tone calibration.

The web app scores every user against the same fixed thresholds. The desktop
app adds an opt-in calibration step: sample a small forehead patch under
guidance ("look straight ahead, no shadows") and use it as a personal
baseline, so naturally warmer/cooler skin tones or ambient lighting don't get
mis-read as redness or dryness. This never changes the *language* used in
results -- only shifts the numeric thresholds slightly.
"""

from dataclasses import dataclass, asdict
from typing import Optional

import cv2
import numpy as np


@dataclass
class CalibrationProfile:
    red_ratio_baseline: float = 0.0
    saturation_baseline: float = 120.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "CalibrationProfile":
        return CalibrationProfile(**d)


def compute_calibration(patch_bgr: np.ndarray) -> Optional[CalibrationProfile]:
    if patch_bgr.size == 0:
        return None

    hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    red_mask = ((h <= 10) | (h >= 165)) & (s > 60) & (v > 60)
    red_ratio = float(np.mean(red_mask))
    saturation = float(np.mean(s))

    return CalibrationProfile(red_ratio_baseline=red_ratio, saturation_baseline=saturation)
