"""WhatsApp delivery through the Meta WhatsApp Cloud API.

Two message templates are used, because WhatsApp only allows free-form
messages inside a 24-hour window after the user last wrote to you:

  * an *authentication* template for the 6-digit verification code
  * a *utility* template with a PDF document header for the analysis report

Both are created (and approved) in Meta Business Manager -- see the README for
the exact text. All credentials come from environment variables or
backend/.env and never reach the browser.

Setting WHATSAPP_DRY_RUN=1 skips the network entirely: codes and reports are
written to the server log instead. It exists so the whole flow can be tried
before a Meta account is set up.
"""

import hashlib
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger("foxtale.whatsapp")

OTP_TTL_S = 10 * 60
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_S = 30
OTP_MAX_SENDS_PER_HOUR = 5
API_TIMEOUT_S = 30.0


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


def dry_run() -> bool:
    return _env("WHATSAPP_DRY_RUN") in ("1", "true", "yes")


def is_configured() -> bool:
    return dry_run() or bool(_env("WHATSAPP_TOKEN") and _env("WHATSAPP_PHONE_NUMBER_ID"))


class WhatsAppError(Exception):
    """A failure with a message that is safe to show the user."""

    def __init__(self, message: str, code: str = "send_failed", status: int = 502):
        super().__init__(message)
        self.code = code
        self.status = status


# ----------------------------------------------------------------- numbers

def normalize_phone(raw: str) -> Optional[str]:
    """Digits only in international format (country code first, no '+'), or None."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+"):
        return None  # a country code is required; guessing one could message a stranger
    digits = digits[1:]
    if not digits.isdigit() or not (8 <= len(digits) <= 15) or digits.startswith("0"):
        return None
    return digits


def mask_phone(phone: str) -> str:
    if not phone:
        return ""
    return f"+{phone[:2]}{'•' * max(3, len(phone) - 6)}{phone[-4:]}"


# --------------------------------------------------------------- Graph API

_ERROR_HINTS = {
    190: "The WhatsApp access token is invalid or expired. Update WHATSAPP_TOKEN on the server.",
    131030: "This number is not on the allowed recipient list for the WhatsApp test number. Add it in Meta's API setup page.",
    131026: "WhatsApp could not deliver to this number. Check that it is correct and has WhatsApp.",
    131047: "WhatsApp needs an approved message template for this chat.",
    132000: "The WhatsApp template parameters do not match the template.",
    132001: "The WhatsApp message template was not found or is not approved yet. Check its name and language.",
    132012: "The WhatsApp template parameter format is wrong.",
    100: "WhatsApp rejected the request. Check the phone number ID and template settings.",
}


def _graph(path: str, **kwargs: Any) -> Dict[str, Any]:
    version = _env("WHATSAPP_API_VERSION", "v21.0")
    url = f"https://graph.facebook.com/{version}/{_env('WHATSAPP_PHONE_NUMBER_ID')}/{path}"
    headers = {"Authorization": f"Bearer {_env('WHATSAPP_TOKEN')}"}
    try:
        res = httpx.post(url, headers=headers, timeout=API_TIMEOUT_S, **kwargs)
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp request failed: %s", exc)
        raise WhatsAppError("Could not reach WhatsApp. Check the server's internet connection.", "network") from exc
    if res.status_code >= 400:
        try:
            err = res.json().get("error", {})
        except ValueError:
            err = {}
        code = int(err.get("code", 0) or 0)
        logger.warning("WhatsApp API error %s: %s", res.status_code, err)
        raise WhatsAppError(_ERROR_HINTS.get(code) or err.get("message") or "WhatsApp rejected the message.", f"meta_{code}")
    return res.json()


def _template(name_env: str, default: str, to: str, components: list) -> Dict[str, Any]:
    return _graph("messages", json={
        "messaging_product": "whatsapp", "to": to, "type": "template",
        "template": {
            "name": _env(name_env, default),
            "language": {"code": _env("WHATSAPP_TEMPLATE_LANG", "en")},
            "components": components,
        },
    })


def send_otp(phone: str, code: str) -> None:
    if dry_run():
        logger.warning("[WHATSAPP DRY RUN] verification code for +%s is %s", phone, code)
        return
    _template("WHATSAPP_OTP_TEMPLATE", "foxtale_verify", phone, [
        {"type": "body", "parameters": [{"type": "text", "text": code}]},
        {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]},
    ])


def _param(text: str, limit: int = 500) -> Dict[str, str]:
    # template variables may not contain newlines, tabs or runs of spaces
    clean = re.sub(r"\s+", " ", text or "").strip() or "-"
    return {"type": "text", "text": clean[:limit]}


def send_report(phone: str, pdf: bytes, filename: str, params: Tuple[str, str, str, str]) -> None:
    """params: (score, summary, routine, date) -> template variables {{1}}..{{4}}."""
    if dry_run():
        logger.warning("[WHATSAPP DRY RUN] report to +%s (%d-byte PDF): %s", phone, len(pdf), params)
        return
    media = _graph("media", data={"messaging_product": "whatsapp", "type": "application/pdf"},
                   files={"file": (filename, pdf, "application/pdf")})
    media_id = media.get("id")
    if not media_id:
        raise WhatsAppError("WhatsApp did not accept the PDF upload.")
    _template("WHATSAPP_REPORT_TEMPLATE", "foxtale_report", phone, [
        {"type": "header", "parameters": [{"type": "document", "document": {"id": media_id, "filename": filename}}]},
        {"type": "body", "parameters": [_param(p) for p in params]},
    ])


def send_weekly(phone: str, params: Tuple[str, str, str, str]) -> None:
    """params: (first name, skin summary, routine summary, tip) -> template variables {{1}}..{{4}}."""
    if dry_run():
        logger.warning("[WHATSAPP DRY RUN] weekly check-in to +%s: %s", phone, params)
        return
    _template("WHATSAPP_WEEKLY_TEMPLATE", "foxtale_weekly", phone, [
        {"type": "body", "parameters": [_param(p, 400) for p in params]},
    ])


# --------------------------------------------------------------------- OTP

_lock = threading.Lock()
_pending: Dict[str, Any] = {}  # single pending registration: phone, hash, salt, expires, attempts
_sends: Dict[str, list] = {}  # phone -> timestamps of recent code sends


def _hash(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()


def start_verification(phone: str) -> None:
    now = time.time()
    with _lock:
        recent = [t for t in _sends.get(phone, []) if now - t < 3600]
        if recent and now - recent[-1] < OTP_RESEND_COOLDOWN_S:
            raise WhatsAppError("Please wait a few seconds before asking for another code.", "cooldown", 429)
        if len(recent) >= OTP_MAX_SENDS_PER_HOUR:
            raise WhatsAppError("Too many codes requested for this number. Try again in an hour.", "rate_limited", 429)
        code = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_hex(8)
        _pending.clear()
        _pending.update(phone=phone, hash=_hash(code, salt), salt=salt, expires=now + OTP_TTL_S, attempts=0)
        _sends[phone] = recent + [now]
    try:
        send_otp(phone, code)
    except WhatsAppError:
        with _lock:
            _pending.clear()
        raise


def check_code(code: str) -> str:
    """Returns the verified phone number, or raises WhatsAppError."""
    with _lock:
        if not _pending:
            raise WhatsAppError("Request a verification code first.", "no_pending", 400)
        if time.time() > _pending["expires"]:
            _pending.clear()
            raise WhatsAppError("That code has expired. Request a new one.", "expired", 400)
        _pending["attempts"] += 1
        if _pending["attempts"] > OTP_MAX_ATTEMPTS:
            _pending.clear()
            raise WhatsAppError("Too many wrong attempts. Request a new code.", "too_many_attempts", 429)
        if not secrets.compare_digest(_hash(code.strip(), _pending["salt"]), _pending["hash"]):
            raise WhatsAppError("That code is not right. Check it and try again.", "wrong_code", 400)
        phone = _pending["phone"]
        _pending.clear()
        return phone


def reset_state() -> None:
    """For tests."""
    with _lock:
        _pending.clear()
        _sends.clear()
