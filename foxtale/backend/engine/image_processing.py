"""Face preprocessing: normalizing and splitting the face into regions."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


@dataclass
class FaceRegions:
    crops: Dict[str, np.ndarray]
    centers: Dict[str, Tuple[float, float]]
    # Top-left pixel offset of each crop and the source image size, so
    # detections inside a crop can be mapped back to normalized (0-1) image
    # coordinates for on-photo markers.
    origins: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    image_size: Tuple[int, int] = (0, 0)  # (width, height)
    # The analysed photo and face box, for detectors that need more than the five crops (eyes, lines, symmetry).
    image: Optional[np.ndarray] = None
    box: Optional[Tuple[int, int, int, int]] = None


def normalize(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge((l, a, b))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def split_regions(image: np.ndarray, box: Tuple[int, int, int, int]) -> FaceRegions:
    x, y, w, h = box
    img_h, img_w = image.shape[:2]

    def clamp(bx0, by0, bx1, by1):
        return max(0, bx0), max(0, by0), min(img_w, bx1), min(img_h, by1)

    regions_px = {
        "forehead": (x + int(0.10 * w), y, x + int(0.90 * w), y + int(0.28 * h)),
        "left cheek": (x + int(0.05 * w), y + int(0.40 * h), x + int(0.40 * w), y + int(0.75 * h)),
        "right cheek": (x + int(0.60 * w), y + int(0.40 * h), x + int(0.95 * w), y + int(0.75 * h)),
        "nose": (x + int(0.38 * w), y + int(0.30 * h), x + int(0.62 * w), y + int(0.68 * h)),
        "chin": (x + int(0.30 * w), y + int(0.78 * h), x + int(0.70 * w), y + int(1.02 * h)),
    }

    crops: Dict[str, np.ndarray] = {}
    centers: Dict[str, Tuple[float, float]] = {}
    origins: Dict[str, Tuple[int, int]] = {}

    for name, (bx0, by0, bx1, by1) in regions_px.items():
        bx0, by0, bx1, by1 = clamp(bx0, by0, bx1, by1)
        crop = image[by0:by1, bx0:bx1]
        if crop.size == 0:
            continue
        crops[name] = crop
        centers[name] = (((bx0 + bx1) / 2) / img_w, ((by0 + by1) / 2) / img_h)
        origins[name] = (bx0, by0)

    return FaceRegions(crops=crops, centers=centers, origins=origins, image_size=(img_w, img_h), image=image, box=tuple(box))  # type: ignore[arg-type]


def forehead_calibration_patch(image: np.ndarray, box: Tuple[int, int, int, int]) -> np.ndarray:
    """A small, usually-clear patch of forehead used for skin-tone calibration."""
    x, y, w, h = box
    img_h, img_w = image.shape[:2]
    bx0 = max(0, x + int(0.35 * w))
    by0 = max(0, y + int(0.06 * h))
    bx1 = min(img_w, x + int(0.65 * w))
    by1 = min(img_h, y + int(0.20 * h))
    return image[by0:by1, bx0:bx1]
