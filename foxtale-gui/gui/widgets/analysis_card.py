from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from engine.schemas import LEVEL_SCORE, CategoryResult, RegionObservation
from gui.assets import apply_card_shadow
from gui.core.explainability import LEVEL_THRESHOLDS, METHODOLOGY, flagged_regions_summary
from gui.theme import icon_color, level_pill_colors


class AnalysisCard(QFrame):
    def __init__(
        self, title: str, result: CategoryResult, detail: str,
        baseline_level: Optional[str] = None,
        category_key: Optional[str] = None, regions: Optional[List[RegionObservation]] = None,
        parent=None,
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

        if category_key is not None and category_key in METHODOLOGY:
            why_btn = QPushButton("Why this result?")
            why_btn.setObjectName("Secondary")
            why_btn.setCheckable(True)
            why_btn.setStyleSheet("font-size: 10.5px; padding: 3px 8px;")
            layout.addWidget(why_btn, alignment=Qt.AlignmentFlag.AlignLeft)

            why_body = QLabel(
                f"{METHODOLOGY[category_key]}\n\n"
                f"Levels: {LEVEL_THRESHOLDS}\n\n"
                f"{flagged_regions_summary(category_key, regions or [])}"
            )
            why_body.setObjectName("Muted")
            why_body.setWordWrap(True)
            why_body.setStyleSheet("font-size: 10.5px;")
            why_body.setVisible(False)
            layout.addWidget(why_body)

            def _toggle_why(checked: bool, body=why_body, btn=why_btn) -> None:
                body.setVisible(checked)
                btn.setText("Hide details" if checked else "Why this result?")

            why_btn.toggled.connect(_toggle_why)
