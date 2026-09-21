from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from engine.schemas import LEVEL_SCORE, CategoryResult
from gui.assets import apply_card_shadow
from gui.theme import icon_color, level_pill_colors


class AnalysisCard(QFrame):
    def __init__(
        self, title: str, result: CategoryResult, detail: str,
        baseline_level: Optional[str] = None, parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("Card")
        apply_card_shadow(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QLabel(title)
        header.setStyleSheet("font-weight: 700; font-size: 13px;")
        layout.addWidget(header)

        pill = QLabel(result.level.title())
        bg, text = level_pill_colors(result.level)
        pill.setStyleSheet(
            f"background-color: {bg}; color: {text}; border: none; "
            "border-radius: 10px; padding: 4px 10px; font-weight: 800; max-width: 110px;"
        )
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(pill, alignment=Qt.AlignmentFlag.AlignLeft)

        detail_label = QLabel(detail)
        detail_label.setObjectName("SubHeading")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)

        conf_label = QLabel(f"{int(result.confidence * 100)}% confidence")
        conf_label.setObjectName("Muted")
        layout.addWidget(conf_label)

        if baseline_level is not None:
            current_score = LEVEL_SCORE[result.level]
            baseline_score = LEVEL_SCORE[baseline_level]
            if current_score > baseline_score:
                text, kind = "Higher than your usual", "warning"
            elif current_score < baseline_score:
                text, kind = "Lower than your usual", "success"
            else:
                text, kind = "About your usual", "accent"
            baseline_label = QLabel(text)
            baseline_label.setStyleSheet(f"color: {icon_color(kind)}; font-weight: 700; font-size: 11px;")
            layout.addWidget(baseline_label)
