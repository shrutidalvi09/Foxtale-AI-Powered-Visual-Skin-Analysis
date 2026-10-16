"""Central configuration for the voice Guide module (text-only LLM fallback, intent
matching thresholds, rate limiting, session memory). Same env-var-with-defaults
convention as core/skin_ai_config.py -- see backend/.env.example.
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "voice_assistant.v1.md"
PROMPT_VERSION = "v1"


def _load_env_file() -> None:
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
    # which TextLLMProvider to use: "anthropic" | "mock"
    provider: str = _env("GUIDE_PROVIDER", "anthropic")
    model: str = _env("GUIDE_MODEL", "claude-sonnet-5")
    api_key: str = _env("ANTHROPIC_API_KEY")  # shared with the Skin Analyst; same account/key
    # Skips the network entirely and returns a canned, schema-valid reply -- same idea as
    # AI_DRY_RUN / WHATSAPP_DRY_RUN, so the whole feature can be tried with no account and no cost.
    dry_run: bool = _env("GUIDE_DRY_RUN") in ("1", "true", "yes")
    temperature: float = 0.2
    max_output_tokens: int = _env_int("GUIDE_MAX_OUTPUT_TOKENS", 300)
    request_timeout_s: float = _env_float("GUIDE_TIMEOUT_S", 15.0)

    # Cost/abuse control -- the LLM fallback path only; local intent matches never count.
    rate_limit_per_minute: int = _env_int("GUIDE_RATE_LIMIT_PER_MIN", 20)

    # Local fast-path intent matcher: minimum confidence to act without asking the LLM.
    intent_confidence_threshold: float = 0.6

    # Server-side short-term session memory (per browser tab), purely in-memory.
    session_ttl_minutes: int = _env_int("GUIDE_SESSION_TTL_MIN", 30)
    session_history_turns: int = 6

    # Opt-in transcript storage (text only, never audio) -- see storage.guide_transcripts.
    transcript_retention_days: int = _env_int("GUIDE_TRANSCRIPT_RETENTION_DAYS", 30)


CONFIG = Config()


def system_prompt() -> str:
    full = PROMPT_PATH.read_text(encoding="utf-8")
    start = full.index("## System prompt")
    start = full.index("\n", start) + 1
    end = full.index("## User message")
    return full[start:end].strip()
