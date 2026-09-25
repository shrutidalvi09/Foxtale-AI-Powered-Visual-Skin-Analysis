"""Detailed facial feature detectors (classic computer vision, no trained model).

Given the analysed photo and the detected face box, this module estimates:

  acne (pimples, pustules, blackheads, whiteheads), dark spots (acne marks vs sun/pigment spots), skin-tone
  uniformity, under-eye darkness, pore visibility, possible acne scarring, fine lines, facial hair and
  approximate facial symmetry.

Everything is measured on skin pixels after lighting gradients are divided out, and each result carries
where on the face it was found. These are estimates of what is *visible in one photo*: lighting, hair,
glasses, makeup and head angle all affect them, and none of it is a clinical assessment. Puffiness is not
assessed because it needs 3-D shape that a single flat photo does not contain.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

_eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

Box = Tuple[int, int, int, int]


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _level(score: float, cuts: Tuple[float, float, float] = (0.15, 0.35, 0.60)) -> str:
    if score < cuts[0]:
        return "minimal"
    if score < cuts[1]:
        return "mild"
    if score < cuts[2]:
        return "moderate"
    return "noticeable"


def _robust_std(v: np.ndarray) -> float:
    if v.size == 0:
        return 0.0
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


def _masked_blur(x: np.ndarray, m: np.ndarray, sigma: float) -> np.ndarray:
    return cv2.GaussianBlur(x * m, (0, 0), sigma) / np.maximum(cv2.GaussianBlur(m, (0, 0), sigma), 1e-3)


@dataclass
class _Ctx:
    """Face ROI in Lab with lighting flattened, plus zone rectangles in ROI coordinates."""
    lab: np.ndarray
    skin: np.ndarray  # bool
    L: np.ndarray
    a: np.ndarray
    b: np.ndarray
    L_flat: np.ndarray
    a_flat: np.ndarray
    b_flat: np.ndarray
    ox: int
    oy: int
    img_w: int
    img_h: int
    w: int  # face box width (px)
    h: int  # face box height
    zones: Dict[str, Tuple[int, int, int, int]]  # name -> (x0, y0, x1, y1) in ROI coords


def _zones(box: Box, ox: int, oy: int) -> Dict[str, Tuple[int, int, int, int]]:
    x, y, w, h = box

    def r(x0, y0, x1, y1):
        return (x + int(x0 * w) - ox, y + int(y0 * h) - oy, x + int(x1 * w) - ox, y + int(y1 * h) - oy)

    return {
        # forehead without the brow band at its bottom edge or the hairline at its top
        "forehead": r(0.16, 0.05, 0.84, 0.24),
        "left cheek": r(0.06, 0.48, 0.38, 0.76),
        "right cheek": r(0.62, 0.48, 0.94, 0.76),
        "nose": r(0.40, 0.36, 0.60, 0.62),  # bridge and tip, stopping above the nostrils' shadow
        "chin": r(0.32, 0.86, 0.68, 0.98),
        "upper lip": r(0.34, 0.66, 0.66, 0.73),
        "jaw": r(0.10, 0.80, 0.90, 1.00),
    }


def _build_ctx(image: np.ndarray, box: Box, skin_mask_fn) -> Optional[_Ctx]:
    x, y, w, h = box
    ih, iw = image.shape[:2]
    pad_x, pad_y = int(0.06 * w), int(0.06 * h)
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(iw, x + w + pad_x), min(ih, y + h + pad_y)
    roi = image[y0:y1, x0:x1]
    if roi.shape[0] < 60 or roi.shape[1] < 60:
        return None
    lab = cv2.cvtColor(roi.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    skin = skin_mask_fn(lab)
    if skin.sum() < 2000:
        return None
    m = skin.astype(np.float32)
    L, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
    sigma = max(8.0, w / 8.0)
    L_flat = L - _masked_blur(L, m, sigma)
    a_flat = a - _masked_blur(a, m, sigma)
    b_flat = b - _masked_blur(b, m, sigma)
    return _Ctx(lab, skin, L, a, b, L_flat, a_flat, b_flat, x0, y0, iw, ih, w, h, _zones(box, x0, y0))


def _zone_mask(ctx: _Ctx, names: List[str]) -> np.ndarray:
    m = np.zeros(ctx.skin.shape, dtype=bool)
    for n in names:
        zx0, zy0, zx1, zy1 = ctx.zones[n]
        m[max(0, zy0):max(0, zy1), max(0, zx0):max(0, zx1)] = True
    return m & ctx.skin


def _norm(ctx: _Ctx, cx: float, cy: float) -> Tuple[float, float]:
    return round((cx + ctx.ox) / ctx.img_w, 4), round((cy + ctx.oy) / ctx.img_h, 4)


def _zone_of(ctx: _Ctx, cx: float, cy: float) -> str:
    for name in ("nose", "forehead", "left cheek", "right cheek", "chin", "upper lip", "jaw"):
        x0, y0, x1, y1 = ctx.zones[name]
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return name
    return "face"


def _components(mask: np.ndarray, min_area: float, max_area: float):
    m8 = mask.astype(np.uint8)
    n, _lab, stats, cents = cv2.connectedComponentsWithStats(m8, connectivity=8)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if min_area <= area <= max_area and area / float(max(1, w * h)) >= 0.3 and max(w, h) / float(max(1, min(w, h))) <= 3.2:
            yield float(cents[i][0]), float(cents[i][1]), float(area)


def _location(counts: Dict[str, float]) -> str:
    """Plain-words location from a per-zone tally, e.g. 'around the cheeks', 'in the T-zone'."""
    total = sum(counts.values())
    if total <= 0:
        return ""
    cheeks = counts.get("left cheek", 0) + counts.get("right cheek", 0)
    tzone = counts.get("nose", 0) + counts.get("forehead", 0)
    chin = counts.get("chin", 0) + counts.get("jaw", 0)
    best = max(("cheeks", cheeks), ("tzone", tzone), ("chin", chin), key=lambda t: t[1])
    if best[1] / total < 0.45:
        return "across the face"
    return {"cheeks": "around the cheeks", "tzone": "in the T-zone", "chin": "around the chin and jaw"}[best[0]]


# ------------------------------------------------------------------ detectors

def _peaks(img: np.ndarray, mask: np.ndarray, thr: float, dark: bool) -> List[Tuple[float, float, float]]:
    """Local minima (dark=True) or maxima of a smoothed brightness map that stand out from their surroundings.

    Each candidate must beat the mean of a ring around it (7-13 px) by `thr`, which rejects the centres of large
    dark patches and the ridges next to edges: only small, isolated dots survive."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    outer = cv2.blur(img, (13, 13)) * 169.0
    inner = cv2.blur(img, (5, 5)) * 25.0
    ring = (outer - inner) / (169.0 - 25.0)
    if dark:
        cand = (img <= cv2.erode(img, k)) & mask
        contrast = ring - img
    else:
        cand = (img >= cv2.dilate(img, k)) & mask
        contrast = img - ring
    hit = cand & (contrast > thr)
    ys, xs = np.nonzero(hit)
    return [(float(x), float(y), float(contrast[y, x])) for x, y in zip(xs, ys)]


def _acne_and_pores(ctx: _Ctx, spot_info: Dict[str, Any], hair_present: bool) -> Tuple[Dict[str, Any], Dict[str, Any], List[dict]]:
    """Blackheads, whiteheads and pores from small local brightness dots; pimples/pustules come from the
    colour-based spot finder (spot_info)."""
    names = ["forehead", "left cheek", "right cheek", "nose"] + ([] if hair_present else ["chin"])
    zones_ok = _zone_mask(ctx, names)
    Ls = cv2.GaussianBlur(ctx.L_flat, (0, 0), 1.0)
    noise = max(0.6, _robust_std(Ls[zones_ok]))
    weak_thr, strong_thr = max(2.6 * noise, 3.0), max(5.0 * noise, 8.0)

    markers: List[dict] = []
    dark_pts = _peaks(Ls, zones_ok, weak_thr, dark=True)
    blackheads = [p for p in dark_pts if p[2] >= strong_thr and abs(float(ctx.a_flat[int(p[1]), int(p[0])])) < 4.0]
    whiteheads = [
        p for p in _peaks(Ls, zones_ok, max(4.0 * noise, 6.0), dark=False)
        if p[2] < 16.0 and _zone_of(ctx, p[0], p[1]) != "nose"  # nose highlights are shine, not whiteheads
    ]
    pores: Dict[str, float] = {}
    for cx, cy, _c in dark_pts:
        z = _zone_of(ctx, cx, cy)
        if z in ("nose", "left cheek", "right cheek", "forehead"):
            pores[z] = pores.get(z, 0) + 1
    pore_n = int(sum(pores.values()))

    blackheads.sort(key=lambda t: -t[2])
    whiteheads.sort(key=lambda t: -t[2])
    skin_px = max(1, int(zones_ok.sum()))
    density = pore_n / (skin_px / 10000.0)  # pore-like dots per 10k skin pixels
    pore_score = _clip01((density - 3.0) / 22.0)
    nose_area = max(1, int(_zone_mask(ctx, ["nose"]).sum()))
    nose_density = pores.get("nose", 0) / (nose_area / 10000.0)
    hotspot = ("around the nose" if pores.get("nose", 0) >= 3 and nose_density > 1.3 * max(1.0, density)
               else _location(pores))

    for cx, cy, c in blackheads[:6]:
        nx, ny = _norm(ctx, cx, cy)
        markers.append({"category": "Blackheads", "observation": "Small dark dot that looks like a blackhead",
                        "x": nx, "y": ny, "score": min(1.0, 0.4 + c / 25.0)})
    for cx, cy, c in whiteheads[:4]:
        nx, ny = _norm(ctx, cx, cy)
        markers.append({"category": "Whiteheads", "observation": "Small pale bump that looks like a whitehead",
                        "x": nx, "y": ny, "score": min(1.0, 0.35 + c / 25.0)})

    pimples = int(spot_info.get("pimples", 0))
    pustules = int(spot_info.get("pustules", 0))
    total = pimples + len(blackheads) + len(whiteheads)
    acne = {
        "pimples": pimples, "pustules": pustules, "blackheads": len(blackheads), "whiteheads": len(whiteheads),
        "total": total,
        "where": spot_info.get("where") or _location({_zone_of(ctx, c[0], c[1]): 1 for c in blackheads + whiteheads}),
    }
    pore_d = {"score": round(pore_score, 3), "level": _level(pore_score), "hotspot": hotspot, "count": pore_n}
    return acne, pore_d, markers


def _dark_spots(ctx: _Ctx, acne_marks_hint: int, hair_present: bool) -> Tuple[Dict[str, Any], List[dict]]:
    zones_ok = _zone_mask(ctx, ["forehead", "left cheek", "right cheek", "nose"] + ([] if hair_present else ["chin"]))
    ds = cv2.GaussianBlur(ctx.L_flat, (0, 0), 2.4)
    noise = max(0.5, _robust_std(ds[zones_ok]))
    w = float(ctx.w)
    cand = zones_ok & (ds < -max(3.2 * noise, 4.2))
    cand8 = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    min_area, max_area = (w / 38.0) ** 2, 0.02 * float(zones_ok.sum())
    a_s = cv2.GaussianBlur(ctx.a_flat, (0, 0), 2.0)
    b_s = cv2.GaussianBlur(ctx.b_flat, (0, 0), 2.0)
    spots: List[Tuple[float, float, float, float, float]] = []
    for cx, cy, area in _components(cand8.astype(bool), min_area, max_area):
        iy, ix = int(cy), int(cx)
        spots.append((cx, cy, area, float(a_s[iy, ix]), float(b_s[iy, ix])))
    skin_px = max(1, int(zones_ok.sum()))
    coverage = 100.0 * sum(s[2] for s in spots) / skin_px

    sun, acne_marks = [], []
    for s in spots:
        (acne_marks if s[3] >= 3.0 else sun).append(s)
    score = _clip01(0.55 * len(spots) / 7.0 + 0.45 * coverage / 1.8)
    where = _location({_zone_of(ctx, s[0], s[1]): 1 for s in spots})
    markers = []
    for cx, cy, area, ae, be in sorted(spots, key=lambda t: -t[2])[:6]:
        nx, ny = _norm(ctx, cx, cy)
        kind = "Darker patch with a reddish tint, typical of a healing acne mark" if ae >= 3.0 else "Brownish dark spot"
        markers.append({"category": "Dark spots", "observation": kind, "x": nx, "y": ny, "score": min(1.0, 0.35 + area / (3 * min_area))})
    detail = {
        "score": round(score, 3), "level": _level(score), "count": len(spots), "coverage_pct": round(coverage, 2),
        "sun_spots": len(sun), "acne_marks": len(acne_marks) + acne_marks_hint, "where": where,
    }
    return detail, markers


def _find_eyes(image: np.ndarray, box: Box) -> List[Tuple[int, int, int, int]]:
    x, y, w, h = box
    gray = cv2.cvtColor(image[y:y + int(0.58 * h), x:x + w], cv2.COLOR_BGR2GRAY)
    if gray.size == 0:
        return []
    found = _eye_cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=6, minSize=(max(14, w // 12), max(10, w // 16)))
    eyes = [(x + ex, y + ey, ew, eh) for ex, ey, ew, eh in found if ey < 0.55 * h * 0.85]
    left = [e for e in eyes if e[0] + e[2] / 2 < x + w / 2]
    right = [e for e in eyes if e[0] + e[2] / 2 >= x + w / 2]
    out = []
    if left:
        out.append(max(left, key=lambda e: e[2] * e[3]))
    if right:
        out.append(max(right, key=lambda e: e[2] * e[3]))
    return out


def _under_eye(ctx: _Ctx, image: np.ndarray, box: Box) -> Tuple[Dict[str, Any], List[dict], List[Tuple[int, int, int, int]]]:
    x, y, w, h = box
    eyes = _find_eyes(image, box)
    found = len(eyes) == 2
    if not found:  # fall back to typical frontal-face proportions
        ew, eh = int(0.2 * w), int(0.09 * h)
        eyes = [(x + int(0.30 * w) - ew // 2, y + int(0.36 * h), ew, eh), (x + int(0.70 * w) - ew // 2, y + int(0.36 * h), ew, eh)]
    deltas, markers, zones = [], [], []
    for ex, ey, ew, eh in eyes:
        bottom = ey + eh
        under = (ex + int(0.1 * ew) - ctx.ox, bottom + int(0.02 * h) - ctx.oy, ex + int(0.9 * ew) - ctx.ox, bottom + int(0.08 * h) - ctx.oy)
        ref = (ex + int(0.1 * ew) - ctx.ox, bottom + int(0.11 * h) - ctx.oy, ex + int(0.9 * ew) - ctx.ox, bottom + int(0.17 * h) - ctx.oy)
        zones.append(under)

        def med(rect):
            x0, y0, x1, y1 = [max(0, v) for v in rect]
            sub_l = ctx.L[y0:y1, x0:x1]
            sub_m = ctx.skin[y0:y1, x0:x1]
            return (float(np.median(sub_l[sub_m])), int(sub_m.sum())) if sub_m.sum() >= 40 else (None, 0)

        lu, nu = med(under)
        lr, nr = med(ref)
        if lu is None or lr is None:
            continue
        deltas.append(lr - lu)
        cx, cy = (under[0] + under[2]) / 2, (under[1] + under[3]) / 2
        markers.append((cx, cy))
    if not deltas:
        return {"score": 0.0, "level": None, "measured": False, "eyes_found": found}, [], zones
    delta = float(np.mean(deltas))
    score = _clip01((delta - 1.5) / 8.0)
    out_markers = []
    if score >= 0.15:
        for cx, cy in markers:
            nx, ny = _norm(ctx, cx, cy)
            out_markers.append({"category": "Under-eye", "observation": "Under-eye area looks darker than the cheek below it",
                                "x": nx, "y": ny, "score": 0.4 + 0.5 * score})
    return {"score": round(score, 3), "level": _level(score), "measured": True, "delta_l": round(delta, 1),
            "eyes_found": found}, out_markers, zones


def _ridge_lines(ctx: _Ctx, zone_names: List[str], horizontal_only: bool) -> List[Tuple[float, float, float]]:
    """Thin dark line segments (cx, cy, length px) inside the given zones, via a Hessian ridge filter."""
    sm = cv2.GaussianBlur(ctx.L_flat, (0, 0), 1.3)
    ixx = cv2.Sobel(sm, cv2.CV_32F, 2, 0, ksize=3)
    iyy = cv2.Sobel(sm, cv2.CV_32F, 0, 2, ksize=3)
    ixy = cv2.Sobel(sm, cv2.CV_32F, 1, 1, ksize=3)
    tmp = np.sqrt(((ixx - iyy) / 2.0) ** 2 + ixy ** 2)
    l1 = (ixx + iyy) / 2.0 + tmp  # strong positive curvature across a dark line
    l2 = (ixx + iyy) / 2.0 - tmp
    resp = np.where((l1 > 0) & (np.abs(l2) < 0.55 * l1), l1, 0.0)
    zm = _zone_mask(ctx, zone_names)
    if zm.sum() < 500:
        return []
    thr = max(np.percentile(resp[zm], 96), 3.0 * _robust_std(resp[zm]) + 1e-3)
    mask = (resp > thr) & zm
    n, _lab, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    min_len = 0.085 * ctx.w
    lines = []
    for i in range(1, n):
        ys, xs = np.where(_lab == i)
        if len(xs) < 12:
            continue
        pts = np.column_stack([xs, ys]).astype(np.float32)
        (cx, cy), (rw, rh), ang = cv2.minAreaRect(pts)
        length, thick = max(rw, rh), max(1.0, min(rw, rh))
        if length < min_len or length / thick < 4.0:
            continue
        theta = ang if rw >= rh else ang + 90.0
        theta = abs(((theta + 90) % 180) - 90)  # 0 = horizontal
        if horizontal_only and theta > 32:
            continue
        lines.append((float(cx), float(cy), float(length)))
    return lines


def _fine_lines(ctx: _Ctx, eye_zones: List[Tuple[int, int, int, int]]) -> Tuple[Dict[str, Any], List[dict]]:
    forehead = _ridge_lines(ctx, ["forehead"], horizontal_only=True)
    # crow's-feet area: just outside and below each eye, where lines fan out
    extra = {}
    for i, (x0, y0, x1, y1) in enumerate(eye_zones):
        extra[f"eye{i}"] = (int(x0 - 0.35 * (x1 - x0)), y0 - int(0.05 * ctx.h), int(x1 + 0.35 * (x1 - x0)), y1 + int(0.03 * ctx.h))
    ctx.zones.update(extra)
    eyes = _ridge_lines(ctx, list(extra.keys()), horizontal_only=False)
    def merge(segs: List[Tuple[float, float, float]], tol: float) -> List[Tuple[float, float, float]]:
        """Segments on nearly the same row belong to one crease: keep the longest per row band."""
        kept: List[Tuple[float, float, float]] = []
        for seg in sorted(segs, key=lambda t: -t[2]):
            if all(abs(seg[1] - k[1]) > tol for k in kept):
                kept.append(seg)
        return kept

    forehead = merge(forehead, 0.025 * ctx.h)
    eyes = merge(eyes, 0.02 * ctx.h)[:4]
    total_len = sum(l[2] for l in forehead) + sum(l[2] for l in eyes)
    count = len(forehead) + len(eyes)
    score = _clip01(0.5 * count / 6.0 + 0.5 * total_len / (ctx.w * 1.2))
    where = []
    if forehead:
        where.append("forehead")
    if eyes:
        where.append("around the eyes")
    markers = []
    for cx, cy, ln in sorted(forehead + eyes, key=lambda t: -t[2])[:3]:
        nx, ny = _norm(ctx, cx, cy)
        markers.append({"category": "Fine lines", "observation": "Thin line or crease in the skin surface",
                        "x": nx, "y": ny, "score": min(1.0, 0.35 + ln / (0.3 * ctx.w))})
    return {"score": round(score, 3), "level": _level(score), "count": count, "where": " and ".join(where)}, markers


def _facial_hair(ctx: _Ctx) -> Dict[str, Any]:
    cheeks = ctx.L[_zone_mask(ctx, ["left cheek", "right cheek"])]
    if cheeks.size < 200:
        return {"level": None, "measured": False}
    ref = float(np.median(cheeks))
    hair_zones = ["upper lip", "chin", "jaw"]
    fracs = []
    for name in hair_zones:
        x0, y0, x1, y1 = [max(0, v) for v in ctx.zones[name]]
        sub = ctx.L[y0:y1, x0:x1]
        if sub.size < 100:
            continue
        hp = sub - cv2.GaussianBlur(sub, (0, 0), 2.0)
        dark = (sub < ref - 16) & (np.abs(hp) > 2.0)  # dark AND speckled, unlike a smooth shadow
        fracs.append(float(dark.mean()))
    if not fracs:
        return {"level": None, "measured": False}
    f = max(fracs)
    level = "none" if f < 0.04 else "light" if f < 0.12 else "visible"
    return {"level": level, "fraction": round(f, 3), "measured": True}


def _symmetry(ctx: _Ctx, image: np.ndarray, box: Box, found_eyes: bool) -> Dict[str, Any]:
    x, y, w, h = box
    x0, x1 = max(0, x + int(0.04 * w) - ctx.ox), min(ctx.L.shape[1], x + int(0.96 * w) - ctx.ox)
    y0, y1 = max(0, y + int(0.08 * h) - ctx.oy), min(ctx.L.shape[0], y + int(0.98 * h) - ctx.oy)
    face = ctx.L_flat[y0:y1, x0:x1]
    if face.shape[0] < 40 or face.shape[1] < 40:
        return {"pct": None, "measured": False}
    face = cv2.resize(face, (128, 128), interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(face, (0, 0), 1.6)
    gx, gy = cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)
    mag = cv2.GaussianBlur(np.sqrt(gx * gx + gy * gy), (0, 0), 2.0)
    mirror = mag[:, ::-1]
    best = -1.0
    for shift in range(-8, 9):  # the box may be a little off the true midline
        a = np.roll(mirror, shift, axis=1)
        aa, bb = a[:, 16:112].ravel(), mag[:, 16:112].ravel()
        aa, bb = aa - aa.mean(), bb - bb.mean()
        denom = float(np.sqrt((aa * aa).sum() * (bb * bb).sum())) + 1e-6
        best = max(best, float((aa * bb).sum() / denom))
    if best < 0.12:  # too little structure to compare (flat lighting, heavy blur)
        return {"pct": None, "measured": False, "raw_ncc": round(best, 3)}
    pct = 60.0 + 39.0 * _clip01((best - 0.12) / 0.68)
    return {"pct": int(round(pct)), "measured": True, "raw_ncc": round(best, 3), "eyes_found": found_eyes}


def _uniformity(ctx: _Ctx, evenness_score: float) -> Dict[str, Any]:
    """Skin-tone uniformity: how alike the colour is across the face and within regions."""
    meds = []
    for name in ("forehead", "left cheek", "right cheek", "nose", "chin"):
        m = _zone_mask(ctx, [name])
        if m.sum() >= 150:
            meds.append((float(np.median(ctx.L[m])), float(np.median(ctx.a[m])), float(np.median(ctx.b[m]))))
    if len(meds) < 3:
        return {"pct": None, "measured": False}
    arr = np.array(meds)
    spread = float(np.max(np.sqrt(((arr[:, None, :] - arr[None, :, :]) ** 2).sum(-1))))  # largest Lab distance between zones
    region_term = _clip01((spread - 3.0) / 12.0)
    unevenness = _clip01(0.55 * evenness_score + 0.45 * region_term)
    pct = int(round(100 * (1 - 0.8 * unevenness)))
    return {"pct": pct, "measured": True, "region_spread": round(spread, 1)}


def _scars(marks: int, dark_acne_marks: int, texture_score: float) -> Dict[str, Any]:
    score = _clip01(0.5 * (marks + dark_acne_marks) / 6.0 + 0.5 * max(0.0, texture_score - 0.15) / 0.5)
    return {"score": round(score, 3), "possible": bool(score >= 0.3), "level": _level(score)}


# ---------------------------------------------------------------- entry point

def compute_features(
    image: np.ndarray,
    box: Box,
    skin_mask_fn,
    spot_info: Dict[str, Any],
    hotspots: Dict[str, str],
    evenness_score: float,
    texture_score: float,
) -> Tuple[Dict[str, Any], List[dict]]:
    """Returns (detail dict, extra marker observations). `spot_info` carries the pimple/pustule counts already found
    by the colour-based spot finder; `hotspots` the redness / dryness / oiliness locations."""
    ctx = _build_ctx(image, box, skin_mask_fn)
    if ctx is None:
        return {}, []
    hair = _facial_hair(ctx)
    acne, pores, m1 = _acne_and_pores(ctx, spot_info, hair_present=hair.get("level") in ("light", "visible"))
    dark, m2 = _dark_spots(ctx, int(spot_info.get("marks", 0)), hair.get("level") in ("light", "visible"))
    under, m3, eye_zones = _under_eye(ctx, image, box)
    lines, m4 = _fine_lines(ctx, eye_zones)
    detail = {
        "acne": acne,
        "dark_spots": dark,
        "uniformity": _uniformity(ctx, evenness_score),
        "under_eye": under,
        "pores": pores,
        "scars": _scars(int(spot_info.get("marks", 0)), dark["acne_marks"], texture_score),
        "fine_lines": lines,
        "sun_spots": {"count": dark["sun_spots"], "detected": dark["sun_spots"] >= 2, "where": dark["where"]},
        "facial_hair": hair,
        "symmetry": _symmetry(ctx, image, box, bool(under.get("eyes_found"))),
        "hotspots": hotspots,
    }
    return detail, m1 + m2 + m3 + m4
