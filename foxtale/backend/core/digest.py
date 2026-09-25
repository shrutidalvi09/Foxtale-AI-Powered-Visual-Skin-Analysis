"""Weekly WhatsApp check-in: a short summary of your week, sent on the day and hour you choose.

It uses a WhatsApp *utility template* (default name foxtale_weekly) with four variables, because
WhatsApp only allows free-form messages inside 24 hours of the user's last message:
  {{1}} first name   {{2}} how your skin changed   {{3}} routine progress   {{4}} one tip
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core import effects, storage, whatsapp
from core.recommendations import build_recommendations
from engine.schemas import SkinAnalysis

logger = logging.getLogger("foxtale.digest")

# feature -> (label, lower is better)
FEATURES = {
    "acne": ("acne spots", True),
    "darkSpots": ("dark spots", True),
    "uniformity": ("tone uniformity", False),
    "poresScore": ("pore visibility", True),
}


def _feature_point(scan: dict) -> Dict[str, Optional[float]]:
    a, d = scan["analysis"], scan["analysis"].get("detail") or {}
    return {
        "overall": a.get("overall_score"),
        "acne": (d.get("acne") or {}).get("total", (a.get("acne_like_spots") or {}).get("count")),
        "darkSpots": (d.get("dark_spots") or {}).get("coverage_pct"),
        "uniformity": (d.get("uniformity") or {}).get("pct"),
        "poresScore": round(100 * (d.get("pores") or {}).get("score", 0)) if d.get("pores") else None,
    }


def _skin_line(scans: List[dict], now: datetime) -> str:
    """How the skin changed: latest scan versus the newest scan that is at least a week older."""
    if not scans:
        return "You have not scanned yet, so there is nothing to compare. A quick scan takes about 30 seconds."
    latest = scans[0]
    age_days = (now - datetime.fromisoformat(latest["timestamp"])).days
    older = [s for s in scans[1:] if (datetime.fromisoformat(latest["timestamp"]) - datetime.fromisoformat(s["timestamp"])).days >= 5]
    if age_days > 14:
        return f"Your last scan was {age_days} days ago. Scan again to see how your skin is doing now."
    if not older:
        score = latest["analysis"].get("overall_score")
        return f"Your latest skin score is {score}/100. Scan again in a week to start seeing changes." if score is not None else "Scan again in a week to start seeing changes."
    now_pt, then_pt = _feature_point(latest), _feature_point(older[0])
    parts = []
    if now_pt["overall"] is not None and then_pt["overall"] is not None:
        delta = int(now_pt["overall"] - then_pt["overall"])
        change = "the same as" if delta == 0 else f"{'up' if delta > 0 else 'down'} {abs(delta)} from"
        parts.append(f"Your skin score is {now_pt['overall']}/100, {change} your earlier scan.")
    best: Optional[Tuple[str, float]] = None
    for key, (label, lower) in FEATURES.items():
        a, b = now_pt.get(key), then_pt.get(key)
        if a is None or b is None or b == 0:
            continue
        change = (a - b) / abs(b)
        improvement = -change if lower else change
        if best is None or abs(improvement) > abs(best[1]):
            best = (f"{label} {'improved' if improvement > 0 else 'looks stronger'} ({round(abs(change) * 100)}%)", improvement)
    if best and abs(best[1]) >= 0.1:
        parts.append(best[0].capitalize() + ".")
    return " ".join(parts) or "Your skin looks steady compared with your earlier scan."


def _routine_line(now: datetime) -> str:
    since = (now.date() - timedelta(days=6)).isoformat()
    logged = storage.routine_days(since)
    days_done = sum(1 for v in logged.values() if v["AM"] or v["PM"])
    streak = 0
    for i in range(0, 60):
        d = (now.date() - timedelta(days=i)).isoformat()
        entry = storage.routine_days(d).get(d)
        if entry and (entry["AM"] or entry["PM"]):
            streak += 1
        elif i == 0:
            continue
        else:
            break
    if days_done == 0:
        return "You have not ticked your routine this week. Even a morning cleanse and sunscreen counts."
    return f"You did your routine on {days_done} of the last 7 days" + (f", a {streak}-day streak." if streak >= 2 else ".")


def _tip(scans: List[dict], now: datetime) -> str:
    working = [e for e in effects.compute(now) if e["status"] == "improving"]
    if working:
        return f"{working[0]['name']} seems to be working for you. Keep it up and stay consistent."
    if scans:
        try:
            tips = build_recommendations(SkinAnalysis.from_dict(scans[0]["analysis"]))
            return tips[now.isocalendar()[1] % len(tips)]
        except Exception:  # noqa: BLE001
            pass
    return "Use sunscreen every morning: it protects the results of everything else you do."


def build(now: Optional[datetime] = None) -> Dict[str, str]:
    now = now or datetime.now()
    scans = storage.list_scans()
    profile = storage.load_settings().get("profile") or {}
    name = (profile.get("name") or "").strip().split(" ")[0] or "there"
    return {"name": name, "skin": _skin_line(scans, now), "routine": _routine_line(now), "tip": _tip(scans, now)}


def is_due(now: datetime, settings: Dict[str, Any]) -> bool:
    if not (settings.get("weekly_digest") and settings.get("whatsapp_verified") and settings.get("whatsapp_number")):
        return False
    scheduled = now.replace(hour=int(settings.get("digest_hour", 9)), minute=0, second=0, microsecond=0)
    if now < scheduled:
        return False
    last = settings.get("digest_last_sent") or ""
    last_day: Optional[date] = date.fromisoformat(last[:10]) if last else None
    if last_day == now.date():
        return False
    if now.weekday() == int(settings.get("digest_day", 6)):
        return last_day is None or (now.date() - last_day).days >= 6
    # catch-up: the server was off on the chosen day, so send the next time it is up
    return last_day is not None and (now.date() - last_day).days >= 8


def send_now(now: Optional[datetime] = None) -> Tuple[bool, str]:
    """Send the digest immediately. Returns (ok, message)."""
    now = now or datetime.now()
    settings = storage.load_settings()
    if not (settings.get("whatsapp_verified") and settings.get("whatsapp_number")):
        return False, "Register your WhatsApp number first."
    parts = build(now)
    try:
        whatsapp.send_weekly(settings["whatsapp_number"], (parts["name"], parts["skin"], parts["routine"], parts["tip"]))
    except whatsapp.WhatsAppError as exc:
        logger.warning("Weekly digest failed: %s", exc)
        return False, str(exc)
    storage.save_settings({"digest_last_sent": now.isoformat()}, internal=True)
    return True, "Sent."


def maybe_send(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    if not is_due(now, storage.load_settings()):
        return False
    ok, _ = send_now(now)
    return ok
