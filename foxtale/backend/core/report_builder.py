"""Builds the full face analysis report as JSON for the React Analysis page,
using the same content modules as the PDF so both always agree."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from core import conflicts as cf
from core import report_content as rc
from core import skincare_advisor as adv
from core.recommendations import build_recommendations
from engine.schemas import RegionObservation, SkinAnalysis
from engine.skin_analysis import score_label

PRODUCT_IMAGES = Path(__file__).resolve().parent.parent / "assets" / "products"


def _category_row(row: rc.CategoryRow) -> Dict[str, Any]:
    return {
        "key": row.key, "label": row.label, "level": row.level, "confidence": row.confidence,
        "measurement": row.measurement, "meaning": row.meaning,
    }


def _suggestion(s: adv.Suggestion) -> Dict[str, Any]:
    p = s.product
    has_photo = (PRODUCT_IMAGES / f"{p.id}.jpg").exists()
    return {
        "id": p.id, "name": p.name, "step": p.step, "stepLabel": s.step_label, "when": p.when,
        "ingredients": p.key_ingredients, "reason": s.reason, "howItWorks": p.how_it_works,
        "howToUse": p.how_to_use, "caution": p.caution, "url": p.url, "size": p.size,
        "price": p.price_inr, "priceSource": p.price_source, "variantId": p.variant_id, "shape": p.shape, "owned": s.owned,
        "image": f"/product-images/{p.id}.jpg" if has_photo else None,
    }


def _skin_type_reason(analysis: SkinAnalysis, profile: adv.SkinProfile) -> str:
    m = analysis.metrics or {}
    oil, dry = profile.levels.get("oiliness", 0), profile.levels.get("dryness_indicators", 0)
    bits = []
    if oil:
        bits.append(f"shine on about {m.get('shine_pct', 0):.0f}% of the skin")
    if dry:
        bits.append("dull or dry-looking areas")
    if not bits:
        return "No strong shine or dryness was visible, so your skin reads as balanced."
    lead = " and ".join(bits)
    return f"Based on {lead}. Skin type here is estimated from what is visible in one photo."


def _profile(analysis: SkinAnalysis, profile: adv.SkinProfile) -> Dict[str, Any]:
    m = analysis.metrics or {}
    tone = analysis.skin_tone
    pimples, marks = int(m.get("pimple_count", 0)), int(m.get("mark_count", 0))
    tone_note = None
    if tone:
        tone_note = (f"Apparent tone in this photo (ITA {tone['ita']:.0f} degrees), {tone['undertone']} undertone. "
                     "Lighting and camera colour settings change this, so treat it as a guide.")
    return {
        "skinType": profile.skin_type,
        "skinTypeReason": _skin_type_reason(analysis, profile),
        "tone": ({"label": tone["label"], "undertone": tone["undertone"], "swatch": tone["swatch"], "note": tone_note}
                 if tone else None),
        "spots": {"total": pimples + marks, "pimples": pimples, "marks": marks,
                  "level": analysis.acne_like_spots.level},
        "texture": {"level": analysis.texture.level},
        "toneEvenness": {"level": analysis.tone_evenness.level if analysis.tone_evenness else None},
    }


def build(analysis_dict: dict, regions: List[dict], previous_dict: Optional[dict] = None,
          owned_ids: Optional[List[str]] = None, profile_answers: Optional[dict] = None) -> Dict[str, Any]:
    analysis = SkinAnalysis.from_dict(analysis_dict)
    previous = SkinAnalysis.from_dict(previous_dict) if previous_dict else None
    region_obs = [RegionObservation.from_dict(r) for r in regions]

    profile = adv.skin_profile(analysis)
    suggestions, notes = adv.recommend_full(analysis, owned_ids, profile_answers)
    total, missing = adv.routine_cost(suggestions)

    return {
        "overallScore": analysis.overall_score,
        "scoreLabel": score_label(analysis.overall_score) if analysis.overall_score is not None else None,
        "summary": rc.overall_summary(analysis),
        "categories": [_category_row(r) for r in rc.category_rows(analysis)],
        "regionScores": [{"name": r.name, "score": r.score, "concern": r.concern} for r in rc.region_rows(analysis)],
        "changes": rc.compare_with_previous(analysis, previous),
        "recommendations": build_recommendations(analysis),
        "methodology": {
            "steps": [{"title": t, "body": b} for t, b in rc.METHOD_STEPS],
            "scoreExplanation": rc.SCORE_EXPLANATION,
            "limitations": rc.LIMITATIONS,
        },
        "areas": {key: rc.category_areas(region_obs, key) for key, _label, _attr in rc.CATEGORY_ORDER},
        "findings": rc.detail_rows(analysis),
        "profile": _profile(analysis, profile),
        "skincare": {
            "skinType": profile.skin_type,
            "tone": profile.tone or None,
            "concerns": [{"key": c, "label": adv.CATEGORY_LABELS[c]} for c in profile.concerns],
            "suggestions": [_suggestion(s) for s in suggestions],
            "cost": {"total": total, "unpriced": missing},
            "notes": notes,
            "conflicts": cf.check([x.product for x in suggestions]),
            "priceNote": adv.catalog_price_note(),
            "catalogDate": adv.catalog_date(),
        },
    }
