"""Vision-LLM provider adapter: one small interface so the Skin Analyst can call any
vision-capable chat model behind the same `complete()` method. Swap providers with the
`AI_PROVIDER` environment variable (see core/skin_ai_config.py); no other code changes.

Only Anthropic is a real, working implementation today (`AnthropicProvider`) -- OpenAI and
Gemini are left as clearly-marked stubs with the same interface, since this project has no
existing key for either and wiring up SDKs that can never be exercised here would be
untested dead code. `MockProvider` is the dry-run path (mirrors `WHATSAPP_DRY_RUN`): no
network call, no cost, used for local trials and for every automated test in
`backend/tests/test_skin_ai.py`.
"""

import base64
import json
import logging
from typing import Protocol

from core.skin_ai_config import CONFIG

logger = logging.getLogger("foxtale.skin_ai")


class AiProviderError(Exception):
    """A provider call failed. The message is safe to log (never includes the raw response)."""


class VisionLLMProvider(Protocol):
    name: str

    def complete(self, *, system_prompt: str, user_text: str, image_bytes: bytes, image_media_type: str) -> str:
        """Returns the model's raw text response (expected to be one JSON object)."""
        ...


class AnthropicProvider:
    """Calls the Anthropic Messages API with vision input. Requires `anthropic` (see
    requirements.txt) and `ANTHROPIC_API_KEY` in the environment or backend/.env."""

    name = "anthropic"

    def __init__(self, model: str, api_key: str):
        if not api_key:
            raise AiProviderError("ANTHROPIC_API_KEY is not set.")
        try:
            import anthropic  # local import: keep the dependency optional for providers that don't need it
        except ImportError as exc:
            raise AiProviderError("The 'anthropic' package is not installed (pip install anthropic).") from exc
        self._client = anthropic.Anthropic(api_key=api_key, timeout=CONFIG.request_timeout_s)
        self._model = model

    def complete(self, *, system_prompt: str, user_text: str, image_bytes: bytes, image_media_type: str) -> str:
        import anthropic

        b64 = base64.b64encode(image_bytes).decode("ascii")
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=CONFIG.max_output_tokens,
                temperature=CONFIG.temperature,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": image_media_type, "data": b64}},
                        {"type": "text", "text": user_text},
                    ],
                }],
            )
        except anthropic.APIError as exc:  # noqa: BLE001 - normalise every SDK failure to AiProviderError
            raise AiProviderError(f"Anthropic API error: {type(exc).__name__}") from exc
        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        if not text_parts:
            raise AiProviderError("Anthropic returned no text content.")
        return "".join(text_parts)


class MockProvider:
    """Dry-run / test provider: returns a canned, schema-valid response with no network call.
    The canned findings are intentionally mild and generic -- this exists to exercise the
    pipeline (caching, validation, confidence blending, storage, UI), not to simulate a real
    assessment of any particular photo."""

    name = "mock"

    def complete(self, *, system_prompt: str, user_text: str, image_bytes: bytes, image_media_type: str) -> str:
        del system_prompt, image_bytes, image_media_type  # unused: the mock ignores the actual photo
        logger.info("[AI DRY RUN] Skin Analyst called with %d chars of user text", len(user_text))
        return json.dumps({
            "findings": [
                {"id": "f1", "region": "left cheek", "type": "redness", "severity": "mild",
                 "evidence": "A slightly pinker area is visible on the left cheek.", "confidence": 0.55},
                {"id": "f2", "region": "nose", "type": "pore_visibility", "severity": "mild",
                 "evidence": "Pores look a little more visible around the nose.", "confidence": 0.5},
            ],
            "overall_summary": "Overall the skin looks fairly even, with mild redness on one cheek and "
                               "slightly visible pores around the nose. Nothing stands out as prominent.",
            "routine_suggestions": [
                {"goal": "redness", "suggestion": "A fragrance-free, gentle moisturizer can help calm mild redness."},
            ],
            "lifestyle_notes": ["Daily sunscreen helps keep tone even over time."],
            "retake_advice": None,
            "safety_flags": [],
            "image_notes": {"makeup_suspected": False, "filtered_or_edited_suspected": False},
        })


class _NotImplementedProvider:
    name = "not_implemented"

    def __init__(self, label: str, hint: str):
        self._label, self._hint = label, hint

    def complete(self, **_kwargs) -> str:
        raise AiProviderError(f"The {self._label} provider is not implemented yet. {self._hint}")


def get_provider() -> VisionLLMProvider:
    """Factory: builds the configured provider. Never raises for a missing key at import time --
    only when actually used, so the rest of the app keeps working with AI simply turned off."""
    if CONFIG.dry_run or CONFIG.provider == "mock":
        return MockProvider()
    if CONFIG.provider == "anthropic":
        return AnthropicProvider(model=CONFIG.model, api_key=CONFIG.api_key)
    if CONFIG.provider == "openai":
        return _NotImplementedProvider(
            "openai", "Add the 'openai' package and implement complete() the same way AnthropicProvider does.",
        )
    if CONFIG.provider == "gemini":
        return _NotImplementedProvider(
            "gemini", "Add the 'google-generativeai' package and implement complete() the same way AnthropicProvider does.",
        )
    raise AiProviderError(f"Unknown AI_PROVIDER '{CONFIG.provider}'.")


def is_configured() -> bool:
    """Whether a real call can actually be made (used by the UI to explain why AI is off)."""
    if CONFIG.dry_run:
        return True
    if CONFIG.provider == "anthropic":
        return bool(CONFIG.api_key)
    return False
