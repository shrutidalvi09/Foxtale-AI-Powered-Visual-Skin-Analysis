"""Low-level image decoding helpers shared by services."""

import numpy as np
import cv2


def decode_image(raw_bytes: bytes) -> np.ndarray:
    """Decode raw uploaded bytes into a BGR OpenCV image."""
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image. Please upload a valid JPEG/PNG file.")
    return image


def resize_max_dim(image: np.ndarray, max_dim: int = 900) -> np.ndarray:
    """Resize an image so its longest side does not exceed max_dim, preserving aspect ratio."""
    h, w = image.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1.0:
        return image
    new_size = (int(w * scale), int(h * scale))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def mean_brightness(image: np.ndarray) -> float:
    """Return average brightness (0-255) of an image using the V channel of HSV."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return float(np.mean(hsv[:, :, 2]))
