"""A full-window overlay that blocks the app behind a PIN prompt. It's a
plain QWidget positioned to cover the whole central widget (sidebar
included) and raised above everything else -- MainWindow is responsible for
keeping its geometry in sync on resize.

The background is a frosted-glass treatment: a blurred snapshot of whatever
was on screen the moment the lock screen appears, tinted with the active
theme's glass color -- theme-aware, unlike the plain hardcoded white
background this used to have (which ignored dark mode entirely).
"""

from typing import Optional

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow, logo_mark_pixmap
from gui.core import app_lock
from gui.core.animations import blur_pixmap
from gui.theme import glass_tint, level_pill_colors


class LockScreen(QWidget):
    unlocked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backdrop: Optional[object] = None

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
        _, error_text_color = level_pill_colors("noticeable")
        self.error_label.setStyleSheet(f"color: {error_text_color}; font-size: 11px;")
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
        parent = self.parentWidget()
        if parent is not None and parent.width() > 0 and parent.height() > 0:
            snapshot = parent.grab(QRect(0, 0, parent.width(), parent.height()))
            self._backdrop = blur_pixmap(snapshot, radius=26)
        else:
            self._backdrop = None
        self.pin_edit.clear()
        self.error_label.setText("")
        self.pin_edit.setFocus()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        rect = self.rect()
        if self._backdrop is not None and not self._backdrop.isNull():
            painter.drawPixmap(0, 0, self._backdrop)
        painter.fillRect(rect, QColor(*glass_tint()))

    def _try_unlock(self) -> None:
        if app_lock.verify_pin(self.pin_edit.text()):
            self.unlocked.emit()
        else:
            self.error_label.setText("Incorrect PIN. Try again.")
            self.pin_edit.clear()
            self.pin_edit.setFocus()
