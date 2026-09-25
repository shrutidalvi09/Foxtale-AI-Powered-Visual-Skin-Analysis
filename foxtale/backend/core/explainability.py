"""Plain-language explanations of how each category's rule-based heuristic
works, and the fixed level thresholds it's scored against -- so "moderate"
is never just a label handed down, it's traceable to how the number was
made and which of this scan's regions triggered it.
"""

METHODOLOGY = {
    "Acne-like spots": (
        "Finds small, compact patches that are clearly redder than the surrounding "
        "skin (after lighting is evened out) and scores how many there are and how "
        "much skin they cover."
    ),
    "Redness": (
        "Measures how much of the skin is redder than your own average skin tone, "
        "and how far the overall tone sits above a typical healthy range. Adjusted "
        "by your skin-tone calibration if you've set one."
    ),
    "Texture": (
        "Measures pore-scale brightness variation on skin pixels only, ignoring "
        "camera noise and spots -- smoother-looking regions score lower."
    ),
    "Dryness indicators": (
        "Combines fine-scale roughness, dull low-colour areas and patchy brightness "
        "across each region."
    ),
    "Oiliness": (
        "Measures the share of skin pixels that are noticeably brighter and less "
        "colourful than their surroundings -- the look of light reflecting off oil."
    ),
    "Tone evenness": (
        "Measures how much brightness and colour vary across the skin at a broad "
        "scale, after removing lighting gradients."
    ),
}

LEVEL_THRESHOLDS = "Minimal (<15%) · Mild (15–35%) · Moderate (35–60%) · Noticeable (60%+)"


def flagged_regions_summary(category: str, regions: list) -> str:
    """`regions` is a scan's full RegionObservation list; this filters to
    the given category and renders a short "Flagged in: ..." line."""
    matches = [r for r in regions if r.category == category]
    if not matches:
        return "Not flagged in any specific region this scan."
    bits = [f"{r.region.title()} ({int(r.confidence * 100)}%)" for r in matches]
    return "Flagged in: " + ", ".join(bits)
