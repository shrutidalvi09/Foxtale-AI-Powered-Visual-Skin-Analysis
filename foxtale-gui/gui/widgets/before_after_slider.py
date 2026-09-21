"""An interactive before/after photo comparison: drag the vertical divider
(or the handle) to reveal more of the "before" or "after" image. Both photos
are center-cropped to the same square so they line up reasonably even
though they weren't captured with true facial-landmark alignment -- this is
a visual convenience, not a claim of precise registration.
"""

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


def _bgr_to_square_pixmap(frame: np.ndarray, size: int = 480) -> QPixmap:
    h, w = frame.shape[:2]
    side = min(h, w)
    y0, x0 = (h - side) // 2, (w - side) // 2
    cropped = frame[y0:y0 + side, x0:x0 + side]
    rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
    ch = rgb.shape[2]
    qimg = QImage(rgb.data, side, side, ch * side, QImage.Format.Format_RGB888).copy()
    pixmap = QPixmap.fromImage(qimg)
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class BeforeAfterSlider(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self._before: Optional[QPixmap] = None
        self._after: Optional[QPixmap] = None
        self._before_label = "Previous"
        self._after_label = "Current"
        self._split = 0.5  # 0..1, fraction of width showing "before"
        self._dragging = False

    def set_images(self, before_bgr: Optional[np.ndarray], after_bgr: Optional[np.ndarray],
                    before_label: str = "Previous", after_label: str = "Current") -> None:
        self._before = _bgr_to_square_pixmap(before_bgr) if before_bgr is not None else None
        self._after = _bgr_to_square_pixmap(after_bgr) if after_bgr is not None else None
        self._before_label = before_label
        self._after_label = after_label
        self._split = 0.5
        self.update()

    def _square_rect(self) -> QRectF:
        rect = self.rect()
        side = min(rect.width(), rect.height())
        return QRectF(
            (rect.width() - side) / 2, (rect.height() - side) / 2, side, side,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging = True
        self._update_split(event.position().x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._update_split(event.position().x())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging = False

    def _update_split(self, mouse_x: float) -> None:
        square = self._square_rect()
        if square.width() <= 0:
            return
        self._split = max(0.0, min(1.0, (mouse_x - square.left()) / square.width()))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        square = self._square_rect()

        painter.setBrush(QColor("#0b1224"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(square, 14, 14)

        if not self._before or not self._after:
            painter.setPen(QColor("#8993a8"))
            painter.drawText(square, Qt.AlignmentFlag.AlignCenter, "Both scans need a saved photo\nto compare visually.")
            painter.end()
            return

        painter.save()
        painter.setClipRect(square)
        painter.drawPixmap(square.toRect(), self._before)
        painter.restore()

        split_x = square.left() + square.width() * self._split
        after_rect = QRectF(split_x, square.top(), square.right() - split_x, square.height())
        painter.save()
        painter.setClipRect(after_rect)
        painter.drawPixmap(square.toRect(), self._after)
        painter.restore()

        painter.setPen(QPen(QColor("white"), 3))
        painter.drawLine(QPointF(split_x, square.top()), QPointF(split_x, square.bottom()))
        handle_r = 12
        painter.setBrush(QColor("white"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(split_x, square.center().y()), handle_r, handle_r)
        painter.setPen(QPen(QColor("#33415c"), 2))
        painter.drawLine(int(split_x - 4), int(square.center().y()), int(split_x - 1), int(square.center().y()))
        painter.drawLine(int(split_x + 1), int(square.center().y()), int(split_x + 4), int(square.center().y()))

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor("white"))
        label_bg = QColor(11, 18, 36, 190)
        for text, x_anchor, align in [
            (self._before_label, square.left() + 10, Qt.AlignmentFlag.AlignLeft),
            (self._after_label, square.right() - 10, Qt.AlignmentFlag.AlignRight),
        ]:
            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(text) + 16
            tag_rect = QRectF(
                x_anchor if align == Qt.AlignmentFlag.AlignLeft else x_anchor - text_w,
                square.top() + 10, text_w, 22,
            )
            painter.setBrush(label_bg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(tag_rect, 6, 6)
            painter.setPen(QColor("white"))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()
