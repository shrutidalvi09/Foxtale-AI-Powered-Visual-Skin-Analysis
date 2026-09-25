"""Routine conflict checker: warns when products in the same routine step on each other.

The rules are general, widely-taught skincare guidance (not a substitute for a dermatologist):
retinoids and exfoliating acids irritate when stacked, low-pH vitamin C is best kept apart from
both, and daytime actives need sunscreen.
"""

from typing import Dict, Iterable, List, Set

from core.skincare_advisor import Product

SEVERITY_ORDER = {"avoid": 0, "caution": 1, "info": 2}


def classes_of(product: Product) -> Set[str]:
    """What kind of active a product carries: retinoid, exfoliant (leave-on acid) or vitc (L-ascorbic acid)."""
    text = (product.name + " " + " ".join(product.key_ingredients)).lower()
    out: Set[str] = set()
    if "retinol" in text or "retinal" in text:
        out.add("retinoid")
    if product.active and any(k in text for k in ("glycolic", "lactic", "salicylic", "mandelic", "aha", "bha")):
        out.add("exfoliant")
    if "ascorbic" in text and "ethyl" not in text:  # ethyl ascorbic acid (eye cream) is the gentle form
        out.add("vitc")
    return out


def _slots(product: Product) -> List[str]:
    return [s for s in ("AM", "PM") if s in product.when]


def check(products: Iterable[Product]) -> List[Dict[str, object]]:
    """Issues in a set of products used together. Each issue: severity (avoid|caution|info), title, detail, fix, products."""
    prods = list(products)
    issues: List[Dict[str, object]] = []
    seen: Set[str] = set()

    def add(sev: str, title: str, detail: str, fix: str, names: List[str]) -> None:
        key = title + "|" + ",".join(sorted(names))
        if key in seen:
            return
        seen.add(key)
        issues.append({"severity": sev, "title": title, "detail": detail, "fix": fix, "products": names})

    for slot in ("AM", "PM"):
        inslot = [p for p in prods if slot in _slots(p)]
        by_class: Dict[str, List[Product]] = {"retinoid": [], "exfoliant": [], "vitc": []}
        for p in inslot:
            for c in classes_of(p):
                by_class[c].append(p)
        when = "morning" if slot == "AM" else "evening"

        if by_class["retinoid"] and by_class["exfoliant"]:
            names = [p.name for p in by_class["retinoid"] + by_class["exfoliant"]]
            add("avoid", "Retinol and an exfoliating acid in the same routine",
                f"Using both in the {when} is a common cause of redness, stinging and a damaged skin barrier.",
                "Use them on different nights, for example retinol on some nights and the acid on others, with a rest night between.", names)
        if by_class["retinoid"] and by_class["vitc"]:
            names = [p.name for p in by_class["retinoid"] + by_class["vitc"]]
            add("caution", "Retinol and vitamin C at the same time",
                "Both can sting, and they work best in different parts of the day.",
                "Use vitamin C in the morning and retinol at night.", names)
        if by_class["exfoliant"] and by_class["vitc"]:
            names = [p.name for p in by_class["exfoliant"] + by_class["vitc"]]
            add("caution", "An exfoliating acid and vitamin C in the same routine",
                "Layering low-pH actives can irritate sensitive skin.",
                "Use vitamin C in the morning and the exfoliating acid at night.", names)
        if len(by_class["exfoliant"]) >= 2:
            add("caution", "Two exfoliating products in one routine",
                "Stacking exfoliants can over-exfoliate: tightness, shine, burning or new breakouts.",
                "Pick one exfoliating product and use it two or three nights a week.", [p.name for p in by_class["exfoliant"]])

    am_actives = [p for p in prods if "AM" in _slots(p) and classes_of(p)]
    has_spf = any(p.step == "protect" and "AM" in _slots(p) for p in prods)
    if (am_actives or any(classes_of(p) for p in prods)) and not has_spf:
        add("info", "Add a sunscreen",
            "Retinol, exfoliating acids and vitamin C make skin more sensitive to sun, and sun also darkens marks.",
            "Finish every morning with a broad-spectrum SPF 50.", [p.name for p in prods if classes_of(p)])

    strong = [p for p in prods if p.active]
    if len(strong) >= 2 and not any(i["severity"] in ("avoid", "caution") for i in issues):
        add("info", "Several strong actives in one routine",
            "Even when they do not clash, more than one strong active raises the risk of irritation.",
            "Introduce one at a time and wait two to three weeks before adding the next.", [p.name for p in strong])

    issues.sort(key=lambda i: SEVERITY_ORDER[str(i["severity"])])
    return issues
