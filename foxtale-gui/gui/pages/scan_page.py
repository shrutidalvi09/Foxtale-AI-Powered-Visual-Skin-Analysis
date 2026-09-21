"""Face Scanner page: camera capture -> optional calibration -> analysis."""

from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from engine.calibration import compute_calibration
from engine.face_detection import detect_face
from engine.image_processing import forehead_calibration_patch
from engine.quality import QualityResult
from engine.schemas import AnalyzeResult
from gui.core import storage
from gui.core.analysis_worker import AnalysisWorker
from gui.widgets.camera_view import CameraView
from gui.widgets.disclaimer import DisclaimerBanner
from gui.widgets.scan_progress import ScanProgress

ERROR_COPY = {
    "no_face": ("No face detected", "Please position your face inside the scanning area."),
    "multiple_faces": ("Multiple faces detected", "Please make sure only one person is visible."),
    "poor_lighting": ("Lighting is insufficient", "Move to a well-lit area and try again."),
    "too_close": ("Face too close", "Move slightly farther away."),
    "too_far": ("Face too far", "Move closer to the camera."),
}


class ScanPage(QWidget):
    def __init__(
        self,
        get_settings: Callable[[], dict],
        on_scan_complete: Callable[[AnalyzeResult, np.ndarray, Optional[QualityResult]], None],
        show_toast: Callable[[str], None],
        parent=None,
    ):
        super().__init__(parent)
        self._get_settings = get_settings
        self._on_scan_complete = on_scan_complete
        self._show_toast = show_toast
        self._worker: Optional[AnalysisWorker] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(14)

        heading = QLabel("Scan your face")
        heading.setObjectName("Heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        sub = QLabel("Position your face inside the frame, then capture.")
        sub.setObjectName("SubHeading")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        self.error_banner = QLabel("")
        self.error_banner.setWordWrap(True)
        self.error_banner.setStyleSheet(
            "background-color: #fdecec; color: #b3261e; border: 1px solid #f5c2c0; "
            "border-radius: 10px; padding: 10px;"
        )
        self.error_banner.hide()
        layout.addWidget(self.error_banner)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # --- camera page ---
        camera_page = QWidget()
        camera_layout = QVBoxLayout(camera_page)
        self.camera = CameraView(get_settings=self._get_settings)
        self.camera.captured.connect(self._on_captured)
        self.camera.error.connect(self._on_camera_error)
        camera_layout.addWidget(self.camera)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.calibrate_btn = QPushButton("Calibrate skin tone from this photo")
        self.calibrate_btn.setObjectName("Secondary")
        self.calibrate_btn.clicked.connect(self._calibrate)
        self.calibrate_btn.setVisible(False)
        self.start_scan_btn = QPushButton("Start Scan")
        self.start_scan_btn.setObjectName("Primary")
        self.start_scan_btn.clicked.connect(self._start_scan)
        self.start_scan_btn.setVisible(False)
        action_row.addWidget(self.calibrate_btn)
        action_row.addWidget(self.start_scan_btn)
        action_row.addStretch()
        camera_layout.addLayout(action_row)

        self.stack.addWidget(camera_page)

        # --- scanning/progress page ---
        progress_page = QWidget()
        progress_layout = QVBoxLayout(progress_page)
        progress_layout.addStretch()
        self.progress = ScanProgress()
        progress_layout.addWidget(self.progress)
        progress_layout.addStretch()
        self.stack.addWidget(progress_page)

        layout.addWidget(DisclaimerBanner())

    def _on_captured(self, frame: np.ndarray) -> None:
        self.error_banner.hide()
        self.calibrate_btn.setVisible(True)
        self.start_scan_btn.setVisible(True)

    def _on_camera_error(self, message: str) -> None:
        self.error_banner.setText(message)
        self.error_banner.show()

    def _calibrate(self) -> None:
        frame = self.camera.current_frame()
        if frame is None:
            return
        face_result = detect_face(frame)
        if not face_result.ok:
            self._show_toast("Couldn't calibrate: no clear face found in this photo.")
            return
        patch = forehead_calibration_patch(frame, face_result.box)
        profile = compute_calibration(patch)
        if profile is None:
            self._show_toast("Couldn't calibrate from this photo — try again.")
            return
        storage.save_calibration(profile)
        self._show_toast("Skin-tone calibration saved for future scans.")

    def _start_scan(self) -> None:
        frame = self.camera.current_frame()
        if frame is None:
            return
        self.error_banner.hide()
        self.stack.setCurrentIndex(1)
        self.progress.start()

        settings = self._get_settings()
        calibration = storage.load_calibration()

        self._worker = AnalysisWorker(
            frame, calibration=calibration, min_confidence=settings.get("min_confidence", 0.0)
        )
        self._worker.finished_ok.connect(self._on_analysis_ok)
        self._worker.finished_error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_ok(self, result: AnalyzeResult, image: np.ndarray, quality: Optional[QualityResult]) -> None:
        self.progress.finish()
        self._on_scan_complete(result, image, quality)

    def _on_analysis_error(self, result: AnalyzeResult) -> None:
        self.progress.finish()
        title, body = ERROR_COPY.get(result.error, ("Could not analyze image", result.message or "Please try again."))
        self.error_banner.setText(f"{title}. {body}")
        self.error_banner.show()
        self.stack.setCurrentIndex(0)

    def reset(self) -> None:
        self.camera.retake() if self.camera.current_frame() is not None else None
        self.calibrate_btn.setVisible(False)
        self.start_scan_btn.setVisible(False)
        self.error_banner.hide()
        self.stack.setCurrentIndex(0)

    def shutdown(self) -> None:
        self.camera.shutdown()
