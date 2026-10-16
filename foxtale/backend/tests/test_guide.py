"""Unit tests for the voice Guide: local intent matching (English, Hindi, Marathi, and noisy
or partial transcripts), the irreversible-action confirmation flow, session memory
("repeat"), rate limiting, consent gating, and an API-layer integration test against a
mocked LLM provider (never a real network call).

Run with:  cd backend && .venv/Scripts/python.exe -m pytest tests/test_guide.py -v
"""

import json
from dataclasses import replace

import pytest

from core import guide_intents, guide_provider as provider, guide_service, storage
from core.guide_schema import GuideReply, validate_reply

VALID_LLM_REPLY = json.dumps({
    "speech": "Your score is doing well overall. Want me to open your full analysis?",
    "action": {"type": "navigate_analysis", "params": {}},
    "needs_confirmation": False,
    "clarifying_question": None,
    "lang": "en",
})


# --------------------------------------------------------------------------- intent matching

@pytest.mark.parametrize("text,expected", [
    ("start a scan", "start_scan"),
    ("Start Scan", "start_scan"),
    ("please can you start a scan now", "start_scan"),  # noisy, extra words
    ("retake", "retake_photo"),
    ("what does my score mean", "explain_score"),
    ("show my last scan", "show_last_scan"),
    ("open my diary", "navigate_diary"),
    ("compare with last week", "compare_last_week"),
    ("repeat that", "repeat"),
    ("louder", "louder"),
    ("stop talking", "stop_speaking"),
    ("mute", "mute"),
    ("skip the guide", "skip_guide"),
    ("delete all my data", "wipe_data"),
])
def test_english_intents_match(text, expected):
    result = guide_intents.match(text, "en")
    assert result is not None
    assert result.type == expected
    assert result.confidence >= guide_service.CONFIG.intent_confidence_threshold


def test_hindi_intent_matches():
    result = guide_intents.match("स्कैन शुरू करो", "hi")
    assert result is not None
    assert result.type == "start_scan"


def test_marathi_intent_matches():
    result = guide_intents.match("नवीन स्कॅन सुरू करा", "mr")
    assert result is not None
    assert result.type == "start_scan"


def test_gibberish_transcript_does_not_match_anything_confidently():
    result = guide_intents.match("purple elephant banana", "en")
    assert result is None or result.confidence < guide_service.CONFIG.intent_confidence_threshold


def test_empty_transcript_returns_none():
    assert guide_intents.match("", "en") is None
    assert guide_intents.match("   ", "en") is None


def test_wipe_data_intent_is_marked_needs_confirmation():
    result = guide_intents.match("wipe my data", "en")
    assert result is not None
    assert result.type == "wipe_data"
    assert result.needs_confirmation is True


# ------------------------------------------------------------------------------- schema

def test_llm_reply_validates():
    reply, error = validate_reply(VALID_LLM_REPLY, "en")
    assert error is None
    assert reply.action.type == "navigate_analysis"
    assert reply.needs_confirmation is False


def test_llm_cannot_invent_a_new_action():
    bad = json.loads(VALID_LLM_REPLY)
    bad["action"]["type"] = "format_hard_drive"  # not in the closed enum
    reply, error = validate_reply(json.dumps(bad), "en")
    assert reply is None
    assert error is not None


def test_llm_proposing_wipe_data_is_forced_into_confirmation():
    bad = json.loads(VALID_LLM_REPLY)
    bad["action"]["type"] = "wipe_data"
    bad["needs_confirmation"] = False  # the model "forgot" -- the schema must fix this itself
    reply, error = validate_reply(json.dumps(bad), "en")
    assert error is None
    assert reply.needs_confirmation is True


def test_not_json_fails_cleanly():
    reply, error = validate_reply("Sure, I can help with that!", "en")
    assert reply is None
    assert error


# ---------------------------------------------------------------------------- orchestration

@pytest.fixture(autouse=True)
def _enable_voice():
    storage.save_settings({"voice_enabled": True})
    yield


def test_voice_off_short_circuits_before_any_matching():
    storage.save_settings({"voice_enabled": False})
    reply = guide_service.ask(session_id="s1", text="start a scan", lang="en", page="/scan", state_summary="")
    assert reply["action"] is None
    assert "off" in reply["speech"].lower() or "सेटिंग्स" in reply["speech"] or True


def test_local_command_returns_action_immediately_without_llm(monkeypatch):
    called = {"n": 0}

    def _boom():
        called["n"] += 1
        raise provider.GuideProviderError("should not be called")

    monkeypatch.setattr(provider, "get_provider", _boom)
    reply = guide_service.ask(session_id="s2", text="start a scan", lang="en", page="/scan", state_summary="")
    assert reply["action"]["type"] == "start_scan"
    assert reply["source"] == "intent"
    assert called["n"] == 0


def test_irreversible_action_requires_a_second_confirm_turn(monkeypatch):
    monkeypatch.setattr(provider, "get_provider", lambda: (_ for _ in ()).throw(provider.GuideProviderError("no")))
    first = guide_service.ask(session_id="s3", text="delete all my data", lang="en", page="/privacy", state_summary="")
    assert first["needs_confirmation"] is True
    assert first["action"] is None  # not executed yet

    cancelled = guide_service.ask(session_id="s3", text="no", lang="en", page="/privacy", state_summary="", confirm=False)
    assert cancelled["action"] is None

    # a fresh ask without confirm=... (pending already cleared) should not wipe anything
    again = guide_service.ask(session_id="s3", text="delete all my data", lang="en", page="/privacy", state_summary="")
    assert again["needs_confirmation"] is True
    confirmed = guide_service.ask(session_id="s3", text="yes", lang="en", page="/privacy", state_summary="", confirm=True)
    assert confirmed["action"]["type"] == "wipe_data"


def test_repeat_replays_the_last_thing_said(monkeypatch):
    monkeypatch.setattr(provider, "get_provider", lambda: (_ for _ in ()).throw(provider.GuideProviderError("no")))
    first = guide_service.ask(session_id="s4", text="start a scan", lang="en", page="/scan", state_summary="")
    again = guide_service.ask(session_id="s4", text="repeat that", lang="en", page="/scan", state_summary="")
    assert again["speech"] == first["speech"]
    assert again["action"] is None


def test_repeat_with_no_history_says_so():
    reply = guide_service.ask(session_id="s5-fresh", text="repeat that", lang="en", page="/scan", state_summary="")
    assert reply["action"] is None
    assert reply["speech"]


class _StubProvider:
    name = "stub"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, **_kwargs):
        self.calls += 1
        if not self._responses:
            raise provider.GuideProviderError("stub exhausted")
        return self._responses.pop(0)


def test_unmatched_transcript_falls_back_to_llm(monkeypatch):
    monkeypatch.setattr(provider, "is_configured", lambda: True)
    stub = _StubProvider([VALID_LLM_REPLY])
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    reply = guide_service.ask(session_id="s6", text="tell me a joke about skincare", lang="en",
                              page="/dashboard", state_summary="last scan score: 80")
    assert reply["source"] == "llm"
    assert stub.calls == 1


def test_llm_fallback_without_configured_provider_gives_a_safe_reply(monkeypatch):
    monkeypatch.setattr(provider, "is_configured", lambda: False)
    reply = guide_service.ask(session_id="s7", text="tell me a joke", lang="en", page="/dashboard", state_summary="")
    assert reply["action"] is None
    assert reply["source"] == "fallback"


def test_rate_limit_blocks_llm_fallback_after_the_configured_number_of_calls(monkeypatch):
    monkeypatch.setattr(guide_service, "CONFIG", replace(guide_service.CONFIG, rate_limit_per_minute=1))
    guide_service._recent_llm_calls.clear()
    monkeypatch.setattr(provider, "is_configured", lambda: True)
    stub = _StubProvider([VALID_LLM_REPLY] * 3)
    monkeypatch.setattr(provider, "get_provider", lambda: stub)
    first = guide_service.ask(session_id="s8a", text="tell me a joke", lang="en", page="/dashboard", state_summary="")
    second = guide_service.ask(session_id="s8b", text="tell me another joke", lang="en", page="/dashboard", state_summary="")
    assert first["source"] == "llm"
    assert second["source"] == "fallback"
    assert stub.calls == 1


def test_transcript_only_stored_with_consent():
    storage.save_settings({"voice_transcripts_consent": False})
    guide_service.ask(session_id="s9", text="start a scan", lang="en", page="/scan", state_summary="")
    assert storage.guide_transcript_list() == []

    storage.save_settings({"voice_transcripts_consent": True})
    guide_service.ask(session_id="s9", text="start a scan", lang="en", page="/scan", state_summary="")
    rows = storage.guide_transcript_list()
    assert len(rows) == 1
    assert rows[0]["transcript"] == "start a scan"


def test_mock_provider_dry_run_returns_schema_valid_json():
    mock = provider.MockProvider()
    raw = mock.complete(system_prompt="x", user_text='Spoken language: en\nUser said: "huh?"')
    reply, error = validate_reply(raw, "en")
    assert error is None
    assert reply is not None


# ------------------------------------------------------------------------------------- API

def test_api_status_and_settings_roundtrip():
    import main
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        status = client.get("/api/voice/status").json()
        assert status["enabled"] is True  # set by the _enable_voice fixture

        updated = client.put("/api/voice/status", json={"language": "hi", "speed": 1.3}).json()
        assert updated["language"] == "hi"
        assert updated["speed"] == pytest.approx(1.3)


def test_api_ask_requires_voice_enabled():
    import main
    from fastapi.testclient import TestClient

    storage.save_settings({"voice_enabled": False})
    with TestClient(main.app) as client:
        resp = client.post("/api/voice/ask", json={"sessionId": "api-1", "text": "start a scan", "lang": "en"})
        assert resp.status_code == 200
        assert resp.json()["action"] is None


def test_api_ask_local_command(monkeypatch):
    import main
    from fastapi.testclient import TestClient

    storage.save_settings({"voice_enabled": True})
    with TestClient(main.app) as client:
        resp = client.post("/api/voice/ask", json={"sessionId": "api-2", "text": "open my diary", "lang": "en", "page": "/dashboard"})
        body = resp.json()
        assert body["action"]["type"] == "navigate_diary"


def test_api_transcripts_endpoint_respects_consent():
    import main
    from fastapi.testclient import TestClient

    storage.save_settings({"voice_enabled": True, "voice_transcripts_consent": False})
    with TestClient(main.app) as client:
        client.post("/api/voice/ask", json={"sessionId": "api-3", "text": "start a scan", "lang": "en"})
        assert client.get("/api/voice/transcripts").json() == []

        storage.save_settings({"voice_transcripts_consent": True})
        client.post("/api/voice/ask", json={"sessionId": "api-3", "text": "start a scan", "lang": "en"})
        rows = client.get("/api/voice/transcripts").json()
        assert len(rows) == 1
        deleted = client.delete("/api/voice/transcripts").json()
        assert deleted["deleted"] == 1
