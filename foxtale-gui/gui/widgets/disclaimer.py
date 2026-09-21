from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from engine.schemas import DISCLAIMER
from gui.assets import apply_card_shadow, icon_pixmap
from gui.theme import icon_color


class DisclaimerBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Disclaimer")
        apply_card_shadow(self, blur=18, y_offset=4, alpha=20)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        icon = QLabel()
        icon.setPixmap(icon_pixmap("fa5s.exclamation-triangle", icon_color("warning"), size=16))
        layout.addWidget(icon)

        text = QLabel(f"<b>AI Disclaimer:</b> {DISCLAIMER}")
        text.setWordWrap(True)
        text.setStyleSheet("font-size: 11.5px;")
        layout.addWidget(text, stretch=1)
