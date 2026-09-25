"""Matches a scan's measured skin observations to products in the local
Foxtale catalog (assets/foxtale_products.json) and explains, in plain words,
why each was picked and how it works.

This is cosmetic guidance derived from visible-feature estimates in one
photo -- not medical advice. Everything runs locally; the catalog is a JSON
file that can be edited when the range changes.
"""

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from engine.schemas import LEVEL_SCORE, SkinAnalysis

logger = logging.getLogger(f"foxtale.{__name__}")

CATALOG_PATH = Path(__file__).resolve().parent.parent / "assets" / "foxtale_products.json"

# Routine order and display labels.
STEPS = [("cleanse", "Cleanse"), ("treat", "Treat"), ("moisturize", "Moisturize"), ("protect", "Protect")]
MAX_PER_STEP = {"cleanse": 1, "treat": 2, "moisturize": 1, "protect": 1}
MAX_ACTIVES = 1  # at most one strong active (exfoliating acid / vitamin C) per routine

CATEGORY_LABELS = {
    "acne_like_spots": "acne-like spots",
    "redness": "redness",
    "texture": "rough texture",
    "dryness_indicators": "dryness",
    "oiliness": "shine",
    "tone_evenness": "uneven tone",
}
LEVEL_WEIGHT = {0: 0.0, 1: 1.0, 2: 2.5, 3: 4.0}


@dataclass
class Product:
    id: str
    name: str
    step: str
    when: str
    key_ingredients: List[str]
    targets: List[str]
    skin_types: List[str]
    active: bool
    how_it_works: str
    how_to_use: str
    caution: str
    url: str
    avoid_if: Dict[str, int] = field(default_factory=dict)
    size: str = ""
    price_inr: Optional[int] = None  # printed MRP; None when it was not listed consistently
    price_source: str = "foxtale"  # "foxtale" (store price) or "retailer_mrp"
    shape: str = "tube"  # packaging drawn when there is no photo: tube | dropper | jar


@dataclass
class SkinProfile:
    skin_type: str  # oily | dry | combination | normal
    concerns: List[str]  # category attrs with a non-minimal level, most prominent first
    levels: Dict[str, int]


@dataclass
class Suggestion:
    product: Product
    step_label: str
    reason: str  # why it was picked for this face
    owned: bool = False


@lru_cache(maxsize=1)
def load_catalog() -> List[Product]:
    try:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return [Product(**{k: v for k, v in p.items() if k in Product.__dataclass_fields__}) for p in raw["products"]]
    except (OSError, ValueError, KeyError, TypeError):
        logger.exception("Could not load the product catalog")
        return []


def catalog_date() -> str:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8")).get("verified_on", "")
    except (OSError, ValueError):
        return ""


def _levels(analysis: SkinAnalysis) -> Dict[str, int]:
    out = {}
    for attr in CATEGORY_LABELS:
        result = getattr(analysis, attr, None)
        out[attr] = LEVEL_SCORE[result.level] if result is not None else 0
    return out


def _t_zone_shinier(analysis: SkinAnalysis) -> bool:
    rs = analysis.region_scores or {}

    def oil(name):
        return rs.get(name, {}).get("oiliness", 0.0)

    t_zone = max(oil("nose"), oil("forehead"))
    cheeks = max(oil("left cheek"), oil("right cheek"))
    return t_zone > cheeks + 0.1


def skin_profile(analysis: SkinAnalysis) -> SkinProfile:
    lv = _levels(analysis)
    oil, dry = lv["oiliness"], lv["dryness_indicators"]
    if oil >= 2 and dry >= 2:
        skin_type = "combination"
    elif oil >= 2:
        skin_type = "oily"
    elif dry >= 2:
        skin_type = "dry"
    elif oil >= 1 and dry >= 1:
        skin_type = "combination"
    elif oil >= 1:
        skin_type = "combination" if _t_zone_shinier(analysis) else "normal"
    elif dry >= 1:
        skin_type = "dry"
    else:
        skin_type = "normal"
    concerns = [a for a in sorted(lv, key=lambda k: -lv[k]) if lv[a] > 0]
    return SkinProfile(skin_type=skin_type, concerns=concerns, levels=lv)


def _score(product: Product, profile: SkinProfile) -> float:
    total = sum(LEVEL_WEIGHT[profile.levels.get(t, 0)] for t in product.targets)
    if profile.skin_type in product.skin_types:
        total += 0.5
    return total


def _allowed(product: Product, profile: SkinProfile) -> bool:
    if profile.skin_type not in product.skin_types:
        return False
    return not any(profile.levels.get(cat, 0) >= lvl for cat, lvl in product.avoid_if.items())


def _measurement_phrase(attr: str, analysis: SkinAnalysis, level: int) -> str:
    m = analysis.metrics or {}
    rs = analysis.region_scores or {}
    label = CATEGORY_LABELS[attr]
    if attr == "acne_like_spots" and analysis.acne_like_spots.count:
        n = analysis.acne_like_spots.count
        return f"{n} small reddish spot{'s' if n != 1 else ''}"
    if attr == "redness" and m.get("redness_local_pct", 0) >= 5:
        return f"about {m['redness_local_pct']:.0f}% of your skin looking redder than your average tone"
    if attr == "oiliness" and m.get("shine_pct") and rs:
        top = max(rs, key=lambda r: rs[r].get("oiliness", 0))
        return f"shine on about {m['shine_pct']:.0f}% of your skin, mostly on the {top}"
    if attr == "dryness_indicators" and m.get("dryness_low_chroma_pct", 0) >= 5:
        return f"dull or low-colour areas covering about {m['dryness_low_chroma_pct']:.0f}% of your skin"
    words = {1: "slightly visible", 2: "clearly visible", 3: "prominent"}
    return f"{label} that is {words.get(level, 'visible')}"


def _reason(product: Product, profile: SkinProfile, analysis: SkinAnalysis) -> str:
    matched = [t for t in profile.concerns if t in product.targets][:2]
    if product.step == "protect":
        text = "Sun makes redness, marks and uneven tone worse, so daily sunscreen protects every other step."
        finish = "matte" if "oily" in product.skin_types and "dry" not in product.skin_types else "dewy"
        return text + f" The {finish} finish suits {profile.skin_type} skin."
    if matched:
        seen = " and ".join(_measurement_phrase(t, analysis, profile.levels[t]) for t in matched)
        return f"Your scan shows {seen}, which this is made to help with."
    return (f"A gentle {dict(STEPS)[product.step].lower()} step that suits {profile.skin_type} skin, "
            "which is what your scan suggests.")


def recommend(analysis: SkinAnalysis, owned_ids: Optional[List[str]] = None) -> List[Suggestion]:
    """A short routine (cleanse -> treat -> moisturize -> protect). Products
    the user already uses are kept in the list, marked `owned`, and don't
    take up a suggestion slot -- the next-best product fills it."""
    owned = set(owned_ids or [])
    profile = skin_profile(analysis)
    catalog = [p for p in load_catalog() if _allowed(p, profile)]
    actives_used = sum(1 for p in catalog if p.id in owned and p.active)

    picks: List[Suggestion] = []
    for step, step_label in STEPS:
        ranked = sorted((p for p in catalog if p.step == step), key=lambda p: -_score(p, profile))
        if step == "treat":
            ranked = [p for p in ranked if _score(p, profile) - (0.5 if profile.skin_type in p.skin_types else 0) > 0]

        slots = MAX_PER_STEP[step]
        new_count = 0
        for p in ranked:
            if p.id in owned:
                picks.append(Suggestion(p, step_label, _reason(p, profile, analysis), owned=True))
                continue
            if new_count >= slots:
                continue
            if p.active and actives_used >= MAX_ACTIVES:
                continue
            picks.append(Suggestion(p, step_label, _reason(p, profile, analysis)))
            new_count += 1
            actives_used += 1 if p.active else 0
    return picks


def catalog_price_note() -> str:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8")).get("price_note", "")
    except (OSError, ValueError):
        return ""


def routine_cost(suggestions: List[Suggestion]) -> tuple:
    """(total MRP of the products you would still need to buy, how many of those have no listed price)."""
    new = [s.product for s in suggestions if not s.owned]
    total = sum(p.price_inr for p in new if p.price_inr)
    return total, sum(1 for p in new if not p.price_inr)


def in_routine(suggestion: Suggestion, when: str) -> bool:
    """when: 'all' | 'AM' | 'PM' -- used by the morning / evening toggle."""
    return when == "all" or when in suggestion.product.when
