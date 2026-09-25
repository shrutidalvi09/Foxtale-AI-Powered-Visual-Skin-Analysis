"""Skin diary: daily habits and how the skin felt, and the patterns between them.

Patterns are simple comparisons in your own data (for example "skin felt worse the day after a night
with under 6 hours of sleep"). They show associations, not causes, and need several logged days.
"""

from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

FLAGS = {
    "dairy": "dairy", "sugar": "sugary food", "oily_food": "oily or fried food", "alcohol": "alcohol", "spicy": "spicy food",
    "sun_exposure": "a lot of sun", "makeup": "wearing makeup", "workout": "a workout", "period": "your period",
}
MIN_GROUP = 3  # days in each group before we say anything
MIN_DIFF = 0.5  # on the 1-5 "how did your skin feel" scale


def _prev(day: str) -> str:
    return (date.fromisoformat(day) - timedelta(days=1)).isoformat()


def clean(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Validate one diary entry from the browser."""
    def num(v, lo, hi):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return max(lo, min(hi, f))

    out: Dict[str, Any] = {}
    sleep = num(entry.get("sleep_hours"), 0, 14)
    water = num(entry.get("water_glasses"), 0, 30)
    stress = num(entry.get("stress"), 1, 5)
    feel = num(entry.get("skin_feel"), 1, 5)
    if sleep is not None:
        out["sleep_hours"] = round(sleep * 2) / 2
    if water is not None:
        out["water_glasses"] = int(water)
    if stress is not None:
        out["stress"] = int(stress)
    if feel is not None:
        out["skin_feel"] = int(feel)
    out["flags"] = sorted({f for f in entry.get("flags", []) if f in FLAGS})
    out["note"] = str(entry.get("note", ""))[:500]
    return out


def _avg(xs: List[float]) -> float:
    return round(mean(xs), 2)


def _compare(exposed: List[float], other: List[float]) -> Optional[Tuple[float, float]]:
    if len(exposed) < MIN_GROUP or len(other) < MIN_GROUP:
        return None
    a, b = mean(exposed), mean(other)
    return (a, b) if abs(a - b) >= MIN_DIFF else None


def patterns(entries: Dict[str, Dict[str, Any]], scans: List[dict]) -> Dict[str, Any]:
    """entries: {day: cleaned entry}; scans: newest-first scan dicts."""
    days = sorted(entries)
    with_feel = [d for d in days if "skin_feel" in entries[d]]
    streak = 0
    d = date.today()
    if d.isoformat() not in entries:
        d -= timedelta(days=1)
    while d.isoformat() in entries:
        streak += 1
        d -= timedelta(days=1)

    insights: List[Dict[str, Any]] = []

    def add(factor: str, title: str, text: str, better: bool, n: int) -> None:
        insights.append({"factor": factor, "title": title, "text": text, "direction": "better" if better else "worse",
                         "confidence": "medium" if n >= 12 else "low", "n": n})

    def feels(days_sel: List[str]) -> List[float]:
        return [float(entries[x]["skin_feel"]) for x in days_sel]

    # sleep (recorded on the same day: last night's sleep)
    poor = [x for x in with_feel if entries[x].get("sleep_hours") is not None and entries[x]["sleep_hours"] < 6]
    good = [x for x in with_feel if entries[x].get("sleep_hours") is not None and entries[x]["sleep_hours"] >= 7]
    cmp = _compare(feels(poor), feels(good))
    if cmp:
        add("sleep", "Sleep", f"Your skin felt {'worse' if cmp[0] < cmp[1] else 'better'} on days after under 6 hours of sleep ({_avg(feels(poor))}/5) than after 7 or more hours ({_avg(feels(good))}/5).", cmp[0] > cmp[1], len(poor) + len(good))

    # water and stress: the day before
    def lag_days(pred) -> List[str]:
        return [x for x in with_feel if _prev(x) in entries and pred(entries[_prev(x)])]

    low_w = lag_days(lambda e: e.get("water_glasses") is not None and e["water_glasses"] < 5)
    hi_w = lag_days(lambda e: e.get("water_glasses") is not None and e["water_glasses"] >= 7)
    cmp = _compare(feels(low_w), feels(hi_w))
    if cmp:
        add("water", "Water", f"Skin felt {'worse' if cmp[0] < cmp[1] else 'better'} the day after drinking under 5 glasses ({_avg(feels(low_w))}/5) than after 7 or more ({_avg(feels(hi_w))}/5).", cmp[0] > cmp[1], len(low_w) + len(hi_w))
    hi_s = lag_days(lambda e: e.get("stress") is not None and e["stress"] >= 4)
    lo_s = lag_days(lambda e: e.get("stress") is not None and e["stress"] <= 2)
    cmp = _compare(feels(hi_s), feels(lo_s))
    if cmp:
        add("stress", "Stress", f"Skin felt {'worse' if cmp[0] < cmp[1] else 'better'} the day after a high-stress day ({_avg(feels(hi_s))}/5) than after a calm one ({_avg(feels(lo_s))}/5).", cmp[0] > cmp[1], len(hi_s) + len(lo_s))

    # yes/no habits
    for flag, label in FLAGS.items():
        if flag == "period":  # same day
            yes = [x for x in with_feel if flag in entries[x].get("flags", [])]
            no = [x for x in with_feel if flag not in entries[x].get("flags", [])]
        else:
            yes = lag_days(lambda e, f=flag: f in e.get("flags", []))
            no = lag_days(lambda e, f=flag: f not in e.get("flags", []))
        cmp = _compare(feels(yes), feels(no))
        if cmp:
            when = "on" if flag == "period" else "the day after"
            add(flag, label.capitalize(), f"Skin felt {'worse' if cmp[0] < cmp[1] else 'better'} {when} {label} ({_avg(feels(yes))}/5) than otherwise ({_avg(feels(no))}/5).", cmp[0] > cmp[1], len(yes) + len(no))

    # scans: acne count after low-sleep or sugary days (needs several scans with diary cover)
    scan_notes: List[Dict[str, Any]] = []
    rows = []
    for s in scans:
        sd = s["timestamp"][:10]
        prior = [entries[x] for x in ((date.fromisoformat(sd) - timedelta(days=i)).isoformat() for i in (1, 2, 3)) if x in entries]
        if len(prior) < 2:
            continue
        acne = ((s["analysis"].get("detail") or {}).get("acne") or {}).get("total", (s["analysis"].get("acne_like_spots") or {}).get("count"))
        if acne is None:
            continue
        sleeps = [e["sleep_hours"] for e in prior if e.get("sleep_hours") is not None]
        rows.append({"acne": float(acne), "sleep": mean(sleeps) if sleeps else None,
                     "sweet": sum(1 for e in prior if {"sugar", "dairy"} & set(e.get("flags", []))) >= 2})
    lows = [r["acne"] for r in rows if r["sleep"] is not None and r["sleep"] < 6.5]
    highs = [r["acne"] for r in rows if r["sleep"] is not None and r["sleep"] >= 7]
    if len(lows) >= MIN_GROUP and len(highs) >= MIN_GROUP and abs(mean(lows) - mean(highs)) >= 1.5:
        scan_notes.append({"factor": "sleep_acne", "title": "Sleep and acne", "confidence": "low", "n": len(lows) + len(highs),
                           "direction": "worse" if mean(lows) > mean(highs) else "better",
                           "text": f"Scans after nights of under 6.5 hours of sleep showed about {_avg(lows)} acne spots versus {_avg(highs)} after 7 or more hours."})
    sweet = [r["acne"] for r in rows if r["sweet"]]
    plain = [r["acne"] for r in rows if not r["sweet"]]
    if len(sweet) >= MIN_GROUP and len(plain) >= MIN_GROUP and abs(mean(sweet) - mean(plain)) >= 1.5:
        scan_notes.append({"factor": "sweet_acne", "title": "Sugary food or dairy and acne", "confidence": "low", "n": len(sweet) + len(plain),
                           "direction": "worse" if mean(sweet) > mean(plain) else "better",
                           "text": f"Scans after days with sugary food or dairy showed about {_avg(sweet)} acne spots versus {_avg(plain)} otherwise."})
    insights.sort(key=lambda i: -i["n"])

    needed = max(0, 10 - len(with_feel))
    return {
        "daysLogged": len(days), "daysWithFeel": len(with_feel), "streak": streak,
        "ready": len(with_feel) >= 10, "insights": insights[:6], "scanInsights": scan_notes,
        "message": (f"Log how your skin felt for {needed} more day{'s' if needed != 1 else ''} to start seeing patterns." if needed
                    else "No clear pattern yet. That is normal: keep logging and check back in a couple of weeks." if not insights and not scan_notes else ""),
        "caveat": "These are associations in your own data, not proof that one thing causes another.",
    }
