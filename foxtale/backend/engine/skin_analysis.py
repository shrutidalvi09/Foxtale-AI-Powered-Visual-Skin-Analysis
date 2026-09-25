"""Classic-computer-vision skin analysis (engine v2).

Everything is phrased as a *visual observation*, never a diagnosis. There is
no trained model here -- these are transparent image-statistics measured on
skin pixels only:

  1. A per-region skin mask (chroma + luminance gates in CIELAB) drops eyes,
     brows, hair, lips and deep shadow so they are not mistaken for skin
     features.
  2. Slow illumination gradients are divided out (masked Gaussian), so a
     shadow across one cheek is not read as redness or blotchiness.
  3. Measurements are made in CIELAB, which is closer to how colour and
     brightness are perceived than raw RGB/HSV:
       - spots      : compact patches redder than the surrounding skin
       - redness    : a* excess (local + overall) relative to the face
       - texture    : mid-frequency luminance energy (pores/roughness)
       - dryness    : fine-scale roughness + low chroma + patchiness
       - oiliness   : fraction of bright, low-chroma (specular) pixels
       - evenness   : low-frequency spread of luminance/colour
  4. Each is mapped to a 0-1 score, a level (minimal..noticeable) and a
     confidence that depends on how much usable skin was seen. A weighted
     0-100 overall score is derived from the scores.

The thresholds are heuristics tuned on synthetic and typical webcam images;
they are not clinically validated. Raw measurements are stored with the scan
so the report can show real numbers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from engine.calibration import CalibrationProfile
from engine.image_processing import FaceRegions
from engine.schemas import CategoryResult, RegionObservation, SkinAnalysis

ENGINE_VERSION = 2

REGION_LABELS = {
    "forehead": "FOREHEAD",
    "left cheek": "LEFT CHEEK",
    "right cheek": "RIGHT CHEEK",
    "nose": "NOSE",
    "chin": "CHIN",
}

# Weights of each category in the 0-100 overall score (sum = 1).
SCORE_WEIGHTS = {
    "spots": 0.28,
    "redness": 0.22,
    "texture": 0.16,
    "dryness": 0.12,
    "oiliness": 0.08,
    "evenness": 0.14,
}
SCORE_STRENGTH = 0.85  # so even the worst measured skin keeps a non-zero score

MIN_SKIN_FRACTION = 0.12  # regions with less usable skin than this are skipped
MAX_SPOT_MARKERS = 12  # per-photo cap on individually marked spots

# Per-category level thresholds on the 0-1 score.
LEVEL_CUTS = (0.15, 0.35, 0.60)

REF_A_ABS = 13.0  # typical a* of healthy skin; absolute redness is measured above this


def _level_from_score(score: float) -> str:
    if score < LEVEL_CUTS[0]:
        return "minimal"
    if score < LEVEL_CUTS[1]:
        return "mild"
    if score < LEVEL_CUTS[2]:
        return "moderate"
    return "noticeable"


def score_label(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Fair"
    return "Needs care"


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


# ----------------------------------------------------------------- helpers

def _masked_blur(x: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    num = cv2.GaussianBlur(x * mask, (0, 0), sigma)
    den = cv2.GaussianBlur(mask, (0, 0), sigma)
    return num / np.maximum(den, 1e-3)


def _robust_std(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    med = np.median(values)
    return float(1.4826 * np.median(np.abs(values - med)))


def _to_lab(region_bgr: np.ndarray) -> np.ndarray:
    """float32 CIELAB: L in 0-100, a*/b* in their natural signed units."""
    return cv2.cvtColor(region_bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)


def skin_mask(lab: np.ndarray) -> np.ndarray:
    """Boolean mask of pixels that look like skin (drops eyes, brows, hair,
    lips, nostril/deep shadow). Gates are deliberately broad so different
    skin tones and lighting are kept, then tightened around the region's own
    median luminance."""
    L, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
    broad = (L > 12) & (L < 97) & (a > 2) & (a < 38) & (b > 2) & (b < 52)
    if broad.sum() < 30:
        return np.zeros(L.shape, dtype=bool)
    med_l = float(np.median(L[broad]))
    mask = broad & (L > med_l - 26) & (L < med_l + 32)

    m8 = mask.astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    m8 = cv2.morphologyEx(m8, cv2.MORPH_OPEN, k)
    m8 = cv2.morphologyEx(m8, cv2.MORPH_CLOSE, k)
    return m8.astype(bool)


# ------------------------------------------------------------ measurements

@dataclass
class Spot:
    cx: float  # crop pixel coordinates
    cy: float
    area: float
    contrast: float  # a* excess over local skin


@dataclass
class RegionMetrics:
    region: str
    skin_fraction: float
    skin_pixels: int
    mean_a: float
    spots: List[Spot] = field(default_factory=list)
    spot_area_pct: float = 0.0
    redness_local_pct: float = 0.0
    redness_excess_a: float = 0.0
    texture_std: float = 0.0
    dryness_rough: float = 0.0
    dryness_low_chroma: float = 0.0
    dryness_patchiness: float = 0.0
    shine_pct: float = 0.0
    tone_std_l: float = 0.0
    tone_std_ab: float = 0.0
    # 0-1 scores
    spot_score: float = 0.0
    redness_score: float = 0.0
    texture_score: float = 0.0
    dryness_score: float = 0.0
    oiliness_score: float = 0.0
    evenness_score: float = 0.0

    @property
    def usable(self) -> bool:
        return self.skin_fraction >= MIN_SKIN_FRACTION and self.skin_pixels >= 300

    def region_score(self) -> int:
        weighted = (
            SCORE_WEIGHTS["spots"] * self.spot_score
            + SCORE_WEIGHTS["redness"] * self.redness_score
            + SCORE_WEIGHTS["texture"] * self.texture_score
            + SCORE_WEIGHTS["dryness"] * self.dryness_score
            + SCORE_WEIGHTS["oiliness"] * self.oiliness_score
            + SCORE_WEIGHTS["evenness"] * self.evenness_score
        )
        return int(round(100 * (1 - SCORE_STRENGTH * weighted)))


def _find_spots(a_flat: np.ndarray, mask: np.ndarray, area_total: int) -> Tuple[List[Spot], float]:
    """Compact patches noticeably redder than the local skin."""
    a_s = cv2.GaussianBlur(a_flat, (0, 0), 1.0)
    vals = a_s[mask]
    if vals.size < 100:
        return [], 0.0
    med = float(np.median(vals))
    sigma = max(0.9, _robust_std(vals))
    excess = a_s - med
    cand = ((excess / sigma) > 2.8) & (excess > 3.0) & mask
    cand8 = cand.astype(np.uint8)
    cand8 = cv2.morphologyEx(cand8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

    n, _labels, stats, centroids = cv2.connectedComponentsWithStats(cand8, connectivity=8)
    min_area = max(6, 0.0005 * area_total)
    max_area = 0.03 * area_total
    spots: List[Spot] = []
    total_area = 0.0
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (min_area <= area <= max_area):
            continue
        if area / float(max(1, w * h)) < 0.35 or max(w, h) / float(max(1, min(w, h))) > 3.0:
            continue
        cx, cy = centroids[i]
        contrast = float(excess[int(round(cy)), int(round(cx))]) if excess.size else 0.0
        spots.append(Spot(cx=float(cx), cy=float(cy), area=float(area), contrast=contrast))
        total_area += float(area)
    return spots, total_area


def measure_region(
    name: str,
    crop_bgr: np.ndarray,
    ref_a: float,
    calibration: Optional[CalibrationProfile],
) -> RegionMetrics:
    h, w = crop_bgr.shape[:2]
    empty = RegionMetrics(region=name, skin_fraction=0.0, skin_pixels=0, mean_a=0.0)
    if h < 16 or w < 16:
        return empty

    lab = _to_lab(crop_bgr)
    mask_b = skin_mask(lab)
    n_skin = int(mask_b.sum())
    if n_skin == 0:
        return empty
    mask = mask_b.astype(np.float32)
    L, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
    s = float(min(h, w))
    m = RegionMetrics(
        region=name, skin_fraction=n_skin / float(h * w), skin_pixels=n_skin, mean_a=float(np.median(a[mask_b])),
    )
    if not m.usable:
        return m

    # 1) divide out illumination gradients / skin-tone shading
    big = max(6.0, s / 4.0)
    L_flat = L - _masked_blur(L, mask, big)
    a_flat = a - _masked_blur(a, mask, big) + m.mean_a

    # 2) spots
    spots, spot_area = _find_spots(a_flat, mask_b, h * w)
    m.spots = spots
    m.spot_area_pct = 100.0 * spot_area / max(1, n_skin)
    density = len(spots) / max(1.0, n_skin / 10000.0)  # spots per 10k skin pixels
    m.spot_score = _clip01(0.65 * density / 5.0 + 0.35 * m.spot_area_pct / 3.0)

    spot_px = np.zeros((h, w), dtype=bool)
    if spots:
        for sp in spots:
            cv2.circle(spot_px.view(np.uint8), (int(sp.cx), int(sp.cy)), int(np.sqrt(sp.area / np.pi)) + 2, 1, -1)
    clean = mask_b & ~spot_px
    if clean.sum() < 100:
        clean = mask_b

    # 3) redness: how much redder than the face's overall skin, locally and overall
    a_smooth = cv2.GaussianBlur(a, (0, 0), max(1.5, s / 30.0))
    excess = a_smooth[clean] - ref_a
    m.redness_local_pct = 100.0 * float(np.mean(excess > 3.0))
    m.redness_excess_a = float(np.median(a[clean]) - REF_A_ABS)
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    hh, ss, vv = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    red_ratio = float(np.mean((((hh <= 10) | (hh >= 165)) & (ss > 60) & (vv > 60))[mask_b]))
    baseline = calibration.red_ratio_baseline if calibration else 0.0
    hsv_component = _clip01(max(0.0, red_ratio - baseline) / 0.35)
    m.redness_score = _clip01(
        0.50 * _clip01(m.redness_local_pct / 40.0)
        + 0.35 * _clip01(m.redness_excess_a / 8.0)
        + 0.15 * hsv_component
    )

    # 4) texture: band-pass luminance energy (pores / roughness), noise-robust
    lo = cv2.GaussianBlur(L, (0, 0), max(1.0, s / 70.0))
    hi = cv2.GaussianBlur(L, (0, 0), max(2.0, s / 22.0))
    band = (lo - hi)[clean]
    m.texture_std = _robust_std(band) if band.size else 0.0
    m.texture_score = _clip01((m.texture_std - 0.5) / 2.6)

    # 5) dryness: fine-scale flaking + dull (low chroma) + patchy brightness
    fine = (L - cv2.GaussianBlur(L, (0, 0), 1.0))[clean]
    m.dryness_rough = _robust_std(fine) if fine.size else 0.0
    chroma = np.sqrt(a * a + b * b)
    sat_ref = (calibration.saturation_baseline / 255.0 * 60.0) if calibration else 24.0
    m.dryness_low_chroma = float(np.mean(chroma[clean] < max(10.0, sat_ref * 0.55)))
    block = max(4, int(s // 8))
    patch_means = [
        float(np.mean(L[yy:yy + block, xx:xx + block][mask_b[yy:yy + block, xx:xx + block]]))
        for yy in range(0, h - block + 1, block)
        for xx in range(0, w - block + 1, block)
        if mask_b[yy:yy + block, xx:xx + block].mean() > 0.6
    ]
    m.dryness_patchiness = float(np.std(patch_means)) if len(patch_means) >= 4 else 0.0
    m.dryness_score = _clip01(
        0.25 * _clip01((m.dryness_rough - 1.0) / 2.5)  # fine scale is partly camera noise: low weight
        + 0.35 * _clip01(m.dryness_low_chroma / 0.5)
        + 0.40 * _clip01(m.dryness_patchiness / 8.0)
    )

    # 6) oiliness: bright, low-chroma (specular) pixels
    med_l = float(np.median(L[mask_b]))
    shine = mask_b & (L > med_l + 10) & (chroma < np.median(chroma[mask_b]) * 1.05)
    m.shine_pct = 100.0 * float(shine.sum()) / max(1, n_skin)
    m.oiliness_score = _clip01(m.shine_pct / 12.0)

    # 7) tone evenness: low-frequency spread of luminance and colour
    mid = max(3.0, s / 10.0)
    L_lo = _masked_blur(L_flat, mask, mid)[clean]
    a_lo = _masked_blur(a_flat, mask, mid)[clean]
    b_lo = _masked_blur(b, mask, mid)[clean]
    m.tone_std_l = float(np.std(L_lo)) if L_lo.size else 0.0
    m.tone_std_ab = float(0.5 * (np.std(a_lo) + np.std(b_lo))) if a_lo.size else 0.0
    m.evenness_score = _clip01(0.5 * m.tone_std_l / 4.0 + 0.5 * m.tone_std_ab / 2.5)

    return m


# ---------------------------------------------------------------- pipeline

def _confidence(score: float, coverage: float) -> float:
    return round(min(0.95, max(0.35, 0.50 + 0.33 * coverage + 0.12 * min(score, 1.0))), 2)


def _weighted_mean(values: List[Tuple[float, int]]) -> float:
    total = sum(w for _, w in values)
    if total <= 0:
        return 0.0
    return sum(v * w for v, w in values) / total


def analyze_face(
    regions: FaceRegions,
    calibration: Optional[CalibrationProfile] = None,
    min_confidence: float = 0.0,
) -> Tuple[SkinAnalysis, List[RegionObservation]]:
    """Run the full analysis pipeline.

    `min_confidence` filters which per-region observations are surfaced (a
    GUI-only "advanced" setting; the summary cards always reflect every
    usable region).
    """
    # Face-wide reference a* from a first, cheap pass over the skin pixels.
    a_samples = []
    for crop in regions.crops.values():
        if crop.shape[0] < 16 or crop.shape[1] < 16:
            continue
        lab = _to_lab(crop)
        mk = skin_mask(lab)
        if mk.sum() >= 100:
            a_samples.append(lab[:, :, 1][mk])
    ref_a = float(np.median(np.concatenate(a_samples))) if a_samples else REF_A_ABS

    measured = [measure_region(n, c, ref_a, calibration) for n, c in regions.crops.items()]
    usable = [m for m in measured if m.usable]
    weights = [(m, m.skin_pixels) for m in usable]

    def avg(attr: str) -> float:
        return _weighted_mean([(getattr(m, attr), wt) for m, wt in weights])

    spot_s, red_s, tex_s = avg("spot_score"), avg("redness_score"), avg("texture_score")
    dry_s, oil_s, eve_s = avg("dryness_score"), avg("oiliness_score"), avg("evenness_score")
    coverage = float(np.mean([m.skin_fraction for m in usable])) if usable else 0.0
    total_spots = int(sum(len(m.spots) for m in usable))

    def cat(score: float, count: Optional[int] = None) -> CategoryResult:
        return CategoryResult(level=_level_from_score(score), confidence=_confidence(score, coverage), count=count)

    overall = int(round(100 * (1 - SCORE_STRENGTH * (
        SCORE_WEIGHTS["spots"] * spot_s + SCORE_WEIGHTS["redness"] * red_s
        + SCORE_WEIGHTS["texture"] * tex_s + SCORE_WEIGHTS["dryness"] * dry_s
        + SCORE_WEIGHTS["oiliness"] * oil_s + SCORE_WEIGHTS["evenness"] * eve_s
    )))) if usable else None

    region_scores = {
        m.region: {
            "score": m.region_score(),
            "skin_pct": round(100 * m.skin_fraction, 1),
            "spots": len(m.spots),
            "spot_score": round(m.spot_score, 3),
            "redness": round(m.redness_score, 3),
            "texture": round(m.texture_score, 3),
            "dryness": round(m.dryness_score, 3),
            "oiliness": round(m.oiliness_score, 3),
            "evenness": round(m.evenness_score, 3),
        }
        for m in usable
    }

    def mean_of(attr: str) -> float:
        return round(avg(attr), 3)

    metrics = {
        "skin_coverage_pct": round(100 * coverage, 1),
        "regions_analyzed": len(usable),
        "reference_a": round(ref_a, 2),
        "spot_area_pct": mean_of("spot_area_pct"),
        "redness_local_pct": mean_of("redness_local_pct"),
        "redness_excess_a": mean_of("redness_excess_a"),
        "texture_std": mean_of("texture_std"),
        "dryness_rough": mean_of("dryness_rough"),
        "dryness_low_chroma_pct": round(100 * avg("dryness_low_chroma"), 1),
        "shine_pct": mean_of("shine_pct"),
        "tone_std_l": mean_of("tone_std_l"),
        "tone_std_ab": mean_of("tone_std_ab"),
    }

    analysis = SkinAnalysis(
        acne_like_spots=cat(spot_s, total_spots),
        redness=cat(red_s),
        texture=cat(tex_s),
        dryness_indicators=cat(dry_s),
        oiliness=cat(oil_s),
        tone_evenness=cat(eve_s),
        overall_score=overall,
        region_scores=region_scores,
        metrics=metrics,
        engine_version=ENGINE_VERSION,
    )

    return analysis, _build_observations(regions, usable, min_confidence)


def _build_observations(
    regions: FaceRegions, usable: List[RegionMetrics], min_confidence: float,
) -> List[RegionObservation]:
    img_w, img_h = regions.image_size
    observations: List[RegionObservation] = []
    spot_markers: List[Tuple[float, RegionObservation]] = []

    def add(label, category, text, score, cx, cy, coverage, bucket=None):
        confidence = _confidence(score, coverage)
        if confidence < min_confidence:
            return
        obs = RegionObservation(region=label, category=category, observation=text,
                                confidence=confidence, x=cx, y=cy)
        if bucket is not None:
            bucket.append((score, obs))
        else:
            observations.append(obs)

    for m in usable:
        cx, cy = regions.centers[m.region]
        label = REGION_LABELS.get(m.region, m.region.upper())
        cov = m.skin_fraction
        origin = regions.origins.get(m.region)

        if m.spots and m.spot_score >= 0.08:
            ranked = sorted(m.spots, key=lambda sp: -sp.contrast)
            if origin and img_w and img_h:
                for sp in ranked[:4]:
                    add(label, "Acne-like spots",
                        f"Small reddish spot (about {sp.contrast:.0f} units redder than nearby skin)",
                        min(1.0, 0.3 + sp.contrast / 14.0),
                        (origin[0] + sp.cx) / img_w, (origin[1] + sp.cy) / img_h, cov, bucket=spot_markers)
            else:
                add(label, "Acne-like spots", f"{len(m.spots)} visible spot(s) detected", m.spot_score, cx, cy, cov)
        if m.redness_score >= 0.22:
            detail = (f" ({m.redness_local_pct:.0f}% of it redder than the rest of the face)"
                      if m.redness_local_pct >= 5 else "")
            add(label, "Redness", f"Visible redness around the {m.region} area{detail}", m.redness_score, cx, cy, cov)
        if m.texture_score >= 0.30:
            add(label, "Texture", "Uneven-looking texture detected", m.texture_score, cx, cy, cov)
        if m.dryness_score >= 0.32:
            add(label, "Dryness indicators",
                "Visual characteristics that can be associated with dryness", m.dryness_score, cx, cy, cov)
        if m.oiliness_score >= 0.35:
            add(label, "Oiliness", f"Shiny areas detected ({m.shine_pct:.0f}% of skin reflecting light)",
                m.oiliness_score, cx, cy, cov)
        if m.evenness_score >= 0.40:
            add(label, "Tone evenness", "Noticeable tone variation across this area", m.evenness_score, cx, cy, cov)

    spot_markers.sort(key=lambda t: -t[0])
    observations.extend(obs for _, obs in spot_markers[:MAX_SPOT_MARKERS])
    return observations


def run_engine_self_test(patch: np.ndarray) -> None:
    """Exercises the measurement pipeline on a single image patch -- used by
    the Privacy Dashboard's offline-verification check, which runs this
    with network access blocked to prove the analysis pipeline never
    attempts to phone home."""
    measure_region("patch", patch, REF_A_ABS, None)
