"""Plain-language explanations of how each category's rule-based heuristic
works, and the fixed level thresholds it's scored against -- so "moderate"
is never just a label handed down, it's traceable to how the number was
made and which of this scan's regions triggered it.
"""

METHODOLOGY = {
    "Acne-like spots": (
        "Counts small, high-contrast blob-like shapes within a typical blemish "
        "size range in each facial region, then scores how dense they are."
    ),
    "Redness": (
        "Measures the share of pixels in the red hue range in each region, "
        "adjusted against your skin-tone calibration if you've set one."
    ),
    "Texture": (
        "Measures local contrast variance (a roughness signal) within each "
        "region -- smoother-looking regions score lower."
    ),
    "Dryness indicators": (
        "Combines low color saturation with blotchy brightness patterns "
        "(patchiness) across each region."
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
