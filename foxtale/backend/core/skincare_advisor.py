"""Matches a scan's measured skin observations to products in the local
Foxtale catalog (assets/foxtale_products.json) and explains, in plain words,
why each was picked and how it works.

This is cosmetic guidance derived from visible-feature estimates in one
photo -- not medical advice. Everything runs locally; the catalog is a JSON
file that can be edited when the range changes.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.schemas import LEVEL_SCORE, SkinAnalysis

logger = logging.getLogger(f"foxtale.{__name__}")

CATALOG_PATH = Path(__file__).resolve().parent.parent / "assets" / "foxtale_products.json"

# Routine order and display labels.
STEPS = [("cleanse", "Cleanse"), ("treat", "Treat"), ("eye", "Eye care"), ("moisturize", "Moisturize"), ("protect", "Protect")]
MAX_PER_STEP = {"cleanse": 1, "treat": 3, "eye": 1, "moisturize": 1, "protect": 1}
MAX_ACTIVES = 1  # at most one strong active (exfoliating acid / vitamin C) per routine

CATEGORY_LABELS = {
    "acne_like_spots": "acne-like spots",
    "redness": "redness",
    "texture": "rough texture",
    "dryness_indicators": "dryness",
    "oiliness": "shine",
    "tone_evenness": "uneven tone",
    # from the detailed findings (engine.features)
    "dark_spots": "dark spots",
    "pores": "visible pores",
    "under_eye": "under-eye darkness",
    "fine_lines": "fine lines",
    "acne_scars": "possible acne scarring",
    "blackheads": "blackheads and whiteheads",
}
DETAIL_ATTRS = ("dark_spots", "pores", "under_eye", "fine_lines", "acne_scars", "blackheads")
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
    variant_id: Optional[str] = None  # Shopify variant id, for cart links
    price_source: str = "foxtale"  # "foxtale" (store price) or "retailer_mrp"
    shape: str = "tube"  # packaging drawn when there is no photo: tube | dropper | jar


@dataclass
class SkinProfile:
    skin_type: str  # oily | dry | combination | normal
    concerns: List[str]  # category attrs with a non-minimal level, most prominent first
    levels: Dict[str, int]
    tone: str = ""  # apparent skin tone label (Very light ... Deep), when measured
    deeper_tone: bool = False  # Tan / Brown / Deep: post-acne marks tend to linger longer


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


def _detail_levels(analysis: SkinAnalysis) -> Dict[str, int]:
    d = analysis.detail or {}
    out = {k: 0 for k in DETAIL_ATTRS}
    if not d:
        return out

    def lv(section: str) -> int:
        level = (d.get(section) or {}).get("level")
        return LEVEL_SCORE.get(level, 0) if level else 0

    out["dark_spots"] = lv("dark_spots")
    out["pores"] = lv("pores")
    out["under_eye"] = lv("under_eye")
    out["fine_lines"] = lv("fine_lines")
    scars = d.get("scars") or {}
    out["acne_scars"] = (2 if scars.get("score", 0) >= 0.6 else 1) if scars.get("possible") else 0
    acne = d.get("acne") or {}
    heads = int(acne.get("blackheads", 0)) + int(acne.get("whiteheads", 0))
    out["blackheads"] = 0 if heads == 0 else 1 if heads <= 3 else 2 if heads <= 8 else 3
    return out


def _levels(analysis: SkinAnalysis) -> Dict[str, int]:
    out = {}
    for attr in CATEGORY_LABELS:
        if attr in DETAIL_ATTRS:
            continue
        result = getattr(analysis, attr, None)
        out[attr] = LEVEL_SCORE[result.level] if result is not None else 0
    out.update(_detail_levels(analysis))
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
    tone = (analysis.skin_tone or {}).get("label", "")
    deeper = tone in ("Tan", "Brown", "Deep")
    if deeper and lv["acne_like_spots"] > 0 and lv["tone_evenness"] == 0:
        # marks from spots are the tone concern on deeper skin even before the tone itself looks uneven
        lv["tone_evenness"] = 1
        if "tone_evenness" not in concerns:
            concerns.append("tone_evenness")
    return SkinProfile(skin_type=skin_type, concerns=concerns, levels=lv, tone=tone, deeper_tone=deeper)


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
    d = analysis.detail or {}
    if attr == "dark_spots" and d.get("dark_spots"):
        n = d["dark_spots"].get("count", 0)
        return f"{n} dark spot{'s' if n != 1 else ''}" + (f" {d['dark_spots']['where']}" if d["dark_spots"].get("where") else "")
    if attr == "pores" and d.get("pores"):
        return "pores that look " + ("enlarged" if level >= 2 else "slightly visible") + (f" {d['pores']['hotspot']}" if d["pores"].get("hotspot") else "")
    if attr == "under_eye" and d.get("under_eye", {}).get("measured"):
        return f"under-eye darkness ({d['under_eye']['level']})"
    if attr == "fine_lines" and d.get("fine_lines"):
        return "fine lines" + (f" on the {d['fine_lines']['where']}" if d["fine_lines"].get("where") else "")
    if attr == "acne_scars":
        return "signs of possible acne scarring or lingering marks"
    if attr == "blackheads" and d.get("acne"):
        return f"{d['acne'].get('blackheads', 0)} blackhead(s) and {d['acne'].get('whiteheads', 0)} whitehead(s)"
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
        text = f"Your scan shows {seen}, which this is made to help with."
        if profile.deeper_tone and ("acne_like_spots" in matched or "tone_evenness" in matched):
            text += " Marks left by spots can linger longer on deeper skin tones, so calming and evening-out steps matter here."
        return text
    return (f"A gentle {dict(STEPS)[product.step].lower()} step that suits {profile.skin_type} skin, "
            "which is what your scan suggests.")


GOAL_TARGETS = {
    "acne": ["acne_like_spots", "blackheads"],
    "dark_spots": ["dark_spots", "tone_evenness", "acne_scars"],
    "anti_aging": ["fine_lines"],
    "hydration": ["dryness_indicators"],
    "oil_control": ["oiliness", "pores"],
    "redness": ["redness"],
    "texture": ["texture", "pores"],
    "under_eye": ["under_eye"],
    "brightening": ["tone_evenness", "dark_spots"],
}
BUDGET_CAP = {"low": 400, "mid": 600}
PREGNANCY_EXCLUDED = {"retinol-serum", "aha-bha-serum", "exfoliating-toner"}


def _profile_filter(catalog: List[Product], profile: Optional[dict], notes: List[str]) -> List[Product]:
    """Drop products the person's questionnaire answers rule out, and say why (notes)."""
    if not profile:
        return catalog
    out = []
    allergy_tokens = [t for t in re.split(r"[,;/\n]+", str(profile.get("allergies", "")).lower()) for t in [t.strip()] if len(t) >= 3]
    dropped: Dict[str, str] = {}
    for p in catalog:
        if profile.get("pregnant") and p.id in PREGNANCY_EXCLUDED:
            dropped[p.name] = "you are pregnant or breastfeeding"
            continue
        if profile.get("sensitive_skin") and p.active:
            dropped[p.name] = "you have sensitive skin"
            continue
        text = (p.name + " " + " ".join(p.key_ingredients)).lower()
        hit = next((t for t in allergy_tokens if t in text), None)
        if hit:
            dropped[p.name] = f"you listed {hit} as an allergy"
            continue
        out.append(p)
    if profile.get("pregnant"):
        notes.append("Retinol and exfoliating acids are left out because you are pregnant or breastfeeding. Please ask your doctor before using them.")
    if profile.get("sensitive_skin"):
        notes.append("Strong actives (exfoliating acids, retinol, vitamin C) are left out because you told us your skin is sensitive.")
    by_allergy: Dict[str, List[str]] = {}
    for name, why in dropped.items():
        if "allergy" in why:
            by_allergy.setdefault(why, []).append(name)
    for why, names in by_allergy.items():
        notes.append(f"Left out because {why}: {', '.join(names)}.")
    return out


def recommend_full(analysis: SkinAnalysis, owned_ids: Optional[List[str]] = None,
                   profile: Optional[dict] = None) -> Tuple[List[Suggestion], List[str]]:
    """recommend() plus the questionnaire: goals boost matching products, safety answers remove products,
    and budget ranks over-budget products lower. Returns (suggestions, plain-words notes for the user)."""
    notes: List[str] = []
    suggestions = _recommend(analysis, owned_ids, profile, notes)
    cap = BUDGET_CAP.get((profile or {}).get("budget", "any"))
    if cap and any(s.product.price_inr and s.product.price_inr > cap for s in suggestions):
        notes.append(f"Some picks cost more than your budget of about ₹{cap} per product; cheaper options were ranked first where they exist.")
    goals = [g for g in (profile or {}).get("goals", []) if g in GOAL_TARGETS]
    if goals:
        notes.append("Ranked with your goals in mind: " + ", ".join(g.replace("_", " ") for g in goals) + ".")
    return suggestions, notes


def recommend(analysis: SkinAnalysis, owned_ids: Optional[List[str]] = None) -> List[Suggestion]:
    return _recommend(analysis, owned_ids, None, [])


def _recommend(analysis: SkinAnalysis, owned_ids: Optional[List[str]], user: Optional[dict], notes: List[str]) -> List[Suggestion]:
    """A short routine (cleanse -> treat -> moisturize -> protect). Products
    the user already uses are kept in the list, marked `owned`, and don't
    take up a suggestion slot -- the next-best product fills it."""
    owned = set(owned_ids or [])
    profile = skin_profile(analysis)
    catalog = _profile_filter([p for p in load_catalog() if _allowed(p, profile)], user, notes)
    goal_targets = {t for g in (user or {}).get("goals", []) for t in GOAL_TARGETS.get(g, [])}
    cap = BUDGET_CAP.get((user or {}).get("budget", "any"))

    def score_of(p: Product) -> float:
        total = _score(p, profile)
        if goal_targets and goal_targets & set(p.targets):
            total += 1.5
        if cap and p.price_inr and p.price_inr > cap:
            total -= 2.0
        return total
    actives_used = sum(1 for p in catalog if p.id in owned and p.active)

    picks: List[Suggestion] = []
    for step, step_label in STEPS:
        ranked = sorted((p for p in catalog if p.step == step), key=lambda p: -score_of(p))
        if step == "treat":
            ranked = [p for p in ranked if score_of(p) - (0.5 if profile.skin_type in p.skin_types else 0) > 0]

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
