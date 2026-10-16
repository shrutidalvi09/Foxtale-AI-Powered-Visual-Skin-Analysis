"""Orchestrates one turn with Fox, the voice assistant (module keeps its internal
`guide_*` name; "Fox" is the spoken/display name): consent check -> local intent match ->
(LLM fallback if needed) -> confirmation gating for irreversible actions -> optional
transcript logging.

Scope note: the small set of pure playback-control commands (repeat / louder / quieter /
stop speaking / mute / unmute / skip guide) never reach this module at all -- the frontend
(`lib/intentMatcher.ts`, mirroring the phrase lists in core.guide_intents) handles those
entirely client-side for zero-network, sub-100ms response, since they only ever change
local playback state the frontend already owns. Everything that touches app content or
navigation (start a scan, explain my score, open my diary, ...), plus anything that does
not match a known command at all, comes through here.

Session memory is in-process and keyed by a client-generated session id (one per browser
tab/session) -- there is no concept of a logged-in user in this app yet, so this mirrors
the same single-process, resets-on-restart pattern as core.skin_ai_analyst's rate limiter.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core import guide_intents, guide_llm
from core import guide_provider as provider
from core import storage
from core.guide_config import CONFIG
from core.guide_schema import GuideAction, GuideReply, Lang

logger = logging.getLogger("foxtale.guide")

_CANCEL_SPEECH = {"en": "Okay, cancelled! Nothing's changed, don't worry.",
                  "hi": "ठीक है, रद्द किया! कुछ नहीं बदला, चिंता मत करो।",
                  "mr": "ठीक आहे, रद्द केले! काहीही बदललं नाही, काळजी नको."}
_CONFIRM_DONE_SPEECH = {"en": "Done! All taken care of.", "hi": "हो गया! सब हो गया।", "mr": "झालं! सगळं झालं."}
_NOT_CONFIGURED_SPEECH = {
    "en": "I can handle the simple stuff, but I can't chat freely just yet. Try asking me to start a scan or open your diary!",
    "hi": "मैं आसान कमांड समझ सकती हूं, लेकिन अभी खुलकर बात नहीं कर सकती। \"स्कैन शुरू करो\" जैसा कुछ कहो।",
    "mr": "मी सोपे आदेश समजू शकते, पण अजून मोकळेपणाने बोलू शकत नाही. \"स्कॅन सुरू करा\" असं काही सांग.",
}
_RATE_LIMITED_SPEECH = {
    "en": "Whoa, I've been chatty! Give me just a moment and ask me again.",
    "hi": "अरे, मैं थोड़ी ज़्यादा बोल चुकी हूं! बस एक पल रुको और फिर पूछो।",
    "mr": "अरे, मी जरा जास्तच बोलले! जरा थांब आणि पुन्हा विचार.",
}
_GENERIC_FAILURE_SPEECH = {
    "en": "Hmm, I didn't quite catch that. Can you say it a different way?",
    "hi": "हम्म, मैं समझ नहीं पाई। क्या तुम इसे दूसरे तरीके से कह सकते हो?",
    "mr": "हम्म, मला ते समजलं नाही. तू ते वेगळ्या पद्धतीने सांगशील का?",
}
_VOICE_OFF_SPEECH = {
    "en": "I'm turned off right now -- flip me on in Settings and I'll be right here.",
    "hi": "मैं अभी बंद हूं -- सेटिंग्स में मुझे चालू करो, मैं यहीं हूं।",
    "mr": "मी आत्ता बंद आहे -- सेटिंग्जमध्ये मला सुरू कर, मी इथेच आहे.",
}
_NO_HISTORY_SPEECH = {
    "en": "I haven't said anything yet this time around!",
    "hi": "मैंने अभी तक कुछ कहा ही नहीं है!",
    "mr": "मी अजून काहीच सांगितलेलं नाही!",
}


@dataclass
class _Session:
    history: List[str] = field(default_factory=list)  # alternating "user: ..." / "guide: ..." lines
    last_speech: str = ""
    pending_action: Optional[Dict[str, Any]] = None
    updated: float = field(default_factory=time.monotonic)


_lock = threading.Lock()
_sessions: Dict[str, _Session] = {}
_recent_llm_calls: List[float] = []


def _prune_sessions() -> None:
    cutoff = time.monotonic() - CONFIG.session_ttl_minutes * 60
    stale = [sid for sid, s in _sessions.items() if s.updated < cutoff]
    for sid in stale:
        _sessions.pop(sid, None)


def _get_session(session_id: str) -> _Session:
    with _lock:
        _prune_sessions()
        session = _sessions.setdefault(session_id, _Session())
        session.updated = time.monotonic()
        return session


def _remember(session: _Session, user_text: str, reply_speech: str) -> None:
    session.history.append(f"user: {user_text}")
    if reply_speech:
        session.history.append(f"guide: {reply_speech}")
        session.last_speech = reply_speech
    session.history = session.history[-(CONFIG.session_history_turns * 2):]


def _rate_limited() -> bool:
    now = time.monotonic()
    with _lock:
        global _recent_llm_calls
        _recent_llm_calls = [t for t in _recent_llm_calls if now - t < 60.0]
        if len(_recent_llm_calls) >= CONFIG.rate_limit_per_minute:
            return True
        _recent_llm_calls.append(now)
        return False


# ------------------------------------------------------------------------------- consent

def status() -> Dict[str, Any]:
    s = storage.load_settings()
    return {
        "enabled": bool(s.get("voice_enabled")),
        "wakeWordEnabled": bool(s.get("wake_word_enabled")),
        "language": s.get("voice_language", "en"),
        "speed": float(s.get("voice_speed", 1.0)),
        "volume": float(s.get("voice_volume", 1.0)),
        "captionsEnabled": bool(s.get("captions_enabled", True)),
        "transcriptsConsent": bool(s.get("voice_transcripts_consent")),
        "configured": provider.is_configured(),
        "provider": CONFIG.provider,
        "model": CONFIG.model,
        "dryRun": CONFIG.dry_run,
        "disclosure": (
            "Your voice is converted to text on this device by your browser. Only that text (never "
            "raw audio) is sent to this server to match a command, and only sent on to an AI provider "
            f"({'a local test mode, no network call' if CONFIG.dry_run else CONFIG.provider}) when it "
            "isn't a simple command Fox already knows. Your face photo is never sent to her. "
            "Transcripts are kept only if you turn on 'Save voice transcripts' below."
        ),
    }


def set_status(patch: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "voice_enabled": "enabled", "wake_word_enabled": "wakeWordEnabled", "voice_language": "language",
        "voice_speed": "speed", "voice_volume": "volume", "captions_enabled": "captionsEnabled",
        "voice_transcripts_consent": "transcriptsConsent",
    }
    clean = {k: patch[v] for k, v in allowed.items() if v in patch}
    storage.save_settings(clean)
    return status()


# --------------------------------------------------------------------------------- asking

def _maybe_log_transcript(session_id: str, text: str, reply: GuideReply) -> None:
    if not storage.load_settings().get("voice_transcripts_consent"):
        return
    storage.guide_transcript_add(session_id, text[:500], reply.speech[:500],
                                 reply.action.type if reply.action else "none", datetime.now().isoformat())


def ask(*, session_id: str, text: str, lang: Lang, page: str, state_summary: str,
        confirm: Optional[bool] = None) -> Dict[str, Any]:
    settings = storage.load_settings()
    if not settings.get("voice_enabled"):
        return GuideReply(speech=_VOICE_OFF_SPEECH[lang], lang=lang, source="fallback").model_dump()

    text = (text or "").strip()[:500]
    session = _get_session(session_id)

    if confirm is not None and session.pending_action is not None:
        pending = session.pending_action
        session.pending_action = None
        if confirm:
            reply = GuideReply(speech=_CONFIRM_DONE_SPEECH[lang], action=GuideAction(**pending),
                               lang=lang, source="intent")
        else:
            reply = GuideReply(speech=_CANCEL_SPEECH[lang], action=None, lang=lang, source="intent")
        _remember(session, text, reply.speech)
        _maybe_log_transcript(session_id, text, reply)
        return reply.model_dump()

    if not text:
        reply = GuideReply(speech="", action=None, lang=lang, source="fallback")
        return reply.model_dump()

    local = guide_intents.match(text, lang)
    if local and local.confidence >= CONFIG.intent_confidence_threshold:
        if local.type == "repeat":
            speech = session.last_speech or _NO_HISTORY_SPEECH[lang]
            reply = GuideReply(speech=speech, action=None, lang=lang, source="intent")
            # "repeat" itself is never remembered as the new last_speech
            session.history.append(f"user: {text}")
            _maybe_log_transcript(session_id, text, reply)
            return reply.model_dump()
        if local.needs_confirmation:
            session.pending_action = {"type": local.type, "params": {}}
            reply = GuideReply(speech=local.speech, action=None, needs_confirmation=True, lang=lang, source="intent")
        else:
            action = None if local.type == "none" else GuideAction(type=local.type)
            reply = GuideReply(speech=local.speech, action=action, lang=lang, source="intent")
        _remember(session, text, reply.speech)
        _maybe_log_transcript(session_id, text, reply)
        return reply.model_dump()

    # No confident local match -- fall back to the LLM, subject to its own rate limit.
    if _rate_limited():
        reply = GuideReply(speech=_RATE_LIMITED_SPEECH[lang], action=None, lang=lang, source="fallback")
    elif not provider.is_configured():
        reply = GuideReply(speech=_NOT_CONFIGURED_SPEECH[lang], action=None, lang=lang, source="fallback")
    else:
        result, llm_status = guide_llm.ask(page=page, state_summary=state_summary, history=session.history,
                                           lang=lang, transcript=text)
        if result is None:
            reply = GuideReply(speech=_GENERIC_FAILURE_SPEECH[lang], action=None, lang=lang, source="fallback")
        else:
            reply = result
            if reply.needs_confirmation and reply.action:
                session.pending_action = reply.action.model_dump()
                reply.action = None

    _remember(session, text, reply.speech)
    _maybe_log_transcript(session_id, text, reply)
    return reply.model_dump()


def clear_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
