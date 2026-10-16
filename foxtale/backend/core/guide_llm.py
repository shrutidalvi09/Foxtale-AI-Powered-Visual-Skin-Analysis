"""Calls the configured text LLM for the voice Guide's fallback path (used only when
core.guide_intents could not confidently match a local command) and validates the result
against core.guide_schema, retrying once on a schema failure -- the same two-step pattern
as core.skin_ai_analyst._call_model.
"""

import logging
from typing import List, Optional, Tuple

from core import guide_provider as provider
from core.guide_config import CONFIG, system_prompt
from core.guide_provider import GuideProviderError
from core.guide_schema import GuideReply, Lang, validate_reply

logger = logging.getLogger("foxtale.guide")


def _build_user_text(page: str, state_summary: str, history: List[str], lang: Lang, transcript: str) -> str:
    history_text = " | ".join(history[-CONFIG.session_history_turns:]) if history else "(none yet)"
    return (
        f"Current screen: {page}\n"
        f"App state: {state_summary}\n"
        f"Recent turns (most recent last): {history_text}\n"
        f'Spoken language: {lang}\n'
        f'User said: "{transcript}"\n\n'
        "Reply with the JSON object described in the system prompt. JSON only."
    )


def ask(*, page: str, state_summary: str, history: List[str], lang: Lang, transcript: str) -> Tuple[Optional[GuideReply], str]:
    """Returns (reply_or_None, status: 'ready' | 'failed')."""
    llm = provider.get_provider()
    system = system_prompt()
    base_user_text = _build_user_text(page, state_summary, history, lang, transcript)
    attempts = [base_user_text]
    for attempt_n, user_text in enumerate(attempts, start=1):
        try:
            raw = llm.complete(system_prompt=system, user_text=user_text)
        except GuideProviderError as exc:
            logger.warning("Guide LLM call failed (attempt %d, provider=%s): %s", attempt_n, llm.name, exc)
            return None, "failed"
        reply, error = validate_reply(raw, lang)
        if reply is not None:
            return reply, "ready"
        logger.warning("Guide LLM response failed schema validation (attempt %d)", attempt_n)
        if attempt_n == 1:
            attempts.append(
                base_user_text + "\n\nYour previous response did not match the required JSON schema "
                f"({error}). Reply again with ONLY a single corrected JSON object, no other text."
            )
    return None, "failed"
