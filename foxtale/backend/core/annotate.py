"""Draws the coloured observation markers on the photo used in the PDF report."""

from typing import List

import cv2
import numpy as np

from engine.schemas import RegionObservation

CATEGORY_COLOR_BGR = {
    "Acne-like spots": (60, 60, 220),
    "Redness": (0, 140, 255),
    "Texture": (0, 190, 255),
    "Dryness indicators": (255, 170, 80),
    "Oiliness": (200, 200, 60),
    "Tone evenness": (200, 120, 200),
}


def save_annotated_image(image_bgr: np.ndarray, regions: List[RegionObservation], dest_path: str) -> None:
    annotated = image_bgr.copy()
    h, w = annotated.shape[:2]
    for r in regions:
        center = (int(r.x * w), int(r.y * h))
        color = CATEGORY_COLOR_BGR.get(r.category, (255, 140, 94))
        cv2.circle(annotated, center, 8, color, -1, lineType=cv2.LINE_AA)
        cv2.circle(annotated, center, 8, (255, 255, 255), 2, lineType=cv2.LINE_AA)
    cv2.imwrite(dest_path, annotated)
