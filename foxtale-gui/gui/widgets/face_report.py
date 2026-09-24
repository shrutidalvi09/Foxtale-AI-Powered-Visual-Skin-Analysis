"""Captured photo with clickable observation markers, mirroring the web
app's face-visualization panel."""

from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from engine.schemas import RegionObservation
from gui.theme import CATEGORY_QCOLOR

MARKER_RADIUS = 8
HIT_RADIUS = 14
HEATMAP_BLOB_RADIUS = 46


class FaceReportView(QWidget):
    marker_clicked = Signal(object)  # RegionObservation

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self._pixmap: Optional[QPixmap] = None
        self._regions: List[RegionObservation] = []
        self._marker_screen_pos: List[tuple] = []  # (screen_x, screen_y, region)
        self._image_rect = None
        self._heatmap_enabled = False
        self._heatmap_category: Optional[str] = None

    def set_heatmap_mode(self, enabled: bool, category_filter: Optional[str] = None) -> None:
        self._heatmap_enabled = enabled
        self._heatmap_category = category_filter
        self.update()

    def _visible_regions(self) -> List[RegionObservation]:
        if self._heatmap_category:
            return [r for r in self._regions if r.category == self._heatmap_category]
        return self._regions

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
        rect = QRectF(self.rect())

        clip = QPainterPath()
        clip.addRoundedRect(rect, 20, 20)
        painter.setClipPath(clip)
        painter.fillRect(rect, QColor("#0d1220"))

        self._marker_screen_pos = []

        if self._pixmap:
            # Fit the whole photo (never crop a forehead or chin away) and
            # letterbox it on the dark panel.
            scaled = self._pixmap.scaled(
                rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = int(rect.x() + (rect.width() - scaled.width()) / 2)
            y = int(rect.y() + (rect.height() - scaled.height()) / 2)
            painter.drawPixmap(x, y, scaled)
            self._image_rect = (x, y, scaled.width(), scaled.height())
            photo_rect = QRectF(x, y, scaled.width(), scaled.height())
            visible = self._visible_regions()

            if self._heatmap_enabled:
                painter.save()
                painter.setClipRect(photo_rect)
                for r in visible:
                    sx = x + int(r.x * scaled.width())
                    sy = y + int(r.y * scaled.height())
                    base = QColor(CATEGORY_QCOLOR.get(r.category, "#3b8dff"))
                    gradient = QRadialGradient(QPointF(sx, sy), HEATMAP_BLOB_RADIUS)
                    hot = QColor(base)
                    hot.setAlpha(160)
                    cold = QColor(base)
                    cold.setAlpha(0)
                    gradient.setColorAt(0.0, hot)
                    gradient.setColorAt(1.0, cold)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(gradient)
                    painter.drawEllipse(QPointF(sx, sy), HEATMAP_BLOB_RADIUS, HEATMAP_BLOB_RADIUS)
                painter.restore()

            for r in visible:
                sx = x + int(r.x * scaled.width())
                sy = y + int(r.y * scaled.height())
                if not photo_rect.contains(sx, sy):
                    continue
                color = QColor(CATEGORY_QCOLOR.get(r.category, "#3b8dff"))
                painter.setPen(QPen(QColor("white"), 2))
                painter.setBrush(color)
                painter.drawEllipse(sx - MARKER_RADIUS, sy - MARKER_RADIUS, MARKER_RADIUS * 2, MARKER_RADIUS * 2)
                self._marker_screen_pos.append((sx, sy, r))
        else:
            painter.setPen(QColor("#b9bfd0"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No captured image available")

        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        for sx, sy, region in self._marker_screen_pos:
            if (pos.x() - sx) ** 2 + (pos.y() - sy) ** 2 <= HIT_RADIUS ** 2:
                self.marker_clicked.emit(region)
                return
        super().mousePressEvent(event)
