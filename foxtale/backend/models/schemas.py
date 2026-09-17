"""Pydantic response/request models for the Foxtale API."""

from typing import List, Optional
from pydantic import BaseModel, Field

DISCLAIMER = (
    "This analysis is based only on visible features in the captured image and is "
    "not a medical diagnosis. For persistent, painful, spreading, or concerning "
    "skin changes, consult a qualified dermatologist."
)


class CategoryResult(BaseModel):
    level: str = Field(..., description="minimal | mild | moderate | noticeable")
    confidence: float
    count: Optional[int] = None


class SkinAnalysis(BaseModel):
    acne_like_spots: CategoryResult
    redness: CategoryResult
    texture: CategoryResult
    dryness_indicators: CategoryResult


class RegionObservation(BaseModel):
    region: str
    category: str
    observation: str
    confidence: float
    x: float = Field(..., description="Normalized 0-1 x position within the image")
    y: float = Field(..., description="Normalized 0-1 y position within the image")


class AnalyzeResponse(BaseModel):
    faceDetected: bool
    analysis: Optional[SkinAnalysis] = None
    regions: List[RegionObservation] = []
    disclaimer: str = DISCLAIMER
    error: Optional[str] = None
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    faceDetected: bool = False
    error: str
    message: str
    disclaimer: str = DISCLAIMER
