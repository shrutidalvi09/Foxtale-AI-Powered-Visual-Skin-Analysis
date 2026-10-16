"""Deterministic guardrail over the Skin Analyst's free-text fields.

The schema's closed `region`/`type` enums (core/skin_ai_schema.py) already stop the model
from naming a disease as a *finding type*. This module is the second layer: a word-list
scan over every free-text sentence (evidence, summary, suggestions, notes) that strips out
anything that reads as a diagnosis, a prescription/drug reference, or alarmist language --
in case the model mentions one in passing prose rather than as a structured field.

This is a blunt, explainable safety net, not a language model -- it is meant to over-redact
rather than risk letting something through.
"""

import re
from typing import List, Tuple

# Named conditions/diseases: never acceptable, whatever the context.
_CONDITIONS = [
    "eczema", "psoriasis", "rosacea", "dermatitis", "melanoma", "carcinoma", "cancer",
    "impetigo", "folliculitis", "fungal infection", "ringworm", "herpes", "shingles",
    "lupus", "vitiligo", "hidradenitis", "seborrheic keratosis", "actinic keratosis",
    "cellulitis", "mrsa", "chickenpox", "measles", "scabies", "hpv", "wart",
    "acne vulgaris", "cystic acne diagnosis", "allergic reaction",
]

# Prescription / drug references: the model may name an OTC ingredient category, but never
# a prescription-only drug, a prescription strength, or language that implies prescribing.
_DRUGS = [
    "isotretinoin", "accutane", "tretinoin", "adapalene prescription", "tazarotene",
    "clindamycin", "doxycycline", "minocycline", "antibiotic", "corticosteroid",
    "hydrocortisone prescription", "prescription strength", "prescribe", "prescription",
    "dosage", "dosing",
]

# Alarmist or urgency language the prompt explicitly forbids.
_ALARMIST = [
    "urgent", "urgently", "emergency", "life-threatening", "life threatening", "dangerous",
    "deadly", "cancerous", "must see a doctor immediately", "call 911", "go to the er",
    "go to the emergency room", "serious condition", "alarming",
]

_ALL_TERMS = _CONDITIONS + _DRUGS + _ALARMIST
_PATTERN = re.compile(r"\b(" + "|".join(re.escape(t) for t in _ALL_TERMS) + r")\b", re.IGNORECASE)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def scrub(text: str) -> Tuple[str, bool]:
    """Removes any sentence containing a denied term (whole sentence, not just the word, so the
    surrounding claim does not survive half-redacted). Returns (clean_text, anything_redacted)."""
    if not text:
        return text, False
    sentences: List[str] = _SENTENCE_SPLIT.split(text.strip()) or [text]
    kept, redacted = [], False
    for s in sentences:
        if _PATTERN.search(s):
            redacted = True
            continue
        kept.append(s)
    clean = " ".join(kept).strip()
    if redacted and not clean:
        clean = "(removed by the app's safety filter)"
    return clean, redacted


def contains_denied_term(text: str) -> bool:
    return bool(text) and _PATTERN.search(text) is not None
