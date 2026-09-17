"""Face preprocessing: cropping, normalizing, and splitting the face into regions."""

from dataclasses import dataclass
from typing import Dict, Tuple

import cv2
import numpy as np


@dataclass
class FaceRegions:
    """Cropped sub-images for each analyzed facial region, plus their normalized
    center coordinates (0-1) within the *full* source image, used for placing
    markers on the frontend's face visualization."""

    crops: Dict[str, np.ndarray]
    centers: Dict[str, Tuple[float, float]]


def crop_face(image: np.ndarray, box: Tuple[int, int, int, int], padding: float = 0.25) -> np.ndarray:
    """Crop the face out of the full image with a small margin."""
    x, y, w, h = box
    pad_x, pad_y = int(w * padding), int(h * padding)
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(image.shape[1], x + w + pad_x)
    y1 = min(image.shape[0], y + h + pad_y)
    return image[y0:y1, x0:x1]


def normalize(image: np.ndarray) -> np.ndarray:
    """Mild contrast normalization so lighting differences don't skew heuristics."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge((l, a, b))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def split_regions(image: np.ndarray, box: Tuple[int, int, int, int]) -> FaceRegions:
    """Divide the detected face into forehead / left cheek / right cheek / nose / chin
    using simple proportional geometry, which is a reasonable approximation without
    a full facial-landmark model."""

    x, y, w, h = box
    img_h, img_w = image.shape[:2]

    def clamp_box(bx0, by0, bx1, by1):
        bx0, by0 = max(0, bx0), max(0, by0)
        bx1, by1 = min(img_w, bx1), min(img_h, by1)
        return bx0, by0, bx1, by1

    regions_px = {
        "forehead": (x + int(0.10 * w), y, x + int(0.90 * w), y + int(0.28 * h)),
        "left cheek": (x + int(0.05 * w), y + int(0.40 * h), x + int(0.40 * w), y + int(0.75 * h)),
        "right cheek": (x + int(0.60 * w), y + int(0.40 * h), x + int(0.95 * w), y + int(0.75 * h)),
        "nose": (x + int(0.38 * w), y + int(0.30 * h), x + int(0.62 * w), y + int(0.68 * h)),
        "chin": (x + int(0.30 * w), y + int(0.78 * h), x + int(0.70 * w), y + int(1.02 * h)),
    }

    crops: Dict[str, np.ndarray] = {}
    centers: Dict[str, Tuple[float, float]] = {}

    for name, (bx0, by0, bx1, by1) in regions_px.items():
        bx0, by0, bx1, by1 = clamp_box(bx0, by0, bx1, by1)
        crop = image[by0:by1, bx0:bx1]
        if crop.size == 0:
            continue
        crops[name] = crop
        centers[name] = (
            ((bx0 + bx1) / 2) / img_w,
            ((by0 + by1) / 2) / img_h,
        )

    return FaceRegions(crops=crops, centers=centers)
