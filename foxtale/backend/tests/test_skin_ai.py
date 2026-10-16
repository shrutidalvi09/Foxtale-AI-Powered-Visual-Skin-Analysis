"""Unit tests for schema validation + moderation, the measurement-to-finding mapping, and
fallback behaviour, plus an integration test against a mocked LLM provider (never a real
network call -- see core/skin_ai_provider.py:MockProvider for the same idea used at runtime).

Run with:  cd backend && .venv/Scripts/python.exe -m pytest tests/ -v
"""

import json
from dataclasses import replace

import cv2
import numpy as np
import pytest

from core import skin_ai_analyst as analyst
from core import skin_ai_provider as provider
from core import skin_ai_schema as schema
from core import storage
from engine.quality import QualityResult
from engine.schemas import CategoryResult, SkinAnalysis

VALID_RESPONSE = json.dumps({
    "findings": [
        {"id": "f1", "region": "left cheek", "type": "redness", "severity": "mild",
         "evidence": "A pink area is visible on the left cheek.", "confidence": 0.7},
    ],
    "overall_summary": "Skin looks fairly even with mild redness on one cheek.",
    "routine_suggestions": [{"goal": "redness", "suggestion": "A gentle, fragrance-free moisturizer."}],
    "lifestyle_notes": ["Daily sunscreen helps."],
    "retake_advice": None,
    "safety_flags": [],
    "image_notes": {"makeup_suspected": False, "filtered_or_edited_suspected": False},
})


def _analysis(overall_score=80) -> SkinAnalysis:
    return SkinAnalysis(
        acne_like_spots=CategoryResult(level="mild", confidence=0.7, count=3),
        redness=CategoryResult(level="moderate", confidence=0.8),
        texture=CategoryResult(level="minimal", confidence=0.6),
        dryness_indicators=CategoryResult(level="minimal", confidence=0.6),
        oiliness=CategoryResult(level="mild", confidence=0.5),
        tone_evenness=CategoryResult(level="minimal", confidence=0.6),
        overall_score=overall_score,
    )


# --------------------------------------------------------------------------- schema + moderation

def test_valid_response_passes_validation():
    result, error = schema.validate_and_clamp(VALID_RESPONSE)
    assert error is None
    assert result is not None
    assert result.findings[0].region == "left cheek"
    assert result.findings[0].type == "redness"
    assert result.moderation_redacted is False


def test_disease_name_is_structurally_impossible_as_a_finding_type():
    bad = json.loads(VALID_RESPONSE)
    bad["findings"][0]["type"] = "eczema"  # not in the closed enum
    result, error = schema.validate_and_clamp(json.dumps(bad))
    assert result is None
    assert error is not None


def test_not_json_fails_cleanly():
    result, error = schema.validate_and_clamp("Sure! Here is my analysis: looks fine.")
    assert result is None
    assert "JSON" in error or error


def test_moderation_redacts_disease_mentions_in_free_text():
    bad = json.loads(VALID_RESPONSE)
    bad["overall_summary"] = "This looks fine. This could be eczema. Nothing else stands out."
    result, error = schema.validate_and_clamp(json.dumps(bad))
    assert error is None
    assert "eczema" not in result.overall_summary.lower()
    assert result.moderation_redacted is True
    # the unrelated sentences survive
    assert "nothing else stands out" in result.overall_summary.lower()


def test_moderation_redacts_alarmist_and_drug_language():
    bad = json.loads(VALID_RESPONSE)
    bad["findings"][0]["evidence"] = "This is dangerous and needs isotretinoin prescription right away."
    result, _ = schema.validate_and_clamp(json.dumps(bad))
    evidence = result.findings[0].evidence.lower()
    assert "dangerous" not in evidence and "isotretinoin" not in evidence
    assert result.moderation_redacted is True


def test_findings_are_capped_at_twelve():
    bad = json.loads(VALID_RESPONSE)
    bad["findings"] = [dict(bad["findings"][0], id=f"f{i}") for i in range(20)]
    result, error = schema.validate_and_clamp(json.dumps(bad))
    assert result is None  # max_length=12 on the list -> validation error, triggers the retry path
    assert error


# ---------------------------------------------------------------------------- measurement mapping

def test_heuristic_measurer_projects_the_existing_analysis():
    from core.skin_ai_measurer import HeuristicMeasurer

    a = _analysis()
    q = QualityResult(position_score=80, lighting_score=70, distance_score=90, sharpness_score=60, angle_score=85, overall=77)
    out = HeuristicMeasurer().measure(a, q)
    assert out["overall_visible_skin_score"] == 80
    assert out["categories"]["redness"]["level"] == "moderate"
    assert out["photo_quality"]["overall"] == 77


def test_trained_model_measurer_stub_raises_not_implemented():
    from core.skin_ai_measurer import TrainedModelMeasurer

    with pytest.raises(NotImplementedError):
        TrainedModelMeasurer().measure(_analysis(), None)


# -------------------------------------------------------------------------------- confidence blend

def test_confidence_blend_takes_the_lower_trust_value():
    result, _ = schema.validate_and_clamp(VALID_RESPONSE)
    result.findings[0].confidence = 0.9
    analyst._blend_confidence(result, quality_confidence=0.4)
    assert result.findings[0].confidence == pytest.approx(0.4, abs=0.01)


def test_confidence_blend_applies_makeup_penalty():
    result, _ = schema.validate_and_clamp(VALID_RESPONSE)
    result.findings[0].confidence = 0.9
    result.image_notes.makeup_suspected = True
    analyst._blend_confidence(result, quality_confidence=0.9)
    assert result.findings[0].confidence == pytest.approx(0.9 * analyst.CONFIG.makeup_confidence_penalty, abs=0.01)


# ------------------------------------------------------------------------------------- fallback

def test_fallback_result_is_schema_valid_and_marked_as_fallback():
    a = _analysis()
    result = analyst._fallback_result(a, quality=None, reason="test")
    assert result.source == "fallback"
    # round-trips through the same schema used for model output
    schema.AnalystResult.model_validate_json(result.model_dump_json())
    assert any(f.type == "redness" for f in result.findings)  # redness was "moderate" in _analysis()


def test_referral_uses_only_measurements_when_ai_result_is_none():
    from core import skin_ai_referral as referral

    a = _analysis().to_dict()
    a["detail"] = {"acne": {"total": 20}}  # above referral_min_spot_count
    out = referral.recommend(None, a)
    assert out["recommended"] is True
    assert out["urgent"] is False
    assert any("spots" in r for r in out["reasons"])


def test_referral_flags_ai_safety_flags_as_urgent():
    from core import skin_ai_referral as referral

    ai_result = {"safety_flags": [{"finding_id": "f1", "reason": "worth a second look"}], "findings": []}
    out = referral.recommend(ai_result, _analysis().to_dict())
    assert out["recommended"] is True
    assert out["urgent"] is True


# --------------------------------------------------------------------------------- orchestration

class _StubProvider:
    name = "stub"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, **_kwargs):
        self.calls += 1
        if not self._responses:
            raise provider.AiProviderError("stub exhausted")
        return self._responses.pop(0)


def test_run_for_scan_is_a_noop_without_consent(monkeypatch, sample_face_image, sample_face_box):
    storage.save_settings({"ai_enabled": False})
    stub = _StubProvider([VALID_RESPONSE])
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    analyst.run_for_scan("scan-1", sample_face_image, sample_face_box, _analysis(), None)
    assert stub.calls == 0
    assert analyst.get("scan-1")["status"] == "disabled"


def test_run_for_scan_succeeds_with_mocked_provider(monkeypatch, sample_face_image, sample_face_box):
    storage.save_settings({"ai_enabled": True})
    stub = _StubProvider([VALID_RESPONSE])
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    q = QualityResult(position_score=80, lighting_score=80, distance_score=80, sharpness_score=80, angle_score=80, overall=80)
    analyst.run_for_scan("scan-2", sample_face_image, sample_face_box, _analysis(), q)
    stored = analyst.get("scan-2")
    assert stored["status"] == "ready"
    assert stored["result"]["findings"][0]["region"] == "left cheek"
    assert stored["referral"]["recommended"] in (True, False)
    assert stub.calls == 1


def test_run_for_scan_falls_back_after_provider_failure(monkeypatch, sample_face_image, sample_face_box):
    storage.save_settings({"ai_enabled": True})
    stub = _StubProvider([])  # every call raises
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    analyst.run_for_scan("scan-3", sample_face_image, sample_face_box, _analysis(), None)
    stored = analyst.get("scan-3")
    assert stored["status"] == "fallback"
    assert stored["result"]["source"] == "fallback"


def test_run_for_scan_retries_once_on_bad_schema_then_succeeds(monkeypatch, sample_face_image, sample_face_box):
    storage.save_settings({"ai_enabled": True})
    stub = _StubProvider(["not json at all", VALID_RESPONSE])
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    analyst.run_for_scan("scan-4", sample_face_image, sample_face_box, _analysis(), None)
    assert stub.calls == 2
    assert analyst.get("scan-4")["status"] == "ready"


def test_cache_avoids_a_second_provider_call(monkeypatch, sample_face_image, sample_face_box):
    storage.save_settings({"ai_enabled": True})
    stub = _StubProvider([VALID_RESPONSE, VALID_RESPONSE])
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    analyst.run_for_scan("scan-5a", sample_face_image, sample_face_box, _analysis(), None)
    analyst.run_for_scan("scan-5b", sample_face_image, sample_face_box, _analysis(), None)  # same image+box -> same cache key
    assert stub.calls == 1
    assert analyst.get("scan-5b")["fromCache"] is True


def test_rate_limit_blocks_after_the_configured_number_of_calls(monkeypatch, sample_face_image, sample_face_box):
    storage.save_settings({"ai_enabled": True})
    analyst._recent_calls.clear()
    # CONFIG is a frozen dataclass singleton -- rebind the module-level name analyst.py reads
    # from, rather than mutating the (immutable) instance.
    monkeypatch.setattr(analyst, "CONFIG", replace(analyst.CONFIG, rate_limit_per_minute=2))
    stub = _StubProvider([VALID_RESPONSE] * 5)
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    for i in range(3):
        # a different image each time so the cache (tested separately above) cannot mask the
        # rate limit by serving a hit instead of a real call
        image = sample_face_image.copy()
        image[0, 0] = (i, i, i)
        analyst.run_for_scan(f"scan-rl-{i}", image, sample_face_box, _analysis(), None)
    assert analyst.get("scan-rl-2")["status"] == "rate_limited"
    assert stub.calls == 2


def test_mock_provider_dry_run_returns_schema_valid_json():
    mock = provider.MockProvider()
    raw = mock.complete(system_prompt="x", user_text="y", image_bytes=b"", image_media_type="image/jpeg")
    result, error = schema.validate_and_clamp(raw)
    assert error is None
    assert result is not None


# ------------------------------------------------------------------------------------- API layer

def test_api_consent_and_feedback_gating(monkeypatch):
    import main
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        status = client.get("/api/ai/status").json()
        assert status["enabled"] is False

        enabled = client.put("/api/ai/status", json={"enabled": True, "improveConsent": False}).json()
        assert enabled["enabled"] is True

        none = client.get("/api/ai/does-not-exist").json()
        assert none["status"] == "none"

        # feedback requires the separate improve-consent toggle
        resp = client.post("/api/ai/scan-x/feedback", json={"findingId": "f1", "vote": "up"})
        assert resp.status_code == 409

        client.put("/api/ai/status", json={"enabled": True, "improveConsent": True})
        resp = client.post("/api/ai/scan-x/feedback", json={"findingId": "f1", "vote": "up", "comment": "looked right"})
        assert resp.status_code == 200
        assert storage.ai_feedback_list("scan-x")[0]["vote"] == "up"

        bad_vote = client.post("/api/ai/scan-x/feedback", json={"findingId": "f1", "vote": "sideways"})
        assert bad_vote.status_code == 422


def test_analyze_kicks_off_ai_when_enabled(monkeypatch, sample_face_image, sample_face_box):
    import main
    from engine.face_detection import FaceDetectionResult
    from fastapi.testclient import TestClient

    monkeypatch.setattr(main, "detect_face", lambda img: FaceDetectionResult(ok=True, box=sample_face_box))
    stub = _StubProvider([VALID_RESPONSE])
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    storage.save_settings({"ai_enabled": True, "save_history": False})

    ok, buf = cv2.imencode(".jpg", sample_face_image)
    assert ok
    with TestClient(main.app) as client:
        resp = client.post("/api/analyze", files={"image": ("f.jpg", buf.tobytes(), "image/jpeg")})
        body = resp.json()
        assert body["faceDetected"] is True
        assert body["ai"] == "pending"
        # BackgroundTasks run synchronously within the TestClient's request/response cycle
        ai = client.get(f"/api/ai/{body['scan']['id']}").json()
        assert ai["status"] == "ready"
        assert "referral" in ai
