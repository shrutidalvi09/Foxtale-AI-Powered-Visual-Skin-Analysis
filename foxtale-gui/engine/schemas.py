"""Plain dataclasses describing analysis results -- shared by the camera
pipeline, storage layer, and GUI widgets. Deliberately dependency-free
(no pydantic/FastAPI) since this is a desktop app, not a web API.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional

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

    def to_dict(self) -> dict:
        return {
            "acne_like_spots": self.acne_like_spots.to_dict(),
            "redness": self.redness.to_dict(),
            "texture": self.texture.to_dict(),
            "dryness_indicators": self.dryness_indicators.to_dict(),
        }

    @staticmethod
    def from_dict(d: dict) -> "SkinAnalysis":
        return SkinAnalysis(
            acne_like_spots=CategoryResult(**d["acne_like_spots"]),
            redness=CategoryResult(**d["redness"]),
            texture=CategoryResult(**d["texture"]),
            dryness_indicators=CategoryResult(**d["dryness_indicators"]),
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
