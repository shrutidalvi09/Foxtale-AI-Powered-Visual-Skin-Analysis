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
    "tone evenness 14%, dryness 12%, oiliness 8%."
)


def category_areas(regions: List[RegionObservation], category: str) -> str:
    matches = [r for r in regions if r.category == category]
    if not matches:
        return "Not flagged in a specific area"
    seen: Dict[str, None] = {}
    for r in matches:
        seen[r.region.title()] = None
    return ", ".join(seen)
