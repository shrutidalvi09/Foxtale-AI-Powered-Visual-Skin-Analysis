"""Ingredient checker: paste a product's ingredient list (INCI) and see how it fits your skin and profile.

General skincare guidance only. It matches ingredient names against a hand-written table; it does not
know a product's concentrations, pH or formula quality, and it is not medical advice.
"""

import re
from typing import Any, Dict, List, Optional

# key: substrings to look for in a lower-cased ingredient token
# flags: pregnancy (avoid/ask), irritant (for sensitive skin), comedogenic (acne-prone), drying, sun (sun sensitivity), fragrance
INGREDIENTS: List[Dict[str, Any]] = [
    {"keys": ["retinol", "retinal", "retinyl", "tretinoin", "adapalene", "retinoate"], "label": "Retinoid (vitamin A)", "kind": "retinoid",
     "why": "Boosts skin renewal and collagen; can irritate and makes skin sun-sensitive.", "pregnancy": "avoid", "irritant": True, "sun": True, "class": "retinoid"},
    {"keys": ["salicylic"], "label": "Salicylic acid (BHA)", "kind": "exfoliant",
     "why": "Clears oil and dead skin inside pores; helpful for blackheads and acne, drying if overused.", "pregnancy": "ask", "irritant": True, "class": "exfoliant"},
    {"keys": ["glycolic", "mandelic"], "label": "AHA exfoliating acid", "kind": "exfoliant",
     "why": "Loosens dead skin on the surface to smooth texture and dullness; can sting and add sun sensitivity.", "pregnancy": "ask", "irritant": True, "sun": True, "class": "exfoliant"},
    {"keys": ["lactic acid"], "label": "Lactic acid (AHA)", "kind": "exfoliant",
     "why": "A gentler AHA that exfoliates and hydrates; can still add sun sensitivity.", "pregnancy": "ask", "irritant": True, "sun": True, "class": "exfoliant"},
    {"keys": ["ascorbic acid", "ascorbyl glucoside"], "label": "Vitamin C", "kind": "antioxidant",
     "why": "Antioxidant that helps brighten and even tone; pure L-ascorbic acid can sting.", "irritant": True, "class": "vitc"},
    {"keys": ["ethyl ascorbic", "ascorbyl palmitate", "sodium ascorbyl", "magnesium ascorbyl", "tetrahexyldecyl ascorbate"], "label": "Vitamin C derivative", "kind": "antioxidant",
     "why": "A gentler, more stable form of vitamin C for brightening."},
    {"keys": ["niacinamide"], "label": "Niacinamide", "kind": "helpful",
     "why": "Helps oil balance, pore look, marks and the skin barrier; well tolerated by most skin."},
    {"keys": ["azelaic"], "label": "Azelaic acid", "kind": "helpful",
     "why": "Calms redness and fades marks; may tingle at first."},
    {"keys": ["benzoyl peroxide"], "label": "Benzoyl peroxide", "kind": "acne",
     "why": "Kills acne bacteria; drying, irritating and bleaches fabric.", "irritant": True, "drying": True},
    {"keys": ["hyaluronic", "hyaluronate"], "label": "Hyaluronic acid", "kind": "helpful", "why": "Draws water into the skin for hydration."},
    {"keys": ["ceramide"], "label": "Ceramides", "kind": "helpful", "why": "Support the skin barrier and lock in moisture."},
    {"keys": ["panthenol", "allantoin", "centella", "madecassoside", "bisabolol", "green tea", "camellia sinensis"], "label": "Soothing ingredient", "kind": "helpful",
     "why": "Calms and comforts irritated or reactive skin."},
    {"keys": ["glycerin", "squalane", "betaine"], "label": "Hydrating ingredient", "kind": "helpful", "why": "Adds and holds moisture."},
    {"keys": ["fragrance", "parfum", "perfume"], "label": "Fragrance", "kind": "sensitizer", "why": "A common cause of allergic reactions and stinging on sensitive skin.", "irritant": True, "fragrance": True},
    {"keys": ["limonene", "linalool", "citral", "geraniol", "eugenol", "citronellol", "coumarin", "lavender", "peppermint", "menthol",
              "tea tree", "melaleuca", "eucalyptus", "citrus", "orange peel", "lemon", "bergamot", "rose oil", "ylang", "cinnamal"],
     "label": "Essential oil or fragrance allergen", "kind": "sensitizer", "why": "Natural does not mean gentle: these are frequent skin sensitizers.", "irritant": True, "fragrance": True},
    {"keys": ["alcohol denat", "sd alcohol", "ethanol", "isopropyl alcohol", "methanol"], "label": "Drying alcohol", "kind": "drying",
     "why": "Can dry out and irritate the skin, especially if it is dry or reactive.", "irritant": True, "drying": True},
    {"keys": ["sodium lauryl sulfate", "sodium laureth sulfate", "ammonium lauryl sulfate", "sulfate"], "label": "Sulfate cleanser", "kind": "drying",
     "why": "Strong cleansing agents that can strip oils and tighten dry or sensitive skin.", "drying": True},
    {"keys": ["cocos nucifera", "coconut oil", "isopropyl myristate", "isopropyl palmitate", "myristyl myristate", "theobroma cacao", "cocoa butter",
              "lanolin", "wheat germ", "acetylated lanolin", "decyl oleate", "octyl stearate"],
     "label": "Pore-clogging ingredient", "kind": "comedogenic", "why": "Heavier oils and esters that can clog pores in acne-prone skin.", "comedogenic": True},
    {"keys": ["avobenzone", "octinoxate", "octocrylene", "homosalate", "zinc oxide", "titanium dioxide", "tinosorb", "uvinul", "ethylhexyl triazone"],
     "label": "Sunscreen filter", "kind": "sun_protection", "why": "Protects skin from UV. Look for a broad-spectrum SPF 30 or higher."},
    {"keys": ["oxybenzone", "benzophenone-3"], "label": "Oxybenzone", "kind": "sensitizer",
     "why": "A chemical sunscreen filter some people avoid in pregnancy or when skin is sensitive.", "pregnancy": "ask", "irritant": True},
]

SEVERITY_RANK = {"avoid": 0, "caution": 1, "info": 2, "good": 3}


def _tokens(text: str) -> List[str]:
    parts = re.split(r"[,\n;•·]+", text or "")
    out = []
    for p in parts:
        t = re.sub(r"\s+", " ", p.strip().lower())
        t = t.strip(" .:-")
        if len(t) >= 2:
            out.append(t)
    return out[:200]


def check(text: str, profile: Optional[dict], latest_analysis: Optional[dict], owned_classes: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    profile = profile or {}
    tokens = _tokens(text)
    if len(tokens) < 3:
        return {"ok": False, "message": "Paste the full ingredient list (at least a few ingredients, separated by commas)."}

    matched: List[Dict[str, Any]] = []
    unknown = 0
    for tok in tokens:
        hit = next((e for e in INGREDIENTS if any(k in tok for k in e["keys"])), None)
        if hit:
            matched.append({"token": tok, "entry": hit})
        else:
            unknown += 1

    acne_prone = "acne" in (profile.get("goals") or [])
    if latest_analysis:
        acne_prone = acne_prone or latest_analysis.get("acne_like_spots", {}).get("level") in ("moderate", "noticeable")
        dry = latest_analysis.get("dryness_indicators", {}).get("level") in ("moderate", "noticeable")
    else:
        dry = False
    sensitive = bool(profile.get("sensitive_skin"))
    pregnant = bool(profile.get("pregnant"))
    allergy_tokens = [a.strip().lower() for a in re.split(r"[,;/\n]+", str(profile.get("allergies", ""))) if len(a.strip()) >= 3]

    findings: List[Dict[str, Any]] = []
    positives: List[str] = []
    seen_labels = set()

    def add(sev: str, ingredient: str, label: str, why: str) -> None:
        key = (sev, ingredient, label)
        if key in seen_labels:
            return
        seen_labels.add(key)
        findings.append({"severity": sev, "ingredient": ingredient, "label": label, "why": why})

    for tok in tokens:  # allergies match any ingredient, even ones not in the table
        hit = next((a for a in allergy_tokens if a in tok), None)
        if hit:
            add("avoid", tok, "Matches your allergy list", f"You listed \"{hit}\" as an allergy or ingredient to avoid.")

    for m in matched:
        e, tok = m["entry"], m["token"]
        if e["kind"] == "helpful":
            if e["label"] not in positives:
                positives.append(f"{e['label']}: {e['why']}")
            continue
        if pregnant and e.get("pregnancy") == "avoid":
            add("avoid", tok, e["label"], f"{e['why']} Retinoids are generally avoided in pregnancy and breastfeeding; please ask your doctor.")
        elif pregnant and e.get("pregnancy") == "ask":
            add("caution", tok, e["label"], f"{e['why']} Ask your doctor before using it while pregnant or breastfeeding.")
        if sensitive and e.get("irritant"):
            add("caution", tok, e["label"], f"{e['why']} You told us your skin is sensitive, so patch-test carefully or skip it.")
        elif e.get("kind") in ("sensitizer",) and not sensitive:
            add("info", tok, e["label"], e["why"])
        if acne_prone and e.get("comedogenic"):
            add("caution", tok, e["label"], f"{e['why']} Your scan or goals point to acne-prone skin.")
        if dry and e.get("drying"):
            add("caution", tok, e["label"], f"{e['why']} Your scan shows dry-looking areas.")
        if e.get("sun"):
            add("info", tok, e["label"], f"{e['why']} Use sunscreen every morning.")
        if e["kind"] in ("retinoid", "exfoliant", "antioxidant") and e["label"] not in [f["label"] for f in findings]:
            add("info", tok, e["label"], e["why"])

    # conflicts with what the user already uses
    conflicts: List[Dict[str, str]] = []
    pasted_classes = {e["entry"].get("class") for e in matched if e["entry"].get("class")}
    owned_classes = owned_classes or {}
    pair_msgs = {
        ("retinoid", "exfoliant"): "Retinol and exfoliating acids irritate when stacked. Use them on different nights.",
        ("exfoliant", "retinoid"): "Retinol and exfoliating acids irritate when stacked. Use them on different nights.",
        ("retinoid", "vitc"): "Keep vitamin C for the morning and retinol for the night.",
        ("vitc", "retinoid"): "Keep vitamin C for the morning and retinol for the night.",
        ("exfoliant", "vitc"): "Low-pH vitamin C and exfoliating acids can irritate together. Use them at different times of day.",
        ("vitc", "exfoliant"): "Low-pH vitamin C and exfoliating acids can irritate together. Use them at different times of day.",
        ("exfoliant", "exfoliant"): "Two exfoliating products can over-exfoliate. Pick one and use it a few nights a week.",
    }
    for cls in pasted_classes:
        for other_cls, names in owned_classes.items():
            msg = pair_msgs.get((cls, other_cls))
            if msg and names:
                conflicts.append({"with": ", ".join(names), "detail": msg})

    worst = min((SEVERITY_RANK[f["severity"]] for f in findings), default=3)
    if any(f["severity"] == "avoid" for f in findings):
        verdict, summary = "avoid", "Not a good fit for you: it contains something you asked to avoid or that is unsafe for your situation."
    elif any(f["severity"] == "caution" for f in findings) or conflicts:
        verdict, summary = "caution", "Usable with care: patch-test it and check the points below."
    else:
        verdict, summary = "good", "No problems found for your skin and profile from this ingredient list."
    del worst
    best: Dict[str, Dict[str, Any]] = {}
    for f in findings:  # one line per ingredient: keep its most serious point
        cur = best.get(f["label"] + f["ingredient"])
        if cur is None or SEVERITY_RANK[f["severity"]] < SEVERITY_RANK[cur["severity"]]:
            best[f["label"] + f["ingredient"]] = f
    findings = sorted(best.values(), key=lambda f: SEVERITY_RANK[f["severity"]])
    return {
        "ok": True, "verdict": verdict, "summary": summary, "findings": findings, "positives": positives[:6],
        "conflicts": conflicts, "counts": {"ingredients": len(tokens), "recognised": len(matched), "unrecognised": unknown},
        "note": "Based on ingredient names only. Concentrations, pH and formula quality change how a product behaves, so patch-test and read the label.",
        "usedProfile": bool(profile.get("onboarded")),
    }
