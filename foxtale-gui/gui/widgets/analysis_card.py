from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from engine.schemas import CategoryResult
from gui.assets import apply_card_shadow
from gui.theme import LEVEL_COLORS


class AnalysisCard(QFrame):
    def __init__(self, title: str, result: CategoryResult, detail: str, parent=None):
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
        color = LEVEL_COLORS.get(result.level, "#3b8dff")
        pill.setStyleSheet(
            f"background-color: {color}22; color: {color}; border: 1px solid {color}55; "
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
