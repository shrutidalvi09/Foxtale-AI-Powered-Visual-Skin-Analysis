from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.assets import apply_card_shadow
from gui.widgets.disclaimer import DisclaimerBanner

FEATURES = [
    ("📷", "Camera-based analysis", "Live face-lock guidance before you even capture"),
    ("👁", "Visual skin observations", "Never a diagnosis — always plain, visible findings"),
    ("🔒", "Private, local processing", "Nothing leaves this device, ever"),
    ("📈", "Trend tracking over time", "Compare scans and watch your progress"),
]


class HomePage(QWidget):
    def __init__(self, on_start_scan, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.setSpacing(22)

        hero = QFrame()
        hero.setObjectName("HeroPanel")
        apply_card_shadow(hero, blur=32, y_offset=10, alpha=25)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(48, 52, 48, 52)
        hero_layout.setSpacing(14)

        badge = QLabel("🦊  FOXTALE DESKTOP")
        badge.setObjectName("Badge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        heading = QLabel("Understand Your Skin\nThrough AI Vision")
        heading.setObjectName("Heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 34px; font-weight: 800;")
        hero_layout.addWidget(heading)

        sub = QLabel(
            "Scan your face with your webcam and get an easy-to-understand, visual skin\n"
            "observation report — processed entirely on this device."
        )
        sub.setObjectName("SubHeading")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(sub)

        start_btn = QPushButton("Start Face Scan")
        start_btn.setObjectName("Primary")
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.setMinimumWidth(220)
        start_btn.setMinimumHeight(40)
        apply_card_shadow(start_btn, blur=20, y_offset=8, alpha=60)
        start_btn.clicked.connect(on_start_scan)
        hero_layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(hero)

        grid = QGridLayout()
        grid.setSpacing(14)
        for i, (emoji, title, body) in enumerate(FEATURES):
            card = QFrame()
            card.setObjectName("Card")
            apply_card_shadow(card, blur=18, y_offset=4, alpha=22)
            card_layout = QVBoxLayout(card)
            icon = QLabel(emoji)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("font-size: 24px;")
            card_layout.addWidget(icon)
            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setWordWrap(True)
            title_label.setStyleSheet("font-size: 11.5px; font-weight: 700;")
            card_layout.addWidget(title_label)
            body_label = QLabel(body)
            body_label.setObjectName("Muted")
            body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body_label.setWordWrap(True)
            card_layout.addWidget(body_label)
            grid.addWidget(card, 0, i)
        outer.addLayout(grid)

        outer.addWidget(DisclaimerBanner())
        outer.addStretch()
