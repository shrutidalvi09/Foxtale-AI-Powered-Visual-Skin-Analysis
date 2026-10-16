"""The `SkinMeasurer` interface: whatever produces the deterministic, numeric measurement
JSON that grounds the Skin Analyst. The visible-skin score, region scores and the 14-row
"Detailed Findings" table are *already* computed by the classical CV engine
(`engine.skin_analysis.analyze_face` + `engine.features.compute_features`) before this
module ever runs -- so `HeuristicMeasurer` below does not re-measure anything, it just
projects that already-computed `SkinAnalysis` into the compact JSON shape the LLM prompt
expects. That measurement layer stays the source of truth for the score (see
core/skin_ai_analyst.py: the visible-skin score is never touched by AI output).

Swapping in a trained model later (a classifier/detector instead of the hand-tuned CV
heuristics) means writing a new class with the same `measure()` signature -- see
`TrainedModelMeasurer` below for the stub and `README.md -> "Training a custom SkinMeasurer"`
for the data format this expects.
"""

from typing import Any, Dict, Optional, Protocol

from engine.quality import QualityResult
from engine.schemas import SkinAnalysis


class SkinMeasurer(Protocol):
    """Anything that can turn an already-analysed photo into the measurement JSON the Skin
    Analyst prompt is grounded on. `analysis`/`quality` are what `engine.skin_analysis` and
    `engine.quality` already computed for this scan -- a measurer does not need the raw image
    unless it wants to look at it itself (a future trained-model measurer might)."""

    name: str

    def measure(self, analysis: SkinAnalysis, quality: Optional[QualityResult]) -> Dict[str, Any]:
        ...


class HeuristicMeasurer:
    """Wraps the existing classical-CV engine. This is the default (and only working)
    measurer today -- it is "swappable" in the sense that `core.skin_ai_analyst` only ever
    calls `.measure()`, never engine internals directly."""

    name = "heuristic_cv_v2"

    def measure(self, analysis: SkinAnalysis, quality: Optional[QualityResult]) -> Dict[str, Any]:
        data = analysis.to_dict()
        measurements: Dict[str, Any] = {
            "overall_visible_skin_score": data.get("overall_score"),
            "categories": {
                k: data[k] for k in
                ("acne_like_spots", "redness", "texture", "dryness_indicators", "oiliness", "tone_evenness")
                if k in data
            },
            "region_scores": data.get("region_scores", {}),
            "skin_tone": data.get("skin_tone"),
            "raw_metrics": data.get("metrics", {}),
            "detailed_findings": data.get("detail", {}),
        }
        if quality is not None:
            measurements["photo_quality"] = quality.to_dict()
        return measurements


class TrainedModelMeasurer:
    """Stub for a future trained model (e.g. an acne/pigmentation detector or a skin-type
    classifier) that would replace or augment the hand-tuned heuristics. Not implemented --
    see README.md for the expected dataset format, labels and evaluation metrics, and
    `scripts/eval_skin_ai.py` for the harness that would score it against labelled samples.
    """

    name = "trained_model_stub"

    def measure(self, analysis: SkinAnalysis, quality: Optional[QualityResult]) -> Dict[str, Any]:
        raise NotImplementedError(
            "TrainedModelMeasurer is a placeholder. Implement `.measure()` to call your trained "
            "model and return the same measurement-JSON shape as HeuristicMeasurer, then set "
            "AI_MEASURER=trained in the environment (see core/skin_ai_config.py) to use it."
        )


def default_measurer() -> SkinMeasurer:
    return HeuristicMeasurer()
