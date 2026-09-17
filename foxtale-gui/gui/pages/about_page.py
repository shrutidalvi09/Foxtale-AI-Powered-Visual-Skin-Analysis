from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from gui.assets import apply_card_shadow
from gui.widgets.disclaimer import DisclaimerBanner

CARDS = [
    ("👁", "Visual observations only", "Every result is phrased as a visible observation, not a clinical finding."),
    ("🧮", "Explainable computer vision", "Classic image-processing heuristics (color, contrast, texture) — no opaque black-box model."),
    ("🔒", "Privacy-first, fully local", "Nothing leaves this device. Images aren't stored unless you opt in, and nothing is uploaded."),
    ("🛡", "Not a medical device", "Foxtale doesn't diagnose conditions or infer age, ethnicity, or health status."),
    ("🎚", "Personal calibration", "Optional skin-tone calibration adapts thresholds to you instead of one fixed baseline."),
    ("📈", "Trends over time", "Track how each category changes across scans, and compare any two scans directly."),
]


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(16)

        heading = QLabel("About Foxtale")
        heading.setObjectName("Heading")
        layout.addWidget(heading)

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
        for i, (emoji, title, body) in enumerate(CARDS):
            card = QFrame()
            card.setObjectName("Card")
            apply_card_shadow(card, blur=18, y_offset=4, alpha=22)
            v = QVBoxLayout(card)
            icon = QLabel(emoji)
            icon.setStyleSheet("font-size: 20px;")
            v.addWidget(icon)
            t = QLabel(title)
            t.setStyleSheet("font-weight: 700;")
            v.addWidget(t)
            b = QLabel(body)
            b.setWordWrap(True)
            b.setObjectName("SubHeading")
            v.addWidget(b)
            grid.addWidget(card, i // 2, i % 2)
        layout.addLayout(grid)

        layout.addWidget(DisclaimerBanner())
        layout.addStretch()
