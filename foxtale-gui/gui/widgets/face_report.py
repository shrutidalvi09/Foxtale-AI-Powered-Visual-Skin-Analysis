"""Captured photo with clickable observation markers, mirroring the web
app's face-visualization panel."""

from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from engine.schemas import RegionObservation
from gui.theme import CATEGORY_QCOLOR

MARKER_RADIUS = 8
HIT_RADIUS = 14


class FaceReportView(QWidget):
    marker_clicked = Signal(object)  # RegionObservation

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self._pixmap: Optional[QPixmap] = None
        self._regions: List[RegionObservation] = []
        self._marker_screen_pos: List[tuple] = []  # (screen_x, screen_y, region)
        self._image_rect = None

    def set_image(self, frame_bgr: Optional[np.ndarray], regions: List[RegionObservation]) -> None:
        self._regions = regions
        if frame_bgr is not None:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self._pixmap = QPixmap.fromImage(qimg.copy())
        else:
            self._pixmap = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        side = min(rect.width(), rect.height())
        square = rect.adjusted(
            (rect.width() - side) // 2, (rect.height() - side) // 2,
            -(rect.width() - side) // 2, -(rect.height() - side) // 2,
        )

        painter.setBrush(QColor("#0b1224"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(square, 18, 18)

        self._marker_screen_pos = []

        if self._pixmap:
            painter.save()
            painter.setClipRect(square)
            scaled = self._pixmap.scaled(
                square.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = square.x() - (scaled.width() - square.width()) // 2
            y = square.y() - (scaled.height() - square.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.restore()
            self._image_rect = (x, y, scaled.width(), scaled.height())

            for r in self._regions:
                sx = x + int(r.x * scaled.width())
                sy = y + int(r.y * scaled.height())
                if not square.contains(sx, sy):
                    continue
                color = QColor(CATEGORY_QCOLOR.get(r.category, "#3b8dff"))
                painter.setPen(QPen(QColor("white"), 2))
                painter.setBrush(color)
                painter.drawEllipse(sx - MARKER_RADIUS, sy - MARKER_RADIUS, MARKER_RADIUS * 2, MARKER_RADIUS * 2)
                self._marker_screen_pos.append((sx, sy, r))
        else:
            painter.setPen(QColor("#8993a8"))
            painter.drawText(square, Qt.AlignmentFlag.AlignCenter, "No captured image available")

        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        for sx, sy, region in self._marker_screen_pos:
            if (pos.x() - sx) ** 2 + (pos.y() - sy) ** 2 <= HIT_RADIUS ** 2:
                self.marker_clicked.emit(region)
                return
        super().mousePressEvent(event)
