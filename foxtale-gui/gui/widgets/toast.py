"""A small transient notification banner shown over the main window,
e.g. 'Scan saved', 'Report exported', 'History cleared'.

Rendered as a frosted-glass pill: a blurred snapshot of whatever's behind it
(grabbed once, right before it's shown) tinted with the active theme's glass
color, so it reads correctly in both light and dark mode instead of the
hardcoded white background it used to have.
"""

from typing import Optional

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.core.animations import blur_pixmap, fade_widget
from gui.theme import glass_border, glass_tint


class Toast(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("font-weight: 600; background: transparent;")
        layout.addWidget(self._label)

        self._backdrop: Optional[object] = None
        self.hide()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_hide)

    def show_message(self, text: str, duration_ms: int = 2200) -> None:
        self._timer.stop()
        self._label.setText(text)
        self.adjustSize()
        parent_rect = self.parent().rect()
        x = (parent_rect.width() - self.width()) // 2
        y = parent_rect.height() - self.height() - 28

        snapshot = self.parent().grab(QRect(x, y, self.width(), self.height()))
        self._backdrop = blur_pixmap(snapshot, radius=18)

        self.move(x, y)
        self.show()
        self.raise_()
        fade_widget(self, 0.0, 1.0, 150)
        self._timer.start(duration_ms)

    def _start_hide(self) -> None:
        fade_widget(self, 1.0, 0.0, 220, on_finished=self.hide)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.setClipPath(path)

        if self._backdrop is not None and not self._backdrop.isNull():
            painter.drawPixmap(0, 0, self._backdrop)
        painter.fillPath(path, QColor(*glass_tint()))

        painter.setClipping(False)
        painter.setPen(QPen(QColor(*glass_border()), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
