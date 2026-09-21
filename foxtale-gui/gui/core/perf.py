"""A small in-memory ring buffer of recent analysis-pipeline timings, so the
Settings page can show that on-device processing stays fast -- deliberately
not persisted to disk: this is a live diagnostic, not personal data, and it
naturally resets each time the app starts.
"""

from collections import deque
from typing import Optional

_HISTORY_SIZE = 20
_times_ms: deque = deque(maxlen=_HISTORY_SIZE)


def record_analysis_ms(elapsed_ms: float) -> None:
    _times_ms.append(elapsed_ms)


def get_stats() -> Optional[dict]:
    if not _times_ms:
        return None
    return {
        "count": len(_times_ms),
        "last": _times_ms[-1],
        "avg": sum(_times_ms) / len(_times_ms),
        "min": min(_times_ms),
        "max": max(_times_ms),
    }
