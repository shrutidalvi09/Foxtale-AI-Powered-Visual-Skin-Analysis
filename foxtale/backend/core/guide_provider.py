"""Text-only LLM provider adapter for Fox, the voice assistant -- same adapter pattern as
core/skin_ai_provider.py, but `complete()` takes no image: Fox never receives the face
photo or any audio, only a short transcript and a plain-text app-state summary.
"""

import json
import logging
from typing import Protocol

from core.guide_config import CONFIG

logger = logging.getLogger("foxtale.guide")


class GuideProviderError(Exception):
    """A provider call failed. The message is safe to log."""


class TextLLMProvider(Protocol):
    name: str

    def complete(self, *, system_prompt: str, user_text: str) -> str:
        """Returns the model's raw text response (expected to be one JSON object)."""
        ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str):
        if not api_key:
            raise GuideProviderError("ANTHROPIC_API_KEY is not set.")
        try:
            import anthropic
        except ImportError as exc:
            raise GuideProviderError("The 'anthropic' package is not installed (pip install anthropic).") from exc
        self._client = anthropic.Anthropic(api_key=api_key, timeout=CONFIG.request_timeout_s)
        self._model = model

    def complete(self, *, system_prompt: str, user_text: str) -> str:
        import anthropic

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=CONFIG.max_output_tokens,
                temperature=CONFIG.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_text}],
            )
        except anthropic.APIError as exc:  # noqa: BLE001
            raise GuideProviderError(f"Anthropic API error: {type(exc).__name__}") from exc
        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        if not text_parts:
            raise GuideProviderError("Anthropic returned no text content.")
        return "".join(text_parts)


class MockProvider:
    """Dry-run / test provider: a canned, schema-valid reply with no network call."""

    name = "mock"

    def complete(self, *, system_prompt: str, user_text: str) -> str:
        del system_prompt
        logger.info("[GUIDE DRY RUN] called with %d chars of user text", len(user_text))
        lang = "en"
        for code in ("hi", "mr"):
            if f'"lang": "{code}"' in user_text or f"Spoken language: {code}" in user_text:
                lang = code
        speech = {
            "en": "I'm not totally sure what you meant, but I'm here for you! Want me to start a new scan?",
            "hi": "मुझे ठीक से समझ नहीं आया, पर मैं यहीं हूं तुम्हारे साथ! नया स्कैन शुरू करूं?",
            "mr": "मला नीट समजलं नाही, पण मी तुझ्यासोबत आहे! नवीन स्कॅन सुरू करू का?",
        }[lang]
        return json.dumps({"speech": speech, "action": None, "needs_confirmation": False,
                           "clarifying_question": None, "lang": lang})


def get_provider() -> TextLLMProvider:
    if CONFIG.dry_run or CONFIG.provider == "mock":
        return MockProvider()
    if CONFIG.provider == "anthropic":
        return AnthropicProvider(model=CONFIG.model, api_key=CONFIG.api_key)
    raise GuideProviderError(f"Unknown GUIDE_PROVIDER '{CONFIG.provider}'.")


def is_configured() -> bool:
    if CONFIG.dry_run:
        return True
    if CONFIG.provider == "anthropic":
        return bool(CONFIG.api_key)
    return False
