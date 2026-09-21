"""A full-window overlay that blocks the app behind a PIN prompt. It's a
plain QWidget positioned to cover the whole central widget (sidebar
included) and raised above everything else -- MainWindow is responsible for
keeping its geometry in sync on resize.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow, logo_mark_pixmap
from gui.core import app_lock


class LockScreen(QWidget):
    unlocked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: white;")

        outer = QVBoxLayout(self)
        outer.addStretch()

        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(340)
        apply_card_shadow(card, blur=30, y_offset=10, alpha=30)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(12)

        mark = QLabel()
        mark.setPixmap(logo_mark_pixmap(40))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(mark)

        heading = QLabel("Foxtale is locked")
        heading.setObjectName("Heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 18px; font-weight: 800;")
        card_layout.addWidget(heading)

        sub = QLabel("Enter your PIN to continue.")
        sub.setObjectName("SubHeading")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(sub)

        self.pin_edit = QLineEdit()
        self.pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pin_edit.setPlaceholderText("PIN")
        self.pin_edit.returnPressed.connect(self._try_unlock)
        card_layout.addWidget(self.pin_edit)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #be123c; font-size: 11px;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.error_label)

        unlock_btn = QPushButton("Unlock")
        unlock_btn.setObjectName("Primary")
        unlock_btn.clicked.connect(self._try_unlock)
        card_layout.addWidget(unlock_btn)

        centered = QWidget()
        h = QHBoxLayout(centered)
        h.addStretch()
        h.addWidget(card)
        h.addStretch()
        outer.addWidget(centered)
        outer.addStretch()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.pin_edit.clear()
        self.error_label.setText("")
        self.pin_edit.setFocus()

    def _try_unlock(self) -> None:
        if app_lock.verify_pin(self.pin_edit.text()):
            self.unlocked.emit()
        else:
            self.error_label.setText("Incorrect PIN. Try again.")
            self.pin_edit.clear()
            self.pin_edit.setFocus()
