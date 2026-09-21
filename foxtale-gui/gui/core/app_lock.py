"""A simple local PIN lock for the app window. Not full-disk encryption or
OS-level authentication (that would need per-platform integration this
project doesn't have) -- it's a screen lock: while locked, scan history,
photos, and settings all still exist on disk exactly as before, just as the
main window is hidden behind a PIN prompt. The PIN itself is never stored in
plain text -- only a salted PBKDF2-HMAC-SHA256 hash.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

APP_DIR = Path.home() / ".foxtale_gui"
LOCK_PATH = APP_DIR / "app_lock.json"

_PBKDF2_ITERATIONS = 200_000


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _PBKDF2_ITERATIONS).hex()


def has_pin() -> bool:
    return LOCK_PATH.exists()


def set_pin(pin: str) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(16)
    LOCK_PATH.write_text(json.dumps({
        "salt": salt.hex(),
        "hash": _hash_pin(pin, salt),
    }))


def verify_pin(pin: str) -> bool:
    if not has_pin():
        return False
    try:
        data = json.loads(LOCK_PATH.read_text())
        salt = bytes.fromhex(data["salt"])
        return _hash_pin(pin, salt) == data["hash"]
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return False


def clear_pin() -> None:
    LOCK_PATH.unlink(missing_ok=True)
