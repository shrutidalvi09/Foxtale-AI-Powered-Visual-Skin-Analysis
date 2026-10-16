"""The Guide's output contract (see prompts/voice_assistant.v1.md) as a Pydantic model.

`ActionType` is a closed enum (`Literal[...]`), the same structural-guardrail pattern as
core/skin_ai_schema.py: the LLM cannot propose an action that does not exist in the app,
because no other string is a legal value. The app action is only ever *proposed* here --
core/guide_service.py decides whether it needs spoken confirmation, and the frontend is
the only thing that actually performs navigation or any state change.
"""

from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

ActionType = Literal[
    "navigate_dashboard", "navigate_scan", "navigate_analysis", "navigate_routine", "navigate_diary",
    "navigate_shop", "navigate_ingredient_check", "navigate_history", "navigate_compare",
    "navigate_privacy", "navigate_settings",
    "start_scan", "retake_photo", "show_last_scan", "compare_last_week", "explain_score",
    "repeat", "louder", "quieter", "stop_speaking", "mute", "unmute", "skip_guide",
    "wipe_data", "none",
]

Lang = Literal["en", "hi", "mr"]

# The only action in the list that destroys data without an easy undo -- every path that
# can propose it (local matcher or LLM) must also set needs_confirmation=True.
IRREVERSIBLE_ACTIONS = {"wipe_data"}

MAX_SPEECH_LEN = 400


class GuideAction(BaseModel):
    type: ActionType = "none"
    params: Dict[str, str] = Field(default_factory=dict)


class GuideReply(BaseModel):
    speech: str = Field(max_length=MAX_SPEECH_LEN)
    action: Optional[GuideAction] = None
    needs_confirmation: bool = False
    clarifying_question: Optional[str] = Field(default=None, max_length=MAX_SPEECH_LEN)
    lang: Lang = "en"

    # set by the pipeline, not by the model
    source: Literal["intent", "llm", "fallback"] = "llm"


def validate_reply(raw_json: str, lang: Lang) -> "tuple[Optional[GuideReply], Optional[str]]":
    """Parse + validate the model's raw JSON text. Returns (reply, None) on success, or
    (None, error) so the caller can retry once, mirroring the Skin Analyst's retry rule."""
    try:
        reply = GuideReply.model_validate_json(raw_json)
    except ValidationError as exc:
        return None, str(exc)[:600]
    except ValueError as exc:
        return None, f"Response was not valid JSON: {exc}"[:600]
    if reply.action and reply.action.type in IRREVERSIBLE_ACTIONS:
        reply.needs_confirmation = True
    reply.lang = lang
    reply.source = "llm"
    return reply, None
