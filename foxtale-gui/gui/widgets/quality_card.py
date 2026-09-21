"""Displays the composite capture-quality score for a scan: overall 0-100
plus the five sub-scores that feed it, so users can tell a genuine skin
change from "the photo was just darker/blurrier this time"."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from engine.quality import QualityResult
from gui.theme import LEVEL_COLORS

SUB_SCORES = [
    ("Position", "position_score"),
    ("Lighting", "lighting_score"),
    ("Distance", "distance_score"),
    ("Sharpness", "sharpness_score"),
    ("Angle", "angle_score"),
]


def _score_color(score: int) -> str:
    if score >= 80:
        return LEVEL_COLORS["minimal"]
    if score >= 60:
        return LEVEL_COLORS["mild"]
    if score >= 40:
        return LEVEL_COLORS["moderate"]
    return LEVEL_COLORS["noticeable"]


class QualityCard(QFrame):
    def __init__(self, quality: QualityResult, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QLabel("Scan Quality")
        header.setStyleSheet("font-weight: 700; font-size: 13px;")
        layout.addWidget(header)

        overall_row = QHBoxLayout()
        overall = QLabel(f"{quality.overall}")
        overall.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {_score_color(quality.overall)};")
        overall_row.addWidget(overall)
        out_of = QLabel("/ 100")
        out_of.setObjectName("Muted")
        out_of.setAlignment(Qt.AlignmentFlag.AlignBottom)
        overall_row.addWidget(out_of)
        overall_row.addStretch()
        layout.addLayout(overall_row)

        for label, attr in SUB_SCORES:
            value = getattr(quality, attr)
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("Muted")
            row.addWidget(name)
            row.addStretch()
            val = QLabel(str(value))
            val.setStyleSheet(f"font-weight: 700; color: {_score_color(value)};")
            row.addWidget(val)
            layout.addLayout(row)

        if quality.tips:
            tip = QLabel(quality.tips[0])
            tip.setObjectName("Muted")
            tip.setWordWrap(True)
            layout.addWidget(tip)
