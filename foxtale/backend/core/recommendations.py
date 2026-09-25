from typing import List

from engine.schemas import LEVEL_SCORE, SkinAnalysis

# (category attr, tips shown at any non-minimal level, extra tips at moderate+)
_TIPS = [
    ("acne_like_spots",
     ["Cleanse gently twice a day and avoid picking or squeezing spots.",
      "Choose non-comedogenic products so pores are not blocked."],
     ["Consider a targeted spot treatment, or ask a pharmacist or dermatologist if spots persist or worsen."]),
    ("redness",
     ["Use gentle, fragrance-free products and avoid harsh scrubs.",
      "Protect your skin from sun and very hot water, which can make redness more visible."],
     ["Consult a dermatologist if redness is persistent, painful or spreading."]),
    ("dryness_indicators",
     ["Moisturize morning and night, ideally on slightly damp skin.",
      "Avoid very hot water and over-cleansing."],
     ["Add a richer barrier cream at night."]),
    ("texture",
     ["Exfoliate gently, no more than 1-2 times a week.",
      "Use daily sunscreen; sun damage makes texture look rougher."],
     []),
    ("oiliness",
     ["Use a light, oil-free moisturizer and a gentle gel cleanser.",
      "Blot instead of over-washing, which can increase oil."],
     []),
    ("tone_evenness",
     ["Apply SPF 30+ daily; uneven tone worsens with sun exposure.",
      "Be consistent with your routine for a few weeks before judging changes."],
     []),
]

MAX_TIPS = 9


def build_recommendations(analysis: SkinAnalysis) -> List[str]:
    """Tips for what was actually visible, most prominent concern first."""
    ranked = []
    for attr, base, strong in _TIPS:
        result = getattr(analysis, attr, None)
        if result is None or result.level == "minimal":
            continue
        ranked.append((LEVEL_SCORE[result.level], base, strong))
    ranked.sort(key=lambda t: -t[0])

    tips: List[str] = []
    for level, base, strong in ranked:
        tips += base
        if level >= 2:
            tips += strong
    if not tips:
        tips = [
            "Keep up a gentle, consistent skincare routine.",
            "Use sun protection daily.",
            "Stay hydrated and moisturized.",
        ]
    tips.append("Scan under similar lighting each time so changes over time are comparable.")

    seen = set()
    unique = []
    for tip in tips:
        if tip not in seen:
            seen.add(tip)
            unique.append(tip)
    return unique[:MAX_TIPS]
