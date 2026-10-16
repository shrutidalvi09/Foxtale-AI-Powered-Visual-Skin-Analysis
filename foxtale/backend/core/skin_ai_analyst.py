"""Orchestrates one Skin Analyst run: consent check -> rate limit -> cache -> call the
configured `VisionLLMProvider` -> validate/moderate -> confidence-blend -> store.

This is the only module the rest of the app calls into (`main.py`, as a background task,
mirrors `core.delivery`/`core.digest`). It never blocks the scan response and never raises
out to the caller -- every failure path ends in a stored "failed" or "fallback" status
instead, per the "never block the scan on an LLM failure" rule.
"""

import hashlib
import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from core import skin_ai_provider as provider
from core import storage
from core.skin_ai_config import CONFIG, PROMPT_VERSION, system_prompt
from core.skin_ai_measurer import default_measurer
from core.skin_ai_provider import AiProviderError
from core.skin_ai_referral import recommend as referral_recommend
from core.skin_ai_schema import SEVERITY_SCORE, AnalystResult, validate_and_clamp
from engine.quality import QualityResult
from engine.schemas import SkinAnalysis

logger = logging.getLogger("foxtale.skin_ai")

# A severity level from the classical engine's four-word vocabulary (minimal/mild/moderate/
# noticeable) mapped onto the Skin Analyst's own vocabulary, used only by the measurements-only
# fallback path below -- the two vocabularies are kept separate everywhere else on purpose.
_LEVEL_TO_SEVERITY = {"minimal": "none", "mild": "mild", "moderate": "moderate", "noticeable": "marked"}

_FALLBACK_TYPE = {
    "acne_like_spots": "acne_pimple", "redness": "redness", "texture": "texture_roughness",
    "dryness_indicators": "dryness", "oiliness": "oiliness", "tone_evenness": "uneven_tone",
}

# -------------------------------------------------------------------- rate limiting (in-memory;
# resets on restart, which is fine for a single local server -- see core.whatsapp for the same
# per-process pattern applied to OTP sends).
_lock = threading.Lock()
_recent_calls: list = []


def _rate_limited() -> bool:
    now = time.monotonic()
    with _lock:
        global _recent_calls
        _recent_calls = [t for t in _recent_calls if now - t < 60.0]
        if len(_recent_calls) >= CONFIG.rate_limit_per_minute:
            return True
        _recent_calls.append(now)
        return False


# ------------------------------------------------------------------------------- consent

def consent_status() -> Dict[str, Any]:
    s = storage.load_settings()
    return {
        "enabled": bool(s.get("ai_enabled")),
        "improveConsent": bool(s.get("ai_improve_consent")),
        "configured": provider.is_configured(),
        "provider": CONFIG.provider,
        "model": CONFIG.model,
        "dryRun": CONFIG.dry_run,
        "disclosure": (
            "When turned on, a cropped, resized copy of your face photo (not the full photo, and "
            "with no location/EXIF data) is sent to the configured AI provider "
            f"({'a local test mode, no network call' if CONFIG.dry_run else CONFIG.provider}) "
            "along with the numbers already measured on this device, to get a written description "
            "of what is visible. This is separate from the visible-skin score, which is always "
            "computed on this device and never depends on the AI result."
        ),
    }


def set_consent(enabled: bool, improve_consent: bool) -> Dict[str, Any]:
    storage.save_settings({"ai_enabled": enabled, "ai_improve_consent": improve_consent})
    return consent_status()


# -------------------------------------------------------------------------- image handling

def _prepare_image(image_bgr: np.ndarray, box) -> bytes:
    """Crop to the face (with a little padding) and resize down -- the smallest image that
    still works, per the privacy requirement. Re-encoding as JPEG also drops any EXIF/GPS
    metadata that decode_image's cv2.imdecode did not already discard."""
    h, w = image_bgr.shape[:2]
    x, y, bw, bh = box
    pad_x, pad_y = int(bw * CONFIG.image_padding_frac), int(bh * CONFIG.image_padding_frac)
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
    crop = image_bgr[y0:y1, x0:x1]
    scale = CONFIG.image_max_dim / max(crop.shape[:2])
    if scale < 1.0:
        crop = cv2.resize(crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, CONFIG.image_jpeg_quality])
    if not ok:
        raise AiProviderError("Could not encode the image crop for the AI call.")
    return buf.tobytes()


def _cache_key(image_bytes: bytes) -> str:
    h = hashlib.sha256()
    h.update(image_bytes)
    h.update(b"|" + PROMPT_VERSION.encode() + b"|" + CONFIG.model.encode())
    return h.hexdigest()


# ------------------------------------------------------------------------- blended confidence

def _blend_confidence(result: AnalystResult, quality_confidence: float) -> None:
    """final = min(image-quality confidence, the model's own confidence) * makeup/filter
    penalties, floored so nothing shows as exactly zero. Mutates findings in place."""
    penalty = 1.0
    if result.image_notes.makeup_suspected:
        penalty *= CONFIG.makeup_confidence_penalty
    if result.image_notes.filtered_or_edited_suspected:
        penalty *= CONFIG.filter_confidence_penalty
    for f in result.findings:
        blended = min(quality_confidence, f.confidence) * penalty
        f.confidence = max(CONFIG.min_confidence_floor, round(blended, 3))


# --------------------------------------------------------------------------- fallback result

def _fallback_result(analysis: SkinAnalysis, quality: Optional[QualityResult], reason: str) -> AnalystResult:
    """A schema-valid, non-alarming result built purely from the deterministic measurements,
    used when the AI call could not produce a usable response after one retry. The visible-skin
    score and the regular Detailed Findings table already cover this ground in more detail --
    this exists only so the AI-insights section always has *something* schema-shaped to show."""
    findings = []
    for attr, kind in _FALLBACK_TYPE.items():
        cat = getattr(analysis, attr, None)
        if cat is None or cat.level == "minimal":
            continue
        findings.append({
            "id": attr, "region": "overall", "type": kind, "severity": _LEVEL_TO_SEVERITY[cat.level],
            "evidence": "From the on-device measurements only -- the AI description was unavailable this time.",
            "confidence": cat.confidence, "uncertain_reason": reason,
        })
    score = analysis.overall_score
    summary = (
        f"The on-device measurements give an overall visible-skin score of {score}/100."
        if score is not None else "The on-device measurements are the only source for this result."
    ) + " A written AI description was not available for this scan."
    retake = None
    if quality is not None and quality.overall < 50:
        retake = "This photo's quality was on the lower side; a brighter, sharper, front-facing photo usually helps."
    return AnalystResult(
        findings=findings[:12], overall_summary=summary[:600], retake_advice=retake,
        lifestyle_notes=["Daily sunscreen and a consistent, gentle routine make changes over time easier to see."],
        source="fallback",
    )


# ------------------------------------------------------------------------------- the main call

def _call_model(measurer_json: Dict[str, Any], image_bytes: bytes) -> Tuple[Optional[AnalystResult], str]:
    """Calls the provider once, validates, and -- only on a schema failure -- retries once with
    the validation error appended so the model can correct itself. Returns (result_or_None,
    final_status: 'ready' | 'failed')."""
    llm = provider.get_provider()
    system = system_prompt()
    base_user_text = (
        "You will receive one cropped photo of a face and a JSON object of measurements already "
        "computed by a deterministic computer-vision pipeline. Use the measurements as grounding "
        "context. Return the JSON object described in the system prompt -- JSON only.\n\n"
        f"Measurements:\n```json\n{json.dumps(measurer_json)}\n```"
    )
    attempts = [base_user_text]
    for attempt_n, user_text in enumerate(attempts, start=1):
        try:
            raw = llm.complete(system_prompt=system, user_text=user_text,
                               image_bytes=image_bytes, image_media_type="image/jpeg")
        except AiProviderError as exc:
            logger.warning("Skin Analyst call failed (attempt %d, provider=%s): %s", attempt_n, llm.name, exc)
            return None, "failed"
        result, error = validate_and_clamp(raw)
        if result is not None:
            return result, "ready"
        logger.warning("Skin Analyst response failed schema validation (attempt %d)", attempt_n)
        if attempt_n == 1:
            attempts.append(
                base_user_text + "\n\nYour previous response did not match the required JSON schema "
                f"({error}). Reply again with ONLY a single corrected JSON object, no other text."
            )
    return None, "failed"


def run_for_scan(scan_id: str, image_bgr: np.ndarray, box, analysis: SkinAnalysis,
                 quality: Optional[QualityResult]) -> None:
    """Entry point for the background task kicked off from POST /api/analyze (and from the
    manual re-run endpoint). Always ends by writing a status to storage; never raises."""
    settings = storage.load_settings()
    if not settings.get("ai_enabled"):
        storage.ai_set(scan_id, status="disabled")
        return
    if _rate_limited():
        storage.ai_set(scan_id, status="rate_limited",
                       error=f"More than {CONFIG.rate_limit_per_minute} AI calls in the last minute.")
        return

    quality_confidence = (quality.overall / 100.0) if quality is not None else 0.6
    try:
        image_bytes = _prepare_image(image_bgr, box)
    except Exception:  # noqa: BLE001 - image prep failing should fall back, not crash the task
        logger.exception("Skin Analyst image preparation failed for scan %s", scan_id)
        storage.ai_set(scan_id, status="failed", error="Could not prepare the image for the AI call.")
        return

    cache_key = _cache_key(image_bytes)
    cached = storage.ai_cache_get(cache_key, max_age_days=CONFIG.cache_ttl_days)
    if cached is not None:
        result = AnalystResult.model_validate_json(cached)
        from_cache = True
        status = "ready"
    else:
        measurer = default_measurer()
        measurements = measurer.measure(analysis, quality)
        result, status = _call_model(measurements, image_bytes)
        from_cache = False
        if result is None:
            result = _fallback_result(analysis, quality, reason="The AI call did not return a usable result.")
            status = "fallback"
        else:
            storage.ai_cache_put(cache_key, result.model_dump_json())

    _blend_confidence(result, quality_confidence)
    referral = referral_recommend(result.model_dump(mode="json"), analysis.to_dict())
    storage.ai_set(
        scan_id, status=status, provider=CONFIG.provider, model=CONFIG.model, prompt_version=PROMPT_VERSION,
        result_json=result.model_dump_json(), referral_json=json.dumps(referral), from_cache=from_cache,
    )
    logger.info("Skin Analyst finished scan=%s status=%s from_cache=%s findings=%d",
               scan_id, status, from_cache, len(result.findings))


def get(scan_id: str) -> Dict[str, Any]:
    row = storage.ai_get(scan_id)
    if not row:
        return {"status": "none"}
    out: Dict[str, Any] = dict(row)
    if row.get("result_json"):
        out["result"] = json.loads(row["result_json"])
    if row.get("referral_json"):
        out["referral"] = json.loads(row["referral_json"])
    out.pop("result_json", None)
    out.pop("referral_json", None)
    return out


def add_feedback(scan_id: str, finding_id: str, vote: str, comment: str) -> None:
    """Stores a thumbs up/down on one finding -- only called when the separate "help improve
    this" consent is on (enforced by the caller, main.py). Stores the vote and an optional
    short comment only; never the photo."""
    storage.ai_feedback_add(scan_id, finding_id[:40], vote, comment[:500], datetime.now().isoformat())
