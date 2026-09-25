"""Turns a SkinAnalysis (+ its stored raw measurements) into the plain-language
content of a face analysis report. Shared by the in-app Analysis page and the
PDF so both always say the same thing. Everything is worded as a visible
observation, never a diagnosis.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.schemas import LEVEL_SCORE, CategoryResult, RegionObservation, SkinAnalysis
from engine.skin_analysis import score_label

LEVEL_MEANING = {
    "minimal": "Nothing notable visible",
    "mild": "Slightly visible",
    "moderate": "Clearly visible",
    "noticeable": "Prominent",
}

CATEGORY_ORDER = [
    ("Acne-like spots", "Acne-like Spots", "acne_like_spots"),
    ("Redness", "Visible Redness", "redness"),
    ("Texture", "Skin Texture", "texture"),
    ("Dryness indicators", "Dryness Indicators", "dryness_indicators"),
    ("Oiliness", "Oiliness / Shine", "oiliness"),
    ("Tone evenness", "Tone Evenness", "tone_evenness"),
]

WHAT_IT_MEANS = {
    "Acne-like spots": "Small, compact patches that look redder than the skin around them.",
    "Redness": "How much of the skin looks redder than your own average skin tone.",
    "Texture": "How rough or bumpy the skin surface looks at pore scale.",
    "Dryness indicators": "Dull, low-colour, patchy or fine-flaky looking areas.",
    "Oiliness": "The share of skin that reflects light like a shiny, oily surface.",
    "Tone evenness": "How much brightness and colour vary from place to place.",
}


@dataclass
class CategoryRow:
    key: str
    label: str
    level: str
    confidence: float
    measurement: str
    meaning: str


@dataclass
class RegionRow:
    name: str
    score: int
    concern: str  # main concern in plain words, or "No notable observations"


def _measurement(key: str, a: SkinAnalysis) -> str:
    m = a.metrics or {}
    if not m:
        return "Measured from the visible skin in each region."
    if key == "Acne-like spots":
        n = a.acne_like_spots.count or 0
        return f"{n} spot(s) found, covering about {m.get('spot_area_pct', 0):.1f}% of skin"
    if key == "Redness":
        return f"About {m.get('redness_local_pct', 0):.0f}% of skin looks redder than your average tone"
    if key == "Texture":
        return f"Surface roughness index {m.get('texture_std', 0):.1f} (smoother is lower)"
    if key == "Dryness indicators":
        return f"{m.get('dryness_low_chroma_pct', 0):.0f}% of skin looks dull or low in colour"
    if key == "Oiliness":
        return f"About {m.get('shine_pct', 0):.1f}% of skin is shiny"
    if key == "Tone evenness":
        return f"Brightness varies by {m.get('tone_std_l', 0):.1f}, colour by {m.get('tone_std_ab', 0):.1f}"
    return ""


def category_rows(analysis: SkinAnalysis) -> List[CategoryRow]:
    rows = []
    for key, label, attr in CATEGORY_ORDER:
        result: Optional[CategoryResult] = getattr(analysis, attr, None)
        if result is None:
            continue
        rows.append(CategoryRow(
            key=key, label=label, level=result.level, confidence=result.confidence,
            measurement=_measurement(key, analysis), meaning=WHAT_IT_MEANS[key],
        ))
    return rows


def _main_concern(scores: dict) -> str:
    names = {
        "spot_score": "spots", "redness": "redness", "texture": "texture",
        "dryness": "dryness", "oiliness": "shine", "evenness": "uneven tone",
    }
    best = max(names, key=lambda k: scores.get(k, 0))
    if scores.get(best, 0) < 0.2:
        return "No notable observations"
    return f"Mostly {names[best]}"


def region_rows(analysis: SkinAnalysis) -> List[RegionRow]:
    rows = [
        RegionRow(name=name.title(), score=int(v.get("score", 0)), concern=_main_concern(v))
        for name, v in (analysis.region_scores or {}).items()
    ]
    return sorted(rows, key=lambda r: r.score)  # weakest region first


def priority_categories(analysis: SkinAnalysis, limit: int = 3) -> List[CategoryRow]:
    rows = [r for r in category_rows(analysis) if r.level != "minimal"]
    return sorted(rows, key=lambda r: -LEVEL_SCORE[r.level])[:limit]


def overall_summary(analysis: SkinAnalysis) -> str:
    if analysis.overall_score is None:
        return "This scan was saved by an earlier version of Foxtale, so it has no overall score."
    label = score_label(analysis.overall_score).lower()
    text = f"Your skin looks {label} overall ({analysis.overall_score}/100)."
    top = priority_categories(analysis, 2)
    if top:
        bits = " and ".join(f"{r.label.lower()} ({r.level})" for r in top)
        text += f" The main things visible are {bits}."
    else:
        text += " No category stood out in this photo."
    regions = region_rows(analysis)
    if len(regions) >= 2 and regions[0].score < regions[-1].score - 4:
        text += (f" The {regions[0].name.lower()} showed the most to look after; "
                 f"the {regions[-1].name.lower()} looked clearest.")
    return text


def compare_with_previous(current: SkinAnalysis, previous: Optional[SkinAnalysis]) -> List[str]:
    """Plain-language lines describing what changed since the previous scan."""
    if previous is None:
        return []
    lines = []
    if current.overall_score is not None and previous.overall_score is not None:
        delta = current.overall_score - previous.overall_score
        if abs(delta) >= 3:
            direction = "up" if delta > 0 else "down"
            lines.append(f"Overall score is {direction} {abs(delta)} points since your last scan "
                         f"({previous.overall_score} to {current.overall_score}).")
        else:
            lines.append("Overall score is about the same as your last scan.")
    for _key, label, attr in CATEGORY_ORDER:
        cur, prev = getattr(current, attr, None), getattr(previous, attr, None)
        if cur is None or prev is None:
            continue
        d = LEVEL_SCORE[cur.level] - LEVEL_SCORE[prev.level]
        if d < 0:
            lines.append(f"{label} looks better: {prev.level} to {cur.level}.")
        elif d > 0:
            lines.append(f"{label} looks stronger: {prev.level} to {cur.level}.")
    return lines


METHOD_STEPS: List[Tuple[str, str]] = [
    ("Face and region finding", "A face detector locates one face; it is split into forehead, both cheeks, nose and chin."),
    ("Skin isolation", "Eyes, brows, hair, lips and deep shadow are excluded so only skin pixels are measured."),
    ("Lighting correction", "Slow brightness gradients (a shadow on one cheek) are divided out before measuring."),
    ("Measurement", "Colour and brightness are measured in the CIELAB colour space for spots, redness, texture, dryness, shine and tone evenness."),
    ("Scoring", "Each measurement becomes a 0-1 score, a level and a confidence; a weighted 0-100 overall score summarizes them."),
]

LIMITATIONS = (
    "This is an estimate of what is visible in one photo. It can be affected by lighting, camera quality, "
    "makeup, facial hair, filters and head angle, and it is not clinically validated. Levels describe how "
    "visible a feature is, not its cause."
)

# Score weights, shown in the report so the overall score is traceable.
SCORE_EXPLANATION = (
    "Overall score = 100 minus weighted visible concerns: spots 28%, redness 22%, texture 16%, "
    "tone evenness 14%, dryness 12%, oiliness 8%, then a little more for dark spots, blackheads, visible pores, "
    "under-eye darkness and fine lines."
)


def category_areas(regions: List[RegionObservation], category: str) -> str:
    matches = [r for r in regions if r.category == category]
    if not matches:
        return "Not flagged in a specific area"
    seen: Dict[str, None] = {}
    for r in matches:
        seen[r.region.title()] = None
    return ", ".join(seen)


# ------------------------------------------------------------ detailed findings

LEVEL_WORD = {"minimal": "Minimal", "mild": "Mild", "moderate": "Moderate", "noticeable": "High"}
TEXTURE_WORD = {"minimal": "Smooth", "mild": "Slightly uneven", "moderate": "Uneven", "noticeable": "Rough"}


def _count_level(n: int) -> str:
    return "minimal" if n == 0 else "mild" if n <= 3 else "moderate" if n <= 8 else "noticeable"


def _max_level(a: str, b: str) -> str:
    return a if LEVEL_SCORE[a] >= LEVEL_SCORE[b] else b


def _with_where(text: str, where: str, level: str) -> str:
    return f"{text} {where}" if where and level != "minimal" else text


def detail_rows(analysis: SkinAnalysis) -> List[Dict[str, object]]:
    """The findings table: one row per thing the camera looks for, in plain words, with where it was found."""
    d = analysis.detail or {}
    hot = d.get("hotspots") or {}
    rows: List[Dict[str, object]] = []

    def row(key, icon, category, headline, level, note="", measured=True, where=""):
        rows.append({"key": key, "icon": icon, "category": category, "headline": headline, "level": level,
                     "note": note, "measured": measured, "where": where})

    def unmeasured(key, icon, category, why="Scan again with the latest version to measure this."):
        row(key, icon, category, f"{category}: not measured", None, why, measured=False)

    # acne
    acne = d.get("acne")
    if acne:
        level = _max_level(analysis.acne_like_spots.level, _count_level(acne["total"]))
        parts = []
        if acne["pimples"]:
            parts.append(f"{acne['pimples']} pimple{'s' if acne['pimples'] != 1 else ''}"
                         + (f" ({acne['pustules']} pustule-like)" if acne["pustules"] else ""))
        if acne["blackheads"]:
            parts.append(f"{acne['blackheads']} blackhead{'s' if acne['blackheads'] != 1 else ''}")
        if acne["whiteheads"]:
            parts.append(f"{acne['whiteheads']} whitehead{'s' if acne['whiteheads'] != 1 else ''}")
        row("acne", "🔴", "Acne", f"Acne spots: {acne['total']} detected", level,
            ", ".join(parts) or "No pimples, whiteheads or blackheads spotted.", where=acne.get("where", ""))
    else:
        n = analysis.acne_like_spots.count or 0
        row("acne", "🔴", "Acne", f"Acne spots: {n} detected", analysis.acne_like_spots.level, "Pimple-like spots only.")

    # dark spots
    ds = d.get("dark_spots")
    if ds:
        note = f"{ds['count']} spot{'s' if ds['count'] != 1 else ''} covering about {ds['coverage_pct']:.1f}% of the skin"
        if ds["count"]:
            note += f" ({ds['acne_marks']} look like acne marks, {ds['sun_spots']} like sun or pigment spots)"
        row("dark_spots", "🟤", "Dark spots", f"Dark spots: {LEVEL_WORD[ds['level']]}", ds["level"], note, where=ds.get("where", ""))
    else:
        unmeasured("dark_spots", "🟤", "Dark spots")

    # uniformity
    un = d.get("uniformity")
    if un and un.get("pct") is not None:
        pct = int(un["pct"])
        level = "minimal" if pct >= 88 else "mild" if pct >= 75 else "moderate" if pct >= 60 else "noticeable"
        row("uniformity", "🟡", "Uneven skin tone", f"Skin tone uniformity: {pct}%", level,
            "How alike the colour is across forehead, cheeks, nose and chin. Higher is more even.")
    elif analysis.tone_evenness:
        row("uniformity", "🟡", "Uneven skin tone", f"Tone evenness: {LEVEL_WORD[analysis.tone_evenness.level]}",
            analysis.tone_evenness.level, "Percentage not available for this scan.")
    else:
        unmeasured("uniformity", "🟡", "Uneven skin tone")

    # texture
    row("texture", "🧱", "Skin texture", f"Texture: {TEXTURE_WORD[analysis.texture.level]}", analysis.texture.level,
        "How rough or bumpy the skin surface looks at pore scale.")

    # under-eye
    ue = d.get("under_eye")
    if ue and ue.get("measured"):
        note = ("Compared with the cheek just below the eye. "
                + ("Eyes were located in the photo." if ue.get("eyes_found") else "Eye position was estimated from face proportions.")
                + " Puffiness cannot be judged reliably from one flat photo, so it is not scored.")
        row("under_eye", "👁️", "Under-eye", f"Under-eye darkness: {LEVEL_WORD[ue['level']]}", ue["level"], note)
    else:
        unmeasured("under_eye", "👁️", "Under-eye", "The under-eye area was not clearly visible (glasses, hair or shadow).")

    # redness
    row("redness", "🔴", "Redness", _with_where(f"Redness: {LEVEL_WORD[analysis.redness.level]}", hot.get("redness", ""), analysis.redness.level),
        analysis.redness.level, "Visible redness or irritation compared with the rest of your skin.", where=hot.get("redness", ""))

    # pores
    po = d.get("pores")
    if po:
        word = {"minimal": "Low", "mild": "Low", "moderate": "Medium", "noticeable": "High"}[po["level"]]
        row("pores", "🕳️", "Pores", _with_where(f"Pore visibility: {word}", po.get("hotspot", ""), po["level"]), po["level"],
            f"About {po['count']} pore-like dots counted. Webcam photos only show the larger ones.", where=po.get("hotspot", ""))
    else:
        unmeasured("pores", "🕳️", "Pores")

    # dryness, oiliness
    row("dryness", "💧", "Dryness", _with_where(f"Dryness: {LEVEL_WORD[analysis.dryness_indicators.level]}", hot.get("dryness", ""), analysis.dryness_indicators.level),
        analysis.dryness_indicators.level, "Dull, low-colour, patchy or fine-flaky looking areas.", where=hot.get("dryness", ""))
    if analysis.oiliness:
        row("oiliness", "✨", "Oiliness", _with_where(f"Oiliness: {LEVEL_WORD[analysis.oiliness.level]}", hot.get("oiliness", ""), analysis.oiliness.level),
            analysis.oiliness.level, "Visible shine that looks like oil on the skin surface.", where=hot.get("oiliness", ""))

    # scars
    sc = d.get("scars")
    if sc:
        row("scars", "🩹", "Acne scars", "Possible acne scarring detected" if sc["possible"] else "No clear acne scarring",
            "moderate" if sc["score"] >= 0.6 else "mild" if sc["possible"] else "minimal",
            "Estimated from lingering acne marks and uneven texture. Scars that are indented need light from the side to judge, so this is a rough guide.")
    else:
        unmeasured("scars", "🩹", "Acne scars")

    # fine lines
    fl = d.get("fine_lines")
    if fl:
        row("fine_lines", "😌", "Fine lines", _with_where(f"Fine lines: {LEVEL_WORD[fl['level']]}", f"on the {fl['where']}" if fl.get("where") else "", fl["level"]),
            fl["level"], "Thin creases found on the forehead and around the eyes.", where=fl.get("where", ""))
    else:
        unmeasured("fine_lines", "😌", "Fine lines")

    # sun spots
    sun = d.get("sun_spots")
    if sun:
        count = sun["count"]
        row("sun_spots", "☀️", "Sun-related spots", "Sun spots detected" if sun["detected"] else "No clear sun spots",
            "minimal" if not sun["detected"] else "mild" if count < 4 else "moderate",
            f"{count} brownish spot{'s' if count != 1 else ''} with a well-defined edge.", where=sun.get("where", ""))
    else:
        unmeasured("sun_spots", "☀️", "Sun-related spots")

    # facial hair (optional)
    fh = d.get("facial_hair")
    if fh and fh.get("measured"):
        row("facial_hair", "🧔", "Facial hair", f"Facial hair: {fh['level'].title()}", None,
            "Optional. It is left out of the skin scores and product advice.")
    # symmetry
    sy = d.get("symmetry")
    if sy and sy.get("pct") is not None:
        row("symmetry", "🧩", "Symmetry", f"Facial symmetry: {sy['pct']}%", None,
            "Approximate. Head tilt, expression and lighting change it, and it says nothing about skin health.")
    elif d:
        row("symmetry", "🧩", "Symmetry", "Facial symmetry: not measured", None, "Not enough facial structure was visible to compare both sides.", measured=False)
    return rows
