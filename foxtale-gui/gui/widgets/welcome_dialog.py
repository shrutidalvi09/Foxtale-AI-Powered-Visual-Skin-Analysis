"""A first-run welcome dialog: shown exactly once, right after a fresh
install, to set expectations (visible observations, not diagnoses; fully
local) before the user ever opens the camera -- and to let them pick a
theme up front instead of discovering it buried in Settings.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QRadioButton, QVBoxLayout,
)

from gui.assets import logo_full_pixmap

POINTS = [
    "Visual observations only — never a diagnosis, always plain language about what's visible.",
    "Fully local — your photos and analysis never leave this device.",
    "Built to track change over time, not to judge a single photo.",
]


class WelcomeDialog(QDialog):
    def __init__(self, current_theme: str = "light", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Foxtale")
        self.setModal(True)
        self.setFixedWidth(480)
        self.selected_theme = current_theme

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 28)
        layout.setSpacing(14)

        logo = QLabel()
        logo.setPixmap(logo_full_pixmap(70))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        heading = QLabel("Welcome to Foxtale")
        heading.setObjectName("Heading")
        heading.setStyleSheet("font-size: 20px; font-weight: 800;")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        sub = QLabel("Before your first scan, a few things worth knowing:")
        sub.setObjectName("SubHeading")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        for point in POINTS:
            row = QHBoxLayout()
            bullet = QLabel("•")
            bullet.setStyleSheet("font-weight: 800;")
            row.addWidget(bullet)
            text = QLabel(point)
            text.setWordWrap(True)
            row.addWidget(text, stretch=1)
            layout.addLayout(row)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        theme_label = QLabel("Choose a look to start with (you can change this anytime):")
        theme_label.setObjectName("Muted")
        theme_label.setWordWrap(True)
        layout.addWidget(theme_label)

        theme_row = QHBoxLayout()
        self.light_radio = QRadioButton("Light")
        self.dark_radio = QRadioButton("Dark")
        group = QButtonGroup(self)
        group.addButton(self.light_radio)
        group.addButton(self.dark_radio)
        (self.dark_radio if current_theme == "dark" else self.light_radio).setChecked(True)
        theme_row.addWidget(self.light_radio)
        theme_row.addWidget(self.dark_radio)
        theme_row.addStretch()
        layout.addLayout(theme_row)

        start_btn = QPushButton("Get Started")
        start_btn.setObjectName("Primary")
        start_btn.setMinimumHeight(38)
        start_btn.clicked.connect(self._on_start)
        layout.addWidget(start_btn)

    def _on_start(self) -> None:
        self.selected_theme = "dark" if self.dark_radio.isChecked() else "light"
        self.accept()
