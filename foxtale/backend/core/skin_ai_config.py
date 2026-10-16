"""Central configuration for the Custom Skin AI module: model/provider choice, thresholds
and weights. Reading all of these from one place (env vars, with documented defaults) is
what the rest of `skin_ai_*` modules import, so nothing is hard-coded elsewhere.

Secrets (API keys) are read from the environment only -- see backend/.env.example.
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "skin_analyst.v1.md"
PROMPT_VERSION = "v1"


def _load_env_file() -> None:
    """Same convention as core/whatsapp.py: read backend/.env (if present) without overriding
    real environment variables, so the server never needs a process manager just to read it."""
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    # which VisionLLMProvider to use: "anthropic" | "mock" | "openai" | "gemini"
    provider: str = _env("AI_PROVIDER", "anthropic")
    # Vision-capable model name. Check your provider's current model list before relying on this.
    model: str = _env("AI_MODEL", "claude-sonnet-5")
    api_key: str = _env("ANTHROPIC_API_KEY")
    # Skips the network entirely and returns a canned, schema-valid result -- same idea as
    # WHATSAPP_DRY_RUN, so the whole feature can be tried with no account and no cost.
    dry_run: bool = _env("AI_DRY_RUN") in ("1", "true", "yes")
    temperature: float = 0.0  # lowest available: this is a measurement task, not creative writing
    max_output_tokens: int = _env_int("AI_MAX_OUTPUT_TOKENS", 1400)
    request_timeout_s: float = _env_float("AI_TIMEOUT_S", 45.0)

    # Privacy: send the smallest image that still works -- a tight crop around the face,
    # resized down, JPEG-recompressed (cv2.imencode drops EXIF/GPS as a side effect of
    # re-encoding, so no separate EXIF-stripping step is needed).
    image_max_dim: int = _env_int("AI_IMAGE_MAX_DIM", 512)
    image_jpeg_quality: int = _env_int("AI_IMAGE_JPEG_QUALITY", 82)
    image_padding_frac: float = 0.18  # extra margin around the face box, as a fraction of its size

    # Cost/abuse control.
    rate_limit_per_minute: int = _env_int("AI_RATE_LIMIT_PER_MIN", 6)
    cache_ttl_days: int = _env_int("AI_CACHE_TTL_DAYS", 30)

    # Confidence blending: final = min(image_quality_confidence, llm_confidence) * penalties.
    # image_quality_confidence comes from engine.quality.QualityResult.overall / 100.
    makeup_confidence_penalty: float = 0.6
    filter_confidence_penalty: float = 0.6
    min_confidence_floor: float = 0.05

    # Deterministic dermatologist-referral rule thresholds (core/skin_ai_referral.py).
    referral_min_marked_findings: int = 1  # any single "marked" finding triggers a referral note
    referral_min_moderate_plus_findings: int = 4  # or this many moderate-or-worse findings together
    referral_min_spot_count: int = 15  # measurement-only fallback when AI is off/unavailable


CONFIG = Config()


def system_prompt() -> str:
    """Everything in the versioned prompt file between '## System prompt' and '## User message' --
    the rules, vocabulary and output schema the model must follow. Read fresh each call (not
    cached at import time) so editing the .md file takes effect without restarting the server,
    the same way the WhatsApp templates are plain config rather than compiled-in strings."""
    full = PROMPT_PATH.read_text(encoding="utf-8")
    start = full.index("## System prompt")
    start = full.index("\n", start) + 1
    end = full.index("## User message")
    return full[start:end].strip()
