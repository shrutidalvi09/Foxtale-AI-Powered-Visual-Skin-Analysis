"""Dashboard insights computed from a user's scan history (newest-first list of
scan dicts as returned by core.storage). Worded as visible-score trends across
photos, never as a medical trend.
"""

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.schemas import LEVEL_SCORE

CATEGORIES = [
    ("Acne-like spots", "acne_like_spots"),
    ("Redness", "redness"),
    ("Texture", "texture"),
    ("Dryness indicators", "dryness_indicators"),
]

STREAK_GAP_DAYS = 10
SCAN_MILESTONES = [1, 5, 10, 25, 50]
STREAK_MILESTONES = [3, 7, 14, 30]


def _level(scan: dict, key: str) -> int:
    return LEVEL_SCORE[scan["analysis"][key]["level"]]


def _window_avg(scans: List[dict], key: str, size: int) -> float:
    window = scans[:size]
    return sum(_level(s, key) for s in window) / len(window)


def _streak(chronological: List[dict]) -> int:
    if not chronological:
        return 0
    streak = 1
    for i in range(len(chronological) - 1, 0, -1):
        gap = (datetime.fromisoformat(chronological[i]["timestamp"])
               - datetime.fromisoformat(chronological[i - 1]["timestamp"])).days
        if gap <= STREAK_GAP_DAYS:
            streak += 1
        else:
            break
    return streak


def baseline(scans: List[dict]) -> Dict[str, str]:
    """The user's own most common level per category ("your usual")."""
    out: Dict[str, str] = {}
    for label, key in CATEGORIES:
        if not scans:
            out[label] = "minimal"
            continue
        counts = Counter(s["analysis"][key]["level"] for s in scans)
        top = max(counts.values())
        out[label] = min((lvl for lvl, c in counts.items() if c == top), key=lambda lvl: LEVEL_SCORE[lvl])
    return out


def compute(scans: List[dict]) -> Dict[str, Any]:
    total = len(scans)
    chronological = list(reversed(scans))
    streak = _streak(chronological)
    badges = [{"label": "First Scan" if n == 1 else f"{n} Scans", "kind": "scans", "earned": total >= n}
              for n in SCAN_MILESTONES]
    badges += [{"label": f"{n}-Scan Streak", "kind": "streak", "earned": streak >= n} for n in STREAK_MILESTONES]

    result: Dict[str, Any] = {
        "totalScans": total, "streak": streak, "badges": badges,
        "firstScan": chronological[0]["timestamp"] if chronological else None,
        "lastScan": chronological[-1]["timestamp"] if chronological else None,
        "daysSinceLast": None, "trends": [], "scoreSeries": [],
        "mostFrequentRegion": None, "mostFrequentCategory": None,
        "headline": "Scan your face a few times to start seeing insights here.",
    }
    if not scans:
        return result

    result["daysSinceLast"] = (datetime.now() - datetime.fromisoformat(scans[0]["timestamp"])).days
    result["scoreSeries"] = [
        {"timestamp": s["timestamp"], "score": s["analysis"].get("overall_score")} for s in chronological
    ]
    regions = Counter(r["region"] for s in scans for r in s["regions"])
    cats = Counter(r["category"] for s in scans for r in s["regions"])
    result["mostFrequentRegion"] = regions.most_common(1)[0][0].title() if regions else None
    result["mostFrequentCategory"] = cats.most_common(1)[0][0] if cats else None

    if total < 2:
        result["headline"] = "One scan recorded so far. Take another in a few days to start tracking trends."
        return result

    size = min(3, total // 2) or 1
    trends = []
    for label, key in CATEGORIES:
        recent, early = _window_avg(scans, key, size), _window_avg(chronological, key, size)
        direction = "improved" if recent < early - 0.15 else "worsened" if recent > early + 0.15 else "stable"
        trends.append({
            "label": label, "direction": direction,
            "earlyLevel": chronological[0]["analysis"][key]["level"],
            "recentLevel": chronological[-1]["analysis"][key]["level"],
        })
    result["trends"] = trends
    improved = [t["label"] for t in trends if t["direction"] == "improved"]
    worsened = [t["label"] for t in trends if t["direction"] == "worsened"]
    if improved and not worsened:
        result["headline"] = f"Visible improvement in {', '.join(improved).lower()} since your first scan."
    elif worsened and not improved:
        result["headline"] = (f"{', '.join(worsened)} has looked more noticeable since your first scan. "
                              "Worth keeping an eye on.")
    elif improved and worsened:
        result["headline"] = (f"Mixed picture: {', '.join(improved).lower()} improved, while "
                              f"{', '.join(worsened).lower()} looked more noticeable.")
    else:
        result["headline"] = "Your visible skin metrics have stayed fairly stable across scans."
    return result
