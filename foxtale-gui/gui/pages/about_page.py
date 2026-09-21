import cv2
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.assets import apply_card_shadow, icon_pixmap, logo_mark_pixmap
from gui.theme import icon_color
from gui.widgets.disclaimer import DisclaimerBanner

ENGINE_INFO_ROWS = [
    ("Face detector", "OpenCV Haar Cascade (frontalface_default)"),
    ("Analysis engine", "Rule-based image heuristics, v1.0"),
    ("OpenCV version", cv2.__version__),
    ("App version", "1.0 · Desktop"),
]

CARDS = [
    ("fa5s.eye", "Visual observations only", "Every result is phrased as a visible observation, not a clinical finding."),
    ("fa5s.calculator", "Explainable computer vision", "Classic image-processing heuristics (color, contrast, texture) — no opaque black-box model."),
    ("fa5s.lock", "Privacy-first, fully local", "Nothing leaves this device. Images aren't stored unless you opt in, and nothing is uploaded."),
    ("fa5s.shield-alt", "Not a medical device", "Foxtale doesn't diagnose conditions or infer age, ethnicity, or health status."),
    ("fa5s.sliders-h", "Personal calibration", "Optional skin-tone calibration adapts thresholds to you instead of one fixed baseline."),
    ("fa5s.chart-line", "Trends over time", "Track how each category changes across scans, and compare any two scans directly."),
]


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        mark_label = QLabel()
        mark_label.setPixmap(logo_mark_pixmap(36))
        header_row.addWidget(mark_label)
        heading = QLabel("About Foxtale")
        heading.setObjectName("Heading")
        header_row.addWidget(heading)
        header_row.addStretch()
        layout.addLayout(header_row)

        intro = QLabel(
            "Foxtale Desktop is the native GUI edition of Foxtale — an AI-powered visual skin "
            "analysis tool. It uses your webcam to capture a photo, detects your face locally, "
            "and runs computer-vision heuristics entirely on this device."
        )
        intro.setWordWrap(True)
        intro.setObjectName("SubHeading")
        layout.addWidget(intro)

        grid = QGridLayout()
        grid.setSpacing(12)
        card_icon_color = icon_color("accent")
        for i, (icon_name, title, body) in enumerate(CARDS):
            card = QFrame()
            card.setObjectName("Card")
            apply_card_shadow(card, blur=18, y_offset=4, alpha=22)
            v = QVBoxLayout(card)
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap(icon_name, card_icon_color, size=20))
            v.addWidget(icon_label)
            t = QLabel(title)
            t.setStyleSheet("font-weight: 700;")
            v.addWidget(t)
            b = QLabel(body)
            b.setWordWrap(True)
            b.setObjectName("SubHeading")
            v.addWidget(b)
            grid.addWidget(card, i // 2, i % 2)
        layout.addLayout(grid)

        layout.addWidget(self._engine_card())
        layout.addWidget(DisclaimerBanner())
        layout.addStretch()

    def _engine_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        apply_card_shadow(frame)
        v = QVBoxLayout(frame)
        title = QLabel("Engine & Model")
        title.setStyleSheet("font-weight: 800; font-size: 14px;")
        v.addWidget(title)
        for label, value in ENGINE_INFO_ROWS:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("Muted")
            row.addWidget(name)
            row.addStretch()
            val = QLabel(value)
            val.setStyleSheet("font-weight: 700;")
            row.addWidget(val)
            v.addLayout(row)
        return frame
