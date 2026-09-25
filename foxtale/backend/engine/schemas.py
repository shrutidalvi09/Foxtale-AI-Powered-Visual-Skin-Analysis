"""Plain dataclasses describing analysis results -- shared by the camera
pipeline, storage layer, and GUI widgets. Deliberately dependency-free
(no pydantic/FastAPI) since this is a desktop app, not a web API.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

DISCLAIMER = (
    "This analysis is based only on visible features in the captured image and is "
    "not a medical diagnosis. For persistent, painful, spreading, or concerning "
    "skin changes, consult a qualified dermatologist."
)

LEVEL_SCORE = {"minimal": 0, "mild": 1, "moderate": 2, "noticeable": 3}


@dataclass
class CategoryResult:
    level: str
    confidence: float
    count: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkinAnalysis:
    acne_like_spots: CategoryResult
    redness: CategoryResult
    texture: CategoryResult
    dryness_indicators: CategoryResult
    # Added by the v2 engine. Optional so scans saved by older versions
    # (which only have the four categories above) still load.
    oiliness: Optional[CategoryResult] = None
    tone_evenness: Optional[CategoryResult] = None
    overall_score: Optional[int] = None  # 0-100, higher = clearer-looking skin
    region_scores: Dict[str, dict] = field(default_factory=dict)  # per-region score + raw metrics
    metrics: Dict[str, float] = field(default_factory=dict)  # face-wide raw measurements
    skin_tone: Optional[dict] = None  # {label, ita, undertone, hue, swatch}
    detail: Dict[str, dict] = field(default_factory=dict)  # detailed findings from engine.features
    engine_version: int = 1

    def to_dict(self) -> dict:
        d = {
            "acne_like_spots": self.acne_like_spots.to_dict(),
            "redness": self.redness.to_dict(),
            "texture": self.texture.to_dict(),
            "dryness_indicators": self.dryness_indicators.to_dict(),
        }
        if self.oiliness:
            d["oiliness"] = self.oiliness.to_dict()
        if self.tone_evenness:
            d["tone_evenness"] = self.tone_evenness.to_dict()
        if self.overall_score is not None:
            d["overall_score"] = self.overall_score
        if self.region_scores:
            d["region_scores"] = self.region_scores
        if self.metrics:
            d["metrics"] = self.metrics
        if self.skin_tone:
            d["skin_tone"] = self.skin_tone
        if self.detail:
            d["detail"] = self.detail
        d["engine_version"] = self.engine_version
        return d

    @staticmethod
    def from_dict(d: dict) -> "SkinAnalysis":
        def opt(key):
            return CategoryResult(**d[key]) if d.get(key) else None

        return SkinAnalysis(
            acne_like_spots=CategoryResult(**d["acne_like_spots"]),
            redness=CategoryResult(**d["redness"]),
            texture=CategoryResult(**d["texture"]),
            dryness_indicators=CategoryResult(**d["dryness_indicators"]),
            oiliness=opt("oiliness"),
            tone_evenness=opt("tone_evenness"),
            overall_score=d.get("overall_score"),
            region_scores=d.get("region_scores") or {},
            metrics=d.get("metrics") or {},
            skin_tone=d.get("skin_tone"),
            detail=d.get("detail") or {},
            engine_version=d.get("engine_version", 1),
        )


@dataclass
class RegionObservation:
    region: str
    category: str
    observation: str
    confidence: float
    x: float
    y: float

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "RegionObservation":
        return RegionObservation(**d)


@dataclass
class AnalyzeResult:
    face_detected: bool
    analysis: Optional[SkinAnalysis] = None
    regions: List[RegionObservation] = field(default_factory=list)
    error: Optional[str] = None
    message: Optional[str] = None
    disclaimer: str = DISCLAIMER
