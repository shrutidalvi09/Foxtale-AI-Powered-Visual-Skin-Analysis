"""Building blocks for the Analysis page: the photo panel (with its empty
state), a small face sketch for the "Visible Observation" card, and the
region donut chart.
"""

from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QStackedLayout, QVBoxLayout, QWidget,
)

from engine.schemas import RegionObservation
from gui.assets import apply_card_shadow, icon as make_icon, icon_pixmap
from gui.theme import FOX, get_current_theme
from gui.widgets.face_report import FaceReportView

PANEL_RADIUS = 20


class EmptyPhotoState(QFrame):
    """The dark placeholder shown in the photo slot when there is nothing
    to display yet -- painted on its own dark surface (independent of the
    light/dark theme, like the camera preview) with orange viewfinder
    brackets and a dotted ring behind the message."""

    start_scan = Signal()
    upload_image = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(0)
        layout.addStretch()

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(76, 76)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(
            "background-color: rgba(255,255,255,18); border: 1.5px solid rgba(255,255,255,80); "
            "border-radius: 38px;"
        )
        self.icon_label.setPixmap(icon_pixmap("fa5s.camera", "#f39a63", size=28))
        layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(14)

        self.title = QLabel()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: white; font-size: 16px; font-weight: 800;")
        layout.addWidget(self.title)
        layout.addSpacing(6)

        self.body = QLabel()
        self.body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.setWordWrap(True)
        self.body.setStyleSheet("color: #d3d8e6; font-size: 12.5px;")
        layout.addWidget(self.body)
        layout.addSpacing(18)

        self.start_btn = QPushButton("  Start New Scan")
        self.start_btn.setIcon(make_icon("fa5s.camera", "white"))
        self.start_btn.setIconSize(QSize(16, 16))
        self.start_btn.setFixedSize(220, 46)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #d43f00; color: white; border: none; border-radius: 23px; "
            "font-weight: 800; font-size: 13px; }"
            "QPushButton:hover { background-color: #bf3800; }"
        )
        self.start_btn.clicked.connect(self.start_scan.emit)
        layout.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(12)

        self.upload_btn = QPushButton("  Upload Image")
        self.upload_btn.setIcon(make_icon("fa5s.upload", "white"))
        self.upload_btn.setIconSize(QSize(16, 16))
        self.upload_btn.setFixedSize(220, 46)
        self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upload_btn.setStyleSheet(
            "QPushButton { background-color: transparent; color: white; border: 1.5px solid rgba(255,255,255,170); "
            "border-radius: 23px; font-weight: 700; font-size: 13px; }"
            "QPushButton:hover { background-color: rgba(255,255,255,28); }"
        )
        self.upload_btn.clicked.connect(self.upload_image.emit)
        layout.addWidget(self.upload_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

        self.set_mode("empty")

    def set_mode(self, mode: str) -> None:
        if mode == "no_photo":
            self.title.setText("No photo saved for this scan")
            self.body.setText(
                "Turn on “Also save captured images” in Settings to see markers and the "
                "heatmap on your photo."
            )
            self.start_btn.setVisible(False)
            self.upload_btn.setVisible(False)
        else:
            self.title.setText("No captured image available")
            self.body.setText("Capture or upload a clear face image to view heatmap and analysis.")
            self.start_btn.setVisible(True)
            self.upload_btn.setVisible(True)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())

        clip = QPainterPath()
        clip.addRoundedRect(rect, PANEL_RADIUS, PANEL_RADIUS)
        painter.setClipPath(clip)

        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, QColor("#1b2130"))
        base.setColorAt(1.0, QColor("#0b0f1b"))
        painter.fillRect(rect, base)

        ring_pen = QPen(QColor(255, 255, 255, 46), 1.2)
        ring_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        radius = min(rect.width(), rect.height()) * 0.44
        painter.drawEllipse(rect.center(), radius, radius)

        bracket = QPen(QColor(FOX), 2.6)
        bracket.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bracket)
        inset, arm = 18.0, 26.0
        x0, y0 = rect.left() + inset, rect.top() + inset
        x1, y1 = rect.right() - inset, rect.bottom() - inset
        for sx, sy, dx, dy in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
            painter.drawLine(QPointF(sx, sy), QPointF(sx + dx * arm, sy))
            painter.drawLine(QPointF(sx, sy), QPointF(sx, sy + dy * arm))
        painter.end()


class PhotoPanel(QWidget):
    """The photo slot: the annotated scan photo when there is one, or the
    dark empty state (no scan yet / no photo saved for this scan)."""

    marker_clicked = Signal(object)  # RegionObservation
    start_scan = Signal()
    upload_image = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(340)
        apply_card_shadow(self)
        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self.face_report = FaceReportView()
        self.face_report.marker_clicked.connect(self.marker_clicked)
        self._stack.addWidget(self.face_report)

        self.empty_state = EmptyPhotoState()
        self.empty_state.start_scan.connect(self.start_scan)
        self.empty_state.upload_image.connect(self.upload_image)
        self._stack.addWidget(self.empty_state)

        self.show_empty()

    def show_empty(self) -> None:
        self.empty_state.set_mode("empty")
        self._stack.setCurrentWidget(self.empty_state)

    def show_no_photo(self) -> None:
        self.empty_state.set_mode("no_photo")
        self._stack.setCurrentWidget(self.empty_state)

    def show_photo(self, image: np.ndarray, regions: List[RegionObservation]) -> None:
        self.face_report.set_image(image, regions)
        self._stack.setCurrentWidget(self.face_report)

    def set_heatmap_mode(self, enabled: bool, category_filter: Optional[str] = None) -> None:
        self.face_report.set_heatmap_mode(enabled, category_filter)


class FaceSketch(QWidget):
    """A faint line-art face with five orange dots (forehead, cheeks, nose,
    chin) -- a picture of the kind of marker the photo shows, not real data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 132)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        light = get_current_theme() == "light"
        line = QColor("#c9ceda" if light else "#3a4666")
        pen = QPen(line, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        def pt(u: float, v: float) -> QPointF:
            return QPointF(u * w, v * h)

        head = QPainterPath()
        head.moveTo(pt(0.50, 0.04))
        head.cubicTo(pt(0.74, 0.04), pt(0.80, 0.34), pt(0.74, 0.56))
        head.cubicTo(pt(0.70, 0.72), pt(0.60, 0.90), pt(0.50, 0.95))
        head.cubicTo(pt(0.40, 0.90), pt(0.30, 0.72), pt(0.26, 0.56))
        head.cubicTo(pt(0.20, 0.34), pt(0.26, 0.04), pt(0.50, 0.04))
        painter.drawPath(head)
        for side in (-1, 1):
            cx = 0.5 + side * 0.13
            painter.drawArc(QRectF((cx - 0.07) * w, 0.36 * h, 0.14 * w, 0.09 * h), 0, 180 * 16)
            painter.drawArc(QRectF((cx - 0.08) * w, 0.27 * h, 0.16 * w, 0.07 * h), 30 * 16, 120 * 16)
        painter.drawLine(pt(0.50, 0.42), pt(0.48, 0.60))
        painter.drawArc(QRectF(0.44 * w, 0.72 * h, 0.12 * w, 0.06 * h), 200 * 16, 140 * 16)

        painter.setPen(Qt.PenStyle.NoPen)
        for u, v in [(0.50, 0.11), (0.35, 0.60), (0.65, 0.60), (0.50, 0.55), (0.50, 0.88)]:
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(pt(u, v), 6.5, 6.5)
            painter.setBrush(QColor(FOX))
            painter.drawEllipse(pt(u, v), 4.2, 4.2)
        painter.end()


class RegionDonut(QWidget):
    """Donut chart of observations per region. With no data it draws a
    quiet placeholder ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(124, 124)
        self._segments: List[Tuple[str, int]] = []  # (color, value)
        self._center_text = ""

    def set_segments(self, segments: List[Tuple[str, int]], center_text: str = "") -> None:
        self._segments = [(c, v) for c, v in segments if v > 0]
        self._center_text = center_text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        light = get_current_theme() == "light"
        thickness = 20
        rect = QRectF(self.rect()).adjusted(thickness / 2 + 2, thickness / 2 + 2, -thickness / 2 - 2, -thickness / 2 - 2)

        track = QPen(QColor("#eceef4" if light else "#1f2947"), thickness)
        painter.setPen(track)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

        total = sum(v for _, v in self._segments)
        if total == 0:
            accent = QPen(QColor("#fde4d3" if light else "#3a2818"), thickness)
            accent.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(accent)
            painter.drawArc(rect, 40 * 16, -95 * 16)
        else:
            start = 90.0
            for color, value in self._segments:
                span = 360.0 * value / total
                pen = QPen(QColor(color), thickness)
                painter.setPen(pen)
                gap = 3.0 if len(self._segments) > 1 else 0.0
                painter.drawArc(rect, int(start * 16), int(-(span - gap) * 16))
                start -= span

        if self._center_text:
            painter.setPen(QColor("#0b1224" if light else "#e7ecf7"))
            font = painter.font()
            font.setPointSizeF(15)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self._center_text)
        painter.end()
