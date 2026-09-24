from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from engine.schemas import DISCLAIMER
from gui.assets import apply_card_shadow, icon_pixmap
from gui.theme import FOX


class DisclaimerBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Disclaimer")
        apply_card_shadow(self, blur=18, y_offset=4, alpha=20)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        icon = QLabel()
        icon.setPixmap(icon_pixmap("mdi6.shield-check-outline", FOX, size=24))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(icon)

        text = QLabel(f"<b>AI Disclaimer:</b> {DISCLAIMER}")
        text.setWordWrap(True)
        text.setStyleSheet("font-size: 12px;")
        layout.addWidget(text, stretch=1)
