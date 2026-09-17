"""Rule-based, classic-computer-vision skin analysis (ported from the Foxtale
web backend). All outputs are phrased as visual observations, never
diagnoses. See README "Replacing the prototype model" for how to swap this
for a trained model later.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from engine.calibration import CalibrationProfile
from engine.image_processing import FaceRegions
from engine.schemas import CategoryResult, RegionObservation, SkinAnalysis

REGION_LABELS = {
    "forehead": "FOREHEAD",
    "left cheek": "LEFT CHEEK",
    "right cheek": "RIGHT CHEEK",
    "nose": "NOSE",
    "chin": "CHIN",
}


def _level_from_score(score: float) -> str:
    if score < 0.15:
        return "minimal"
    if score < 0.35:
        return "mild"
    if score < 0.60:
        return "moderate"
    return "noticeable"


def _confidence(score: float, base: float = 0.55, spread: float = 0.35) -> float:
    return round(min(0.95, max(0.35, base + spread * min(score, 1.0))), 2)


def _spot_score(region_bgr: np.ndarray) -> Tuple[float, int]:
    if region_bgr.size == 0:
        return 0.0, 0
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 6)
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    area = region_bgr.shape[0] * region_bgr.shape[1]
    min_area = max(4, area * 0.0008)
    max_area = area * 0.03

    count = sum(1 for c in contours if min_area <= cv2.contourArea(c) <= max_area)
    density = count / max(1.0, area / 4000.0)
    return min(1.0, density / 3.0), count


def _redness_score(region_bgr: np.ndarray, calibration: Optional[CalibrationProfile]) -> float:
    if region_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    red_mask = ((h <= 10) | (h >= 165)) & (s > 60) & (v > 60)
    ratio = float(np.mean(red_mask))

    baseline = calibration.red_ratio_baseline if calibration else 0.0
    adjusted = max(0.0, ratio - baseline)
    return min(1.0, adjusted / 0.35)


def _texture_score(region_bgr: np.ndarray) -> float:
    if region_bgr.size == 0:
        return 0.0
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return min(1.0, variance / 350.0)


def _dryness_score(region_bgr: np.ndarray, calibration: Optional[CalibrationProfile]) -> float:
    if region_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    s, v = hsv[:, :, 1], hsv[:, :, 2]

    sat_reference = calibration.saturation_baseline if calibration else 120.0
    sat_threshold = max(30.0, sat_reference * 0.5)
    low_sat_ratio = float(np.mean(s < sat_threshold))

    h, w = v.shape
    block = max(4, min(h, w) // 8)
    patch_means = [
        np.mean(v[yy:yy + block, xx:xx + block])
        for yy in range(0, h - block + 1, block)
        for xx in range(0, w - block + 1, block)
    ]
    patchiness = float(np.std(patch_means)) if patch_means else 0.0

    return min(1.0, 0.5 * low_sat_ratio / 0.5 + 0.5 * patchiness / 25.0)


@dataclass
class RegionScore:
    region: str
    spot_score: float
    spot_count: int
    redness_score: float
    texture_score: float
    dryness_score: float


def _score_regions(regions: FaceRegions, calibration: Optional[CalibrationProfile]) -> List[RegionScore]:
    scores = []
    for name, crop in regions.crops.items():
        spot_score, spot_count = _spot_score(crop)
        scores.append(RegionScore(
            region=name,
            spot_score=spot_score,
            spot_count=spot_count,
            redness_score=_redness_score(crop, calibration),
            texture_score=_texture_score(crop),
            dryness_score=_dryness_score(crop, calibration),
        ))
    return scores


def analyze_face(
    regions: FaceRegions,
    calibration: Optional[CalibrationProfile] = None,
    min_confidence: float = 0.0,
) -> Tuple[SkinAnalysis, List[RegionObservation]]:
    """Run the full rule-based analysis pipeline.

    `min_confidence` filters which per-region observations are surfaced
    (a GUI-only "advanced" setting; the four summary cards always reflect
    every region regardless of this filter).
    """

    region_scores = _score_regions(regions, calibration)

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
        redness=CategoryResult(level=_level_from_score(avg_redness), confidence=_confidence(avg_redness)),
        texture=CategoryResult(level=_level_from_score(avg_texture), confidence=_confidence(avg_texture)),
        dryness_indicators=CategoryResult(level=_level_from_score(avg_dryness), confidence=_confidence(avg_dryness)),
    )

    observations: List[RegionObservation] = []
    for r in region_scores:
        cx, cy = regions.centers[r.region]
        label = REGION_LABELS.get(r.region, r.region.upper())

        candidates = []
        if r.spot_score >= 0.15 and r.spot_count > 0:
            candidates.append(("Acne-like spots", f"{r.spot_count} visible spot(s) detected", r.spot_score))
        if r.redness_score >= 0.2:
            candidates.append(("Redness", f"Visible redness detected around the {r.region} area", r.redness_score))
        if r.texture_score >= 0.3:
            candidates.append(("Texture", "Uneven-looking texture detected", r.texture_score))
        if r.dryness_score >= 0.3:
            candidates.append((
                "Dryness indicators",
                "Visual characteristics that can be associated with dryness",
                r.dryness_score,
            ))

        for category, text, raw_score in candidates:
            confidence = _confidence(raw_score)
            if confidence < min_confidence:
                continue
            observations.append(RegionObservation(
                region=label, category=category, observation=text, confidence=confidence, x=cx, y=cy,
            ))

    return analysis, observations
