"""Rule-based insights derived from scan history: per-category trend
direction (comparing early vs. recent scans), a scanning-consistency streak,
and a plain-language summary line. All phrasing stays in the app's
established "visible observation, not diagnosis" voice -- this module never
claims to detect a medical trend, only a visible-score trend across photos.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from engine.schemas import LEVEL_SCORE
from gui.core.storage import ScanRecord

CATEGORY_LABELS = [
    ("Acne-like spots", lambda a: a.acne_like_spots),
    ("Redness", lambda a: a.redness),
    ("Texture", lambda a: a.texture),
    ("Dryness indicators", lambda a: a.dryness_indicators),
]

# A scan continues a "streak" if it follows the previous one within this many
# days -- a fixed, generic default (not tied to the user's reminder cadence
# setting, so streaks stay meaningful even if that setting changes later).
STREAK_GAP_DAYS = 10

SCAN_COUNT_MILESTONES = [1, 5, 10, 25, 50]
STREAK_MILESTONES = [3, 7, 14, 30]


@dataclass
class Badge:
    icon: str
    label: str
    earned: bool


@dataclass
class CategoryTrend:
    label: str
    direction: str  # "improved" | "worsened" | "stable"
    early_level: str
    recent_level: str


@dataclass
class InsightsResult:
    total_scans: int
    first_scan: Optional[str]
    last_scan: Optional[str]
    span_days: int
    avg_days_between_scans: Optional[float]
    trends: List[CategoryTrend]
    headline: str
    longest_streak: int = 0
    most_frequent_region: Optional[str] = None
    most_frequent_category: Optional[str] = None
    best_scan_date: Optional[str] = None


def _window_average(records: List[ScanRecord], getter, size: int) -> float:
    window = records[:size]
    return sum(LEVEL_SCORE[getter(r.analysis).level] for r in window) / len(window)


def _longest_streak(chronological: List[ScanRecord]) -> int:
    """The current streak, counted backward from the most recent scan."""
    if not chronological:
        return 0
    streak = 1
    for i in range(len(chronological) - 1, 0, -1):
        gap = (
            datetime.fromisoformat(chronological[i].timestamp)
            - datetime.fromisoformat(chronological[i - 1].timestamp)
        ).days
        if gap <= STREAK_GAP_DAYS:
            streak += 1
        else:
            break
    return streak


def _most_frequent_region(records: List[ScanRecord]) -> Optional[str]:
    counts = Counter(r.region for record in records for r in record.regions)
    if not counts:
        return None
    return counts.most_common(1)[0][0].title()


def _most_frequent_category(records: List[ScanRecord]) -> Optional[str]:
    counts = Counter(r.category for record in records for r in record.regions)
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _best_scan_date(records: List[ScanRecord]) -> Optional[str]:
    """The scan with the lowest average severity across all four categories."""
    if not records:
        return None
    def avg_score(r: ScanRecord) -> float:
        return sum(LEVEL_SCORE[getter(r.analysis).level] for _, getter in CATEGORY_LABELS) / len(CATEGORY_LABELS)
    best = min(records, key=avg_score)
    return best.timestamp


def compute_badges(records: List[ScanRecord]) -> List[Badge]:
    """Milestone badges for scan count and consistency streak -- a light
    gamification layer, ordered easiest-to-earn first so the UI can show
    "what's next" by picking the first unearned one."""
    total = len(records)
    streak = _longest_streak(list(reversed(records))) if records else 0

    badges: List[Badge] = []
    for n in SCAN_COUNT_MILESTONES:
        label = "First Scan" if n == 1 else f"{n} Scans"
        badges.append(Badge(icon="fa5s.camera", label=label, earned=total >= n))
    for n in STREAK_MILESTONES:
        badges.append(Badge(icon="fa5s.fire", label=f"{n}-Scan Streak", earned=streak >= n))
    return badges


def compute_baseline(records: List[ScanRecord]) -> Dict[str, str]:
    """Your personal "typical" level per category (the most common level
    across your own history) -- used to say "higher than your usual" rather
    than judging every scan against one fixed threshold for everyone."""
    baseline: Dict[str, str] = {}
    for label, getter in CATEGORY_LABELS:
        if not records:
            baseline[label] = "minimal"
            continue
        counts = Counter(getter(r.analysis).level for r in records)
        top_count = max(counts.values())
        # Tie-break toward the mildest level among the most-common ones.
        tied = [level for level, c in counts.items() if c == top_count]
        baseline[label] = min(tied, key=lambda lvl: LEVEL_SCORE[lvl])
    return baseline


def compute_insights(records: List[ScanRecord]) -> InsightsResult:
    """`records` must be ordered newest-first (as storage.list_scans() returns)."""
    if not records:
        return InsightsResult(0, None, None, 0, None, [], "Scan your face a few times to start seeing insights here.")

    chronological = list(reversed(records))  # oldest -> newest
    first, last = chronological[0], chronological[-1]
    span_days = (datetime.fromisoformat(last.timestamp) - datetime.fromisoformat(first.timestamp)).days

    avg_gap = None
    if len(chronological) > 1:
        avg_gap = span_days / (len(chronological) - 1)

    if len(records) < 2:
        return InsightsResult(
            total_scans=len(records), first_scan=first.timestamp, last_scan=last.timestamp,
            span_days=span_days, avg_days_between_scans=avg_gap, trends=[],
            headline="One scan recorded so far — take another in a few days to start tracking trends.",
            longest_streak=1, most_frequent_region=_most_frequent_region(records),
            most_frequent_category=_most_frequent_category(records), best_scan_date=first.timestamp,
        )

    window_size = min(3, len(records) // 2) or 1
    trends: List[CategoryTrend] = []
    for label, getter in CATEGORY_LABELS:
        recent_avg = _window_average(records, getter, window_size)  # records: newest-first
        early_avg = _window_average(chronological, getter, window_size)  # chronological: oldest-first
        if recent_avg < early_avg - 0.15:
            direction = "improved"
        elif recent_avg > early_avg + 0.15:
            direction = "worsened"
        else:
            direction = "stable"
        trends.append(CategoryTrend(
            label=label,
            direction=direction,
            early_level=getter(first.analysis).level,
            recent_level=getter(last.analysis).level,
        ))

    improved = [t.label for t in trends if t.direction == "improved"]
    worsened = [t.label for t in trends if t.direction == "worsened"]

    if improved and not worsened:
        headline = f"Visible improvement in {', '.join(improved).lower()} since your first scan."
    elif worsened and not improved:
        headline = f"{', '.join(worsened)} has looked more noticeable since your first scan — worth keeping an eye on."
    elif improved and worsened:
        headline = f"Mixed picture: {', '.join(improved).lower()} improved, while {', '.join(worsened).lower()} looked more noticeable."
    else:
        headline = "Your visible skin metrics have stayed fairly stable across scans."

    return InsightsResult(
        total_scans=len(records), first_scan=first.timestamp, last_scan=last.timestamp,
        span_days=span_days, avg_days_between_scans=avg_gap, trends=trends, headline=headline,
        longest_streak=_longest_streak(chronological), most_frequent_region=_most_frequent_region(records),
        most_frequent_category=_most_frequent_category(records), best_scan_date=_best_scan_date(records),
    )
