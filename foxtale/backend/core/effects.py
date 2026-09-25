"""Is a product working? Compares your scans before you started it with your scans after, on the
measurements that product is meant to help.

This shows a pattern in your own photos, not proof: lighting, season, other products and how
you sit in front of the camera all move these numbers too.
"""

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import skincare_advisor as adv
from core import storage

MIN_DAYS = 14  # a product needs about two weeks before a change means anything
BASELINE_SCANS = 2
RECENT_SCANS = 2
RELATIVE_CHANGE = 0.15  # a measurement must move at least this much (of its starting value) to count


def _get(d: dict, *path: str) -> Optional[float]:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return float(cur) if isinstance(cur, (int, float)) else None


def _pct(v: Optional[float]) -> Optional[float]:
    return None if v is None else 100.0 * v


# target -> (label, unit, lower_is_better, min absolute change, getter(analysis dict))
METRICS: Dict[str, Tuple[str, str, bool, float, Callable[[dict], Optional[float]]]] = {
    "acne_like_spots": ("Acne spots", "", True, 1.0, lambda a: _get(a, "detail", "acne", "total") if _get(a, "detail", "acne", "total") is not None else _get(a, "acne_like_spots", "count")),
    "blackheads": ("Blackheads and whiteheads", "", True, 1.0, lambda a: (_get(a, "detail", "acne", "blackheads") or 0) + (_get(a, "detail", "acne", "whiteheads") or 0) if a.get("detail") else None),
    "dark_spots": ("Dark spots", "% of skin", True, 0.2, lambda a: _get(a, "detail", "dark_spots", "coverage_pct")),
    "pores": ("Pore visibility", "/100", True, 4.0, lambda a: _pct(_get(a, "detail", "pores", "score"))),
    "redness": ("Redness", "% of skin", True, 3.0, lambda a: _get(a, "metrics", "redness_local_pct")),
    "tone_evenness": ("Tone uniformity", "%", False, 3.0, lambda a: _get(a, "detail", "uniformity", "pct")),
    "texture": ("Roughness", "index", True, 0.2, lambda a: _get(a, "metrics", "texture_std")),
    "oiliness": ("Shine", "% of skin", True, 1.0, lambda a: _get(a, "metrics", "shine_pct")),
    "dryness_indicators": ("Dull or dry areas", "% of skin", True, 4.0, lambda a: _get(a, "metrics", "dryness_low_chroma_pct")),
    "fine_lines": ("Fine lines", "/100", True, 5.0, lambda a: _pct(_get(a, "detail", "fine_lines", "score"))),
    "under_eye": ("Under-eye darkness", "/100", True, 5.0, lambda a: _pct(_get(a, "detail", "under_eye", "score"))),
    "acne_scars": ("Marks and scarring", "/100", True, 5.0, lambda a: _pct(_get(a, "detail", "scars", "score"))),
}


def _mean(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _measure(scans: List[dict], getter: Callable[[dict], Optional[float]]) -> List[float]:
    out = []
    for s in scans:
        v = getter(s["analysis"])
        if v is not None:
            out.append(v)
    return out


def _verdict(target: str, before: float, after: float) -> Tuple[str, float]:
    _, _, lower, min_abs, _ = METRICS[target]
    delta = after - before
    better = delta < 0 if lower else delta > 0
    rel = abs(delta) / max(abs(before), min_abs * 2)
    if abs(delta) >= min_abs and rel >= RELATIVE_CHANGE:
        return ("improved" if better else "worse"), round(delta, 2)
    return "steady", round(delta, 2)


def compute(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    now = now or datetime.now()
    usage = storage.usage_all()  # {product_id: iso start}
    if not usage:
        return []
    scans = sorted(storage.list_scans(), key=lambda s: s["timestamp"])  # oldest first
    catalog = {p.id: p for p in adv.load_catalog()}
    starts = sorted(datetime.fromisoformat(v) for v in usage.values())
    results: List[Dict[str, Any]] = []
    for pid, started_iso in sorted(usage.items(), key=lambda kv: kv[1]):
        prod = catalog.get(pid)
        if not prod:
            continue
        started = datetime.fromisoformat(started_iso)
        days = (now - started).days
        before_scans = [s for s in scans if datetime.fromisoformat(s["timestamp"]) <= started + timedelta(days=1)][-BASELINE_SCANS:]
        after_scans = [s for s in scans if datetime.fromisoformat(s["timestamp"]) >= started + timedelta(days=MIN_DAYS)][-RECENT_SCANS:]
        together = [p for p, v in usage.items() if p != pid and abs((datetime.fromisoformat(v) - started).days) <= 7]
        item: Dict[str, Any] = {
            "productId": pid, "name": prod.name, "image": f"/product-images/{pid}.jpg", "startedAt": started_iso[:10], "days": days,
            "startedWith": [catalog[p].name for p in together if p in catalog], "metrics": [], "status": "collecting", "message": "",
            "before": len(before_scans), "after": len(after_scans),
        }
        if days < MIN_DAYS:
            item["message"] = f"Give it time: {MIN_DAYS - days} more day{'s' if MIN_DAYS - days != 1 else ''} before a change means anything."
        elif not before_scans:
            item["message"] = "No scan from before you started this product, so there is nothing to compare with. Scan now and keep scanning every week or two."
        elif not after_scans:
            item["message"] = f"Scan again (it has been {days} days) to see how your skin has changed."
        else:
            for target in prod.targets:
                if target not in METRICS:
                    continue
                label, unit, _lower, _min, getter = METRICS[target]
                b, a = _mean(_measure(before_scans, getter)), _mean(_measure(after_scans, getter))
                if b is None or a is None or (b == 0 and a == 0):
                    continue  # nothing was there before or after: no signal either way
                verdict, delta = _verdict(target, b, a)
                item["metrics"].append({"target": target, "label": label, "unit": unit, "before": round(b, 2), "after": round(a, 2),
                                        "delta": delta, "verdict": verdict})
            verdicts = [m["verdict"] for m in item["metrics"]]
            if not verdicts:
                item["status"], item["message"] = "collecting", "Your older scans do not have the measurements this product targets. Scan again to build the comparison."
            elif "improved" in verdicts and "worse" not in verdicts:
                item["status"], item["message"] = "improving", "Your skin looks better on what this product targets."
            elif "improved" in verdicts and "worse" in verdicts:
                item["status"], item["message"] = "mixed", "Some measurements improved and some did not."
            elif "worse" in verdicts:
                item["status"], item["message"] = "worse", "What this product targets looks worse. Check for irritation, and consider a break or a gentler option."
            else:
                item["status"], item["message"] = "steady", "No clear change yet. Some products take 6 to 12 weeks."
        results.append(item)
    del starts
    return results
