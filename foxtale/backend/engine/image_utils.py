"""Low-level image helpers shared by the analysis engine."""

import numpy as np
import cv2


def resize_max_dim(image: np.ndarray, max_dim: int = 900) -> np.ndarray:
    h, w = image.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1.0:
        return image
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def mean_brightness(image: np.ndarray) -> float:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return float(np.mean(hsv[:, :, 2]))


def sharpness_score(image: np.ndarray) -> float:
    """Higher = sharper. Used to auto-pick the best frame from a capture burst."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
