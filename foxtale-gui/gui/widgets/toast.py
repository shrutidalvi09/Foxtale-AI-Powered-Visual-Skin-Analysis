"""A small transient notification banner shown over the main window,
e.g. 'Scan saved', 'Report exported', 'History cleared'."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

from gui.assets import apply_card_shadow


class Toast(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background-color: #0b1224; color: white; border-radius: 12px; "
            "padding: 10px 18px; font-weight: 600;"
        )
        apply_card_shadow(self, blur=24, y_offset=6, alpha=90)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, duration_ms: int = 2200) -> None:
        self.setText(text)
        self.adjustSize()
        parent_rect = self.parent().rect()
        x = (parent_rect.width() - self.width()) // 2
        y = parent_rect.height() - self.height() - 28
        self.move(x, y)
        self.show()
        self.raise_()
        self._timer.start(duration_ms)
