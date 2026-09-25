"""Face Scanner page: camera capture -> optional calibration -> analysis."""

from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from engine.calibration import compute_calibration
from engine.face_detection import detect_face
from engine.image_processing import forehead_calibration_patch
from engine.quality import QualityResult
from engine.schemas import AnalyzeResult
from gui.assets import apply_card_shadow, apply_cta_glow, icon as make_icon, icon_pixmap
from gui.core import storage
from gui.core.analysis_worker import AnalysisWorker
from gui.theme import FOX, ORANGE_TEXT, get_current_theme
from gui.widgets.camera_view import CameraView
from gui.widgets.disclaimer import DisclaimerBanner
from gui.widgets.scan_progress import ScanProgress

ERROR_COPY = {
    "no_face": ("No face detected", "Please position your face inside the scanning area."),
    "multiple_faces": ("Multiple faces detected", "Please make sure only one person is visible."),
    "too_close": ("Face too close", "Move slightly farther away."),
    "too_far": ("Face too far", "Move closer to the camera."),
    "not_enough_skin": (
        "Not enough visible skin",
        "Face the camera and keep hair or hands off your face, then try again.",
    ),
}

BEST_SCAN_TIPS = [
    ("fa5.eye", "Look straight at the camera"),
    ("fa5s.expand", "Keep your face centered"),
    ("fa5s.sun", "Good natural lighting works best"),
    ("fa5s.glasses", "Remove glasses, hat, and heavy makeup"),
    ("fa5.smile", "Relax and keep a neutral expression"),
]

# (icon, icon color, circle bg, title, body)
NEXT_STEPS = [
    ("fa5s.camera", "#c2540b", "#fde8da", "Capture", "We capture your facial image"),
    ("fa6s.wand-magic-sparkles", "#5b3fc2", "#eae7fb", "Analyze", "AI analyzes visible skin features"),
    ("fa5s.chart-bar", "#12805c", "#e1f5ea", "Get Results", "View your skin observations"),
]


def _icon_circle(icon_name: str, fg: str, bg: str, size: int = 44, icon_size: int = 18) -> QFrame:
    circle = QFrame()
    circle.setFixedSize(size, size)
    circle.setStyleSheet(f"background-color: {bg}; border-radius: {size // 2}px; border: none;")
    inner = QVBoxLayout(circle)
    inner.setContentsMargins(0, 0, 0, 0)
    label = QLabel()
    label.setPixmap(icon_pixmap(icon_name, fg, size=icon_size))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    inner.addWidget(label)
    return circle


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    apply_card_shadow(frame, blur=20, y_offset=5, alpha=20)
    v = QVBoxLayout(frame)
    v.setContentsMargins(22, 18, 22, 18)
    v.setSpacing(0)
    heading = QLabel(title)
    heading.setObjectName("CardTitle")
    heading.setStyleSheet("font-size: 15px;")
    v.addWidget(heading)
    v.addSpacing(10)
    return frame, v


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
        self._analyze_after_capture = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        heading = QLabel("Scan your face")
        heading.setObjectName("Heading")
        title_col.addWidget(heading)
        sub = QLabel("Position your face inside the frame, then capture.")
        sub.setObjectName("SubHeading")
        title_col.addWidget(sub)
        header.addLayout(title_col)
        header.addStretch()
        header.addWidget(self._tip_pill(), alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.error_banner = QLabel("")
        self.error_banner.setObjectName("ErrorBanner")
        self.error_banner.setWordWrap(True)
        self.error_banner.hide()
        layout.addWidget(self.error_banner)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # --- camera page: camera + controls on the left, guidance on the right ---
        camera_page = QWidget()
        page_row = QHBoxLayout(camera_page)
        page_row.setContentsMargins(0, 0, 0, 0)
        page_row.setSpacing(24)

        left = QVBoxLayout()
        left.setSpacing(12)
        self.camera = CameraView(get_settings=self._get_settings)
        self.camera.captured.connect(self._on_captured)
        self.camera.error.connect(self._on_camera_error)
        left.addWidget(self.camera)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        action_row.addStretch()
        self.calibrate_btn = QPushButton("Calibrate skin tone from this photo")
        self.calibrate_btn.setObjectName("Secondary")
        self.calibrate_btn.setFixedHeight(48)
        self.calibrate_btn.clicked.connect(self._calibrate)
        self.calibrate_btn.setVisible(False)
        self.start_scan_btn = QPushButton("  Start Scan")
        self.start_scan_btn.setIcon(make_icon("fa6s.wand-magic-sparkles", "white"))
        self.start_scan_btn.setIconSize(QSize(17, 17))
        self.start_scan_btn.setObjectName("Cta")
        self.start_scan_btn.setFixedHeight(48)
        apply_cta_glow(self.start_scan_btn)
        self.start_scan_btn.clicked.connect(self._start_scan)
        self.start_scan_btn.setVisible(False)
        action_row.addWidget(self.calibrate_btn)
        action_row.addWidget(self.start_scan_btn)
        action_row.addStretch()
        left.addLayout(action_row)
        left.addStretch()
        page_row.addLayout(left, stretch=1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(16)
        right.addWidget(self._best_scan_card())
        right.addWidget(self._next_steps_card())
        right.addStretch()
        right_wrap = QWidget()
        right_wrap.setFixedWidth(320)
        right_wrap.setLayout(right)
        page_row.addWidget(right_wrap)

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

    @staticmethod
    def _tip_pill() -> QFrame:
        pill = QFrame()
        pill.setObjectName("TipPill")
        row = QHBoxLayout(pill)
        pill.setMinimumHeight(42)
        row.setContentsMargins(16, 9, 18, 9)
        row.setSpacing(10)
        bulb = QLabel()
        bulb.setPixmap(icon_pixmap("fa5.lightbulb", FOX, size=15))
        row.addWidget(bulb)
        text = QLabel(
            f'<span style="color:{ORANGE_TEXT}; font-weight:800;">Tip:</span> '
            "Use natural light and remove glasses for best results."
        )
        text.setTextFormat(Qt.TextFormat.RichText)
        row.addWidget(text)
        return pill

    @staticmethod
    def _best_scan_card() -> QFrame:
        frame, v = _card("How to get the best scan")
        for i, (icon_name, text) in enumerate(BEST_SCAN_TIPS):
            if i > 0:
                divider = QFrame()
                divider.setObjectName("Divider")
                divider.setFixedHeight(1)
                v.addWidget(divider)
            row = QHBoxLayout()
            row.setContentsMargins(0, 10, 0, 10)
            row.setSpacing(14)
            icon_lbl = QLabel()
            icon_lbl.setPixmap(icon_pixmap(icon_name, FOX, size=17))
            icon_lbl.setFixedWidth(22)
            row.addWidget(icon_lbl)
            label = QLabel(text)
            label.setWordWrap(True)
            row.addWidget(label, stretch=1)
            v.addLayout(row)
        return frame

    def _next_steps_card(self) -> QFrame:
        frame, v = _card("What happens next?")
        light = get_current_theme() == "light"
        for i, (icon_name, fg, bg, title, body_text) in enumerate(NEXT_STEPS):
            if i > 0:
                connector_row = QHBoxLayout()
                connector_row.setContentsMargins(21, 0, 0, 0)
                line = QFrame()
                line.setFixedSize(2, 16)
                line.setStyleSheet(f"background-color: {'#e7e9f0' if light else '#263457'}; border: none;")
                connector_row.addWidget(line)
                connector_row.addStretch()
                v.addLayout(connector_row)
            row = QHBoxLayout()
            row.setSpacing(12)
            row.addWidget(_icon_circle(icon_name, fg, bg, size=44, icon_size=18))
            number = QLabel(str(i + 1))
            number.setFixedSize(24, 24)
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setStyleSheet(
                f"background-color: {'#f1f2f6' if light else '#1a2340'}; border-radius: 12px; "
                "font-size: 11px; font-weight: 800;"
            )
            row.addWidget(number)
            text_col = QVBoxLayout()
            text_col.setSpacing(1)
            t = QLabel(title)
            t.setObjectName("CardTitle")
            text_col.addWidget(t)
            b = QLabel(body_text)
            b.setObjectName("SubHeading")
            b.setWordWrap(True)
            text_col.addWidget(b)
            row.addLayout(text_col, stretch=1)
            v.addLayout(row)

        v.addSpacing(10)
        self.analysis_btn = QPushButton("  Analysis")
        self.analysis_btn.setIcon(make_icon("fa5s.chart-bar", "white"))
        self.analysis_btn.setIconSize(QSize(17, 17))
        self.analysis_btn.setObjectName("Cta")
        self.analysis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analysis_btn.setFixedHeight(48)
        apply_cta_glow(self.analysis_btn)
        self.analysis_btn.clicked.connect(self._on_analysis_clicked)
        v.addWidget(self.analysis_btn)
        hint = QLabel("Analyzes your photo and opens the report in the Analysis tab.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        v.addWidget(hint)
        return frame

    def _on_analysis_clicked(self) -> None:
        """Analyze the current photo -- capturing one first if the camera is live."""
        if self._worker is not None and self._worker.isRunning():
            return
        if self.camera.current_frame() is not None:
            self._start_scan()
        elif self.camera.is_live():
            self._analyze_after_capture = True
            self.camera.capture()
        elif self.camera.is_running():
            self._show_toast("The camera is still starting \u2014 one moment, then press Analysis again.")
        else:
            self._show_toast("Start the camera or import a photo first, then press Analysis.")

    def _on_captured(self, frame: np.ndarray) -> None:
        self.error_banner.hide()
        self.calibrate_btn.setVisible(True)
        self.start_scan_btn.setVisible(True)
        if self._analyze_after_capture:
            self._analyze_after_capture = False
            self._start_scan()

    def _on_camera_error(self, message: str) -> None:
        self._analyze_after_capture = False
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
        self.analysis_btn.setEnabled(False)
        self.start_scan_btn.setEnabled(False)
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
        self.analysis_btn.setEnabled(True)
        self.start_scan_btn.setEnabled(True)
        self.stack.setCurrentIndex(0)

    def reset(self) -> None:
        """Open the page in its idle state: camera off, nothing captured. The
        camera only ever starts when the user asks for it."""
        self.camera.reset_to_idle()
        self.calibrate_btn.setVisible(False)
        self.start_scan_btn.setVisible(False)
        self.analysis_btn.setEnabled(True)
        self.start_scan_btn.setEnabled(True)
        self._analyze_after_capture = False
        self.error_banner.hide()
        self.stack.setCurrentIndex(0)

    def release_camera(self) -> None:
        """Switch the camera off (leaving the page, locking, hiding to the tray)."""
        self._analyze_after_capture = False
        self.camera.stop_camera()

    def start_camera(self) -> None:
        self.reset()
        self.camera.start_camera()

    def shutdown(self) -> None:
        self.camera.shutdown()
