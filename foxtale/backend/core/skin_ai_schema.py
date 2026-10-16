"""The Skin Analyst output contract (see prompts/skin_analyst.v1.md) as a Pydantic model,
plus validation, clamping and content moderation.

The `region` and `type` fields are closed enums (`Literal[...]`), not free text -- this is
a *structural* guardrail, not just a prompt instruction: the model cannot emit a disease
name as a finding `type` because no disease name is a legal value. Free-text fields
(`evidence`, `overall_summary`, suggestions, notes) are still possible vectors for a
diagnosis word or alarmist language slipping in, so those are scrubbed by
`core.skin_ai_moderation` after validation.
"""

from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from core.skin_ai_moderation import scrub
from core.skincare_advisor import GOAL_TARGETS

Region = Literal["forehead", "left cheek", "right cheek", "nose", "chin", "jaw", "upper lip", "under-eye", "overall"]
FindingType = Literal[
    "redness", "acne_pimple", "acne_pustule", "blackhead", "whitehead", "dark_spot", "post_acne_mark",
    "sun_spot", "texture_roughness", "pore_visibility", "dryness", "oiliness", "shine",
    "under_eye_darkness", "fine_lines", "uneven_tone",
]
Severity = Literal["none", "mild", "moderate", "marked"]
Goal = Literal[tuple(GOAL_TARGETS.keys())]  # type: ignore[valid-type]  # reuse the same goal vocabulary as the shop/advisor

SEVERITY_SCORE = {"none": 0, "mild": 1, "moderate": 2, "marked": 3}
MAX_LEN_SHORT = 220
MAX_LEN_SUMMARY = 600


def _capped(v: str, limit: int = MAX_LEN_SHORT) -> str:
    v = (v or "").strip()
    return v if len(v) <= limit else v[: limit - 1].rstrip() + "…"


class Finding(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    region: Region
    type: FindingType
    severity: Severity
    evidence: str = Field(default="", max_length=MAX_LEN_SHORT)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertain_reason: Optional[str] = Field(default=None, max_length=MAX_LEN_SHORT)


class RoutineSuggestion(BaseModel):
    goal: Goal
    suggestion: str = Field(max_length=MAX_LEN_SHORT)


class SafetyFlag(BaseModel):
    finding_id: str = Field(max_length=40)
    reason: str = Field(max_length=MAX_LEN_SHORT)


class ImageNotes(BaseModel):
    makeup_suspected: bool = False
    filtered_or_edited_suspected: bool = False


class AnalystResult(BaseModel):
    findings: List[Finding] = Field(default_factory=list, max_length=12)
    overall_summary: str = Field(default="", max_length=MAX_LEN_SUMMARY)
    routine_suggestions: List[RoutineSuggestion] = Field(default_factory=list, max_length=6)
    lifestyle_notes: List[str] = Field(default_factory=list, max_length=5)
    retake_advice: Optional[str] = Field(default=None, max_length=MAX_LEN_SHORT)
    safety_flags: List[SafetyFlag] = Field(default_factory=list, max_length=5)
    image_notes: ImageNotes = Field(default_factory=ImageNotes)

    # set by the pipeline, not by the model
    moderation_redacted: bool = False
    source: Literal["model", "fallback"] = "model"


def validate_and_clamp(raw_json: str) -> Tuple[Optional[AnalystResult], Optional[str]]:
    """Parse + validate the model's raw JSON text against the contract, then run every
    free-text field through the moderation scrub. Returns (result, None) on success, or
    (None, error_message) so the caller can retry once with that message appended to the
    prompt, per the "retry once on schema-validation failure" rule."""
    try:
        result = AnalystResult.model_validate_json(raw_json)
    except ValidationError as exc:
        return None, str(exc)[:800]
    except ValueError as exc:  # e.g. not valid JSON at all
        return None, f"Response was not valid JSON: {exc}"[:800]

    redacted = False
    clean_summary, hit = scrub(result.overall_summary)
    redacted = redacted or hit
    result.overall_summary = _capped(clean_summary, MAX_LEN_SUMMARY)

    for f in result.findings:
        clean, hit = scrub(f.evidence)
        f.evidence = _capped(clean)
        redacted = redacted or hit
        if f.uncertain_reason:
            clean, hit = scrub(f.uncertain_reason)
            f.uncertain_reason = _capped(clean)
            redacted = redacted or hit

    for s in result.routine_suggestions:
        clean, hit = scrub(s.suggestion)
        s.suggestion = _capped(clean)
        redacted = redacted or hit

    clean_notes = []
    for n in result.lifestyle_notes:
        clean, hit = scrub(n)
        redacted = redacted or hit
        clean_notes.append(_capped(clean))
    result.lifestyle_notes = clean_notes

    for sf in result.safety_flags:
        clean, hit = scrub(sf.reason)
        sf.reason = _capped(clean)
        redacted = redacted or hit

    if result.retake_advice:
        clean, hit = scrub(result.retake_advice)
        result.retake_advice = _capped(clean)
        redacted = redacted or hit

    result.moderation_redacted = redacted
    return result, None
