"""QThread that runs face detection + region split + skin analysis off the UI thread."""

import time
from typing import Optional

import numpy as np
from PySide6.QtCore import QThread, Signal

from engine.calibration import CalibrationProfile
from engine.face_detection import detect_face
from engine.image_processing import normalize, split_regions
from engine.image_utils import resize_max_dim
from engine.quality import compute_quality
from engine.schemas import AnalyzeResult
from engine.skin_analysis import analyze_face
from gui.core import perf


class AnalysisWorker(QThread):
    finished_ok = Signal(object, np.ndarray, object)  # AnalyzeResult, resized source image, QualityResult
    finished_error = Signal(object)  # AnalyzeResult with face_detected=False

    def __init__(
        self,
        image_bgr: np.ndarray,
        calibration: Optional[CalibrationProfile] = None,
        min_confidence: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self.image_bgr = image_bgr
        self.calibration = calibration
        self.min_confidence = min_confidence

    def run(self) -> None:
        started = time.perf_counter()
        image = resize_max_dim(self.image_bgr, max_dim=900)

        face_result = detect_face(image)
        if not face_result.ok:
            self.finished_error.emit(AnalyzeResult(
                face_detected=False, error=face_result.error, message=face_result.message,
            ))
            return

        normalized = normalize(image)
        regions = split_regions(normalized, face_result.box)
        analysis, observations = analyze_face(regions, self.calibration, self.min_confidence)
        quality = compute_quality(image, face_result.box)

        perf.record_analysis_ms((time.perf_counter() - started) * 1000)

        self.finished_ok.emit(
            AnalyzeResult(face_detected=True, analysis=analysis, regions=observations),
            image,
            quality,
        )
