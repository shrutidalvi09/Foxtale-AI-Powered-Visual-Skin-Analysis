"""Deterministic "would a dermatologist's opinion help?" rule.

This never runs the LLM and never depends on it: it always returns a result from the
measurement data alone, and -- when an AI analysis is available -- folds in its
`safety_flags` and finding severities too. The rule itself (the thresholds) is plain
Python, not a model call, so it behaves the same way every time and is easy to audit.
This is a suggestion to see a professional, never a diagnosis.
"""

from typing import Any, Dict, List, Optional

from core.skin_ai_config import CONFIG
from core.skin_ai_schema import SEVERITY_SCORE

DISCLAIMER = (
    "This is not a diagnosis. It only flags when a lot is visible in the photo, or when the "
    "Skin Analyst noted something worth a second look. A dermatologist can examine skin in "
    "person far more reliably than any photo."
)


def _measurement_reasons(analysis: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    detail = analysis.get("detail") or {}
    acne = detail.get("acne") or {}
    total_spots = acne.get("total", (analysis.get("acne_like_spots") or {}).get("count") or 0)
    if total_spots and total_spots >= CONFIG.referral_min_spot_count:
        reasons.append(f"A high number of visible spots was found ({total_spots}).")
    scars = detail.get("scars") or {}
    if scars.get("possible") and scars.get("score", 0) >= 0.6:
        reasons.append("Possible scarring or lingering marks were flagged.")
    return reasons


def recommend(ai_result: Optional[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    """`ai_result` is a stored AnalystResult.model_dump() (or None if AI is off/unavailable).
    `analysis` is a plain SkinAnalysis.to_dict()."""
    reasons: List[str] = list(_measurement_reasons(analysis))
    urgent = False

    if ai_result:
        for flag in ai_result.get("safety_flags", []):
            reason = flag.get("reason", "").strip()
            if reason:
                reasons.append(reason)
                urgent = True  # the Skin Analyst itself flagged something -- weight it higher

        findings = ai_result.get("findings", [])
        marked = [f for f in findings if f.get("severity") == "marked"]
        moderate_plus = [f for f in findings if SEVERITY_SCORE.get(f.get("severity"), 0) >= SEVERITY_SCORE["moderate"]]
        if len(marked) >= CONFIG.referral_min_marked_findings:
            reasons.append("At least one finding looked prominent in the photo.")
        if len(moderate_plus) >= CONFIG.referral_min_moderate_plus_findings:
            reasons.append(f"Several things stood out together ({len(moderate_plus)} findings at a clearly "
                           "visible level or higher).")

    seen = set()
    unique_reasons = [r for r in reasons if not (r in seen or seen.add(r))]
    return {
        "recommended": bool(unique_reasons),
        "urgent": urgent,
        "reasons": unique_reasons,
        "disclaimer": DISCLAIMER,
    }
