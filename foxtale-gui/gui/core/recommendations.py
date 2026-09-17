from typing import List

from engine.schemas import SkinAnalysis


def build_recommendations(analysis: SkinAnalysis) -> List[str]:
    tips: List[str] = []

    if analysis.acne_like_spots.level != "minimal":
        tips += [
            "Keep the face clean with a gentle cleanser.",
            "Avoid picking or squeezing spots.",
            "Use non-comedogenic skincare products.",
            "Consider professional advice if spots are persistent or worsening.",
        ]
    if analysis.redness.level != "minimal":
        tips += [
            "Avoid harsh skincare products.",
            "Use gentle, fragrance-free products.",
            "Protect exposed skin from excessive sun.",
            "Consult a dermatologist if redness persists or worsens.",
        ]
    if analysis.dryness_indicators.level != "minimal":
        tips += [
            "Use a gentle cleanser.",
            "Apply a moisturizer regularly.",
            "Avoid very hot water.",
            "Consider fragrance-free products.",
        ]
    if not tips:
        tips = [
            "Keep up a gentle, consistent skincare routine.",
            "Use sun protection daily.",
            "Stay hydrated and moisturized.",
        ]

    seen = set()
    unique = []
    for tip in tips:
        if tip not in seen:
            seen.add(tip)
            unique.append(tip)
    return unique
