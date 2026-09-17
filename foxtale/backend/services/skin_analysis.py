"""Rule-based, classic-computer-vision skin analysis prototype.

This module intentionally uses only simple, explainable image-processing
heuristics (color-space thresholds, blob detection, local variance) rather
than a trained model. It exists to (a) ship a working MVP end-to-end and
(b) define a clean interface -- `analyze_face()` -- that a real ML model can
drop into later. See README.md "Replacing the prototype model" section.

All outputs are phrased as visual observations, never diagnoses, per the
product's safety requirements.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

import cv2
import numpy as np

from models.schemas import CategoryResult, RegionObservation, SkinAnalysis
from services.image_processing import FaceRegions

REGION_LABELS = {
    "forehead": "FOREHEAD",
    "left cheek": "LEFT CHEEK",
    "right cheek": "RIGHT CHEEK",
    "nose": "NOSE",
    "chin": "CHIN",
}


def _level_from_score(score: float) -> str:
    """Map a 0-1 heuristic score to a neutral, non-medical severity label."""
    if score < 0.15:
        return "minimal"
    if score < 0.35:
        return "mild"
    if score < 0.60:
        return "moderate"
    return "noticeable"


def _confidence(score: float, base: float = 0.55, spread: float = 0.35) -> float:
    """Turn a raw heuristic score into a plausible-looking, bounded confidence value.
    This is a UI/UX confidence proxy, not a statistically calibrated probability."""
    return round(min(0.95, max(0.35, base + spread * min(score, 1.0))), 2)


def _spot_score(region_bgr: np.ndarray) -> Tuple[float, int]:
    """Detect small dark/blemish-like blobs suggestive of acne-like spots.

    Approach: grayscale -> blur -> adaptive threshold to isolate localized dark
    spots relative to local skin tone, then filter contours by plausible size.
    """
    if region_bgr.size == 0:
        return 0.0, 0

    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 6
    )
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    area = region_bgr.shape[0] * region_bgr.shape[1]
    min_area = max(4, area * 0.0008)
    max_area = area * 0.03

    count = 0
    for c in contours:
        a = cv2.contourArea(c)
        if min_area <= a <= max_area:
            count += 1

    # Normalize count relative to region size so bigger crops aren't unfairly penalized.
    density = count / max(1.0, area / 4000.0)
    score = min(1.0, density / 3.0)
    return score, count


def _redness_score(region_bgr: np.ndarray) -> float:
    """Estimate visible redness relative to the region's own overall skin tone."""
    if region_bgr.size == 0:
        return 0.0

    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    red_mask = ((h <= 10) | (h >= 165)) & (s > 60) & (v > 60)
    ratio = float(np.mean(red_mask))
    score = min(1.0, ratio / 0.35)
    return score


def _texture_score(region_bgr: np.ndarray) -> float:
    """Estimate visible roughness / unevenness using local high-frequency variance."""
    if region_bgr.size == 0:
        return 0.0
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    variance = float(lap.var())
    score = min(1.0, variance / 350.0)
    return score


def _dryness_score(region_bgr: np.ndarray) -> float:
    """Estimate visible dryness/dullness cues: low saturation + patchy local brightness."""
    if region_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    low_sat_ratio = float(np.mean(s < 60))

    # Patchiness: std of block-averaged brightness (flaky-looking areas vary locally).
    h, w = v.shape
    block = max(4, min(h, w) // 8)
    patch_means = []
    for yy in range(0, h - block + 1, block):
        for xx in range(0, w - block + 1, block):
            patch_means.append(np.mean(v[yy:yy + block, xx:xx + block]))
    patchiness = float(np.std(patch_means)) if patch_means else 0.0

    score = min(1.0, 0.5 * low_sat_ratio / 0.5 + 0.5 * patchiness / 25.0)
    return score


@dataclass
class RegionScore:
    region: str
    spot_score: float
    spot_count: int
    redness_score: float
    texture_score: float
    dryness_score: float


def _score_regions(regions: FaceRegions) -> List[RegionScore]:
    scores = []
    for name, crop in regions.crops.items():
        spot_score, spot_count = _spot_score(crop)
        scores.append(
            RegionScore(
                region=name,
                spot_score=spot_score,
                spot_count=spot_count,
                redness_score=_redness_score(crop),
                texture_score=_texture_score(crop),
                dryness_score=_dryness_score(crop),
            )
        )
    return scores


def analyze_face(regions: FaceRegions) -> Tuple[SkinAnalysis, List[RegionObservation]]:
    """Run the full rule-based analysis pipeline and return the API-shaped result."""

    region_scores = _score_regions(regions)

    total_spots = sum(r.spot_count for r in region_scores)
    avg_spot_score = np.mean([r.spot_score for r in region_scores]) if region_scores else 0.0
    avg_redness = np.mean([r.redness_score for r in region_scores]) if region_scores else 0.0
    avg_texture = np.mean([r.texture_score for r in region_scores]) if region_scores else 0.0
    avg_dryness = np.mean([r.dryness_score for r in region_scores]) if region_scores else 0.0

    analysis = SkinAnalysis(
        acne_like_spots=CategoryResult(
            level=_level_from_score(avg_spot_score),
            confidence=_confidence(avg_spot_score),
            count=int(total_spots),
        ),
        redness=CategoryResult(
            level=_level_from_score(avg_redness),
            confidence=_confidence(avg_redness),
        ),
        texture=CategoryResult(
            level=_level_from_score(avg_texture),
            confidence=_confidence(avg_texture),
        ),
        dryness_indicators=CategoryResult(
            level=_level_from_score(avg_dryness),
            confidence=_confidence(avg_dryness),
        ),
    )

    observations: List[RegionObservation] = []
    for r in region_scores:
        cx, cy = regions.centers[r.region]
        label = REGION_LABELS.get(r.region, r.region.upper())

        if r.spot_score >= 0.15 and r.spot_count > 0:
            observations.append(RegionObservation(
                region=label,
                category="Acne-like spots",
                observation=f"{r.spot_count} visible spot(s) detected",
                confidence=_confidence(r.spot_score),
                x=cx, y=cy,
            ))
        if r.redness_score >= 0.2:
            observations.append(RegionObservation(
                region=label,
                category="Redness",
                observation=f"Visible redness detected around the {r.region} area",
                confidence=_confidence(r.redness_score),
                x=cx, y=cy,
            ))
        if r.texture_score >= 0.3:
            observations.append(RegionObservation(
                region=label,
                category="Texture",
                observation="Uneven-looking texture detected",
                confidence=_confidence(r.texture_score),
                x=cx, y=cy,
            ))
        if r.dryness_score >= 0.3:
            observations.append(RegionObservation(
                region=label,
                category="Dryness indicators",
                observation="Visual characteristics that can be associated with dryness",
                confidence=_confidence(r.dryness_score),
                x=cx, y=cy,
            ))

    return analysis, observations
