"""Small, standard "Help menu" dialogs: About and Keyboard Shortcuts."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from gui.assets import logo_full_pixmap
from gui.pages.about_page import ENGINE_INFO_ROWS

SHORTCUTS = [
    ("New Scan", "Ctrl+N"),
    ("Open Settings", "Ctrl+,"),
    ("Open History", "Ctrl+H"),
    ("Go to Home", "Esc"),
    ("Exit", "Ctrl+Q"),
]


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Foxtale")
        self.setModal(True)
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(logo_full_pixmap(60))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        sub = QLabel("AI-Powered Visual Skin Analysis — Desktop Edition")
        sub.setObjectName("SubHeading")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        for label, value in ENGINE_INFO_ROWS:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("Muted")
            row.addWidget(name)
            row.addStretch()
            val = QLabel(value)
            val.setStyleSheet("font-weight: 700;")
            row.addWidget(val)
            layout.addLayout(row)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("Secondary")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(True)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(10)

        heading = QLabel("Keyboard Shortcuts")
        heading.setStyleSheet("font-weight: 800; font-size: 15px;")
        layout.addWidget(heading)

        for label, keys in SHORTCUTS:
            row = QHBoxLayout()
            name = QLabel(label)
            row.addWidget(name)
            row.addStretch()
            keys_label = QLabel(keys)
            keys_label.setObjectName("Badge")
            row.addWidget(keys_label)
            layout.addLayout(row)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("Secondary")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
