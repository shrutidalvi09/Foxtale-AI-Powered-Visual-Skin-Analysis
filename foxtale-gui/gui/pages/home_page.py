"""Dashboard-style Home page: greeting header, at-a-glance stats, a hero
scan-CTA card, a "Skin Journey" milestone tracker, a Latest Analysis
preview, and quick links into the rest of the app.
"""

from datetime import datetime
from typing import Callable, List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from PySide6.QtWidgets import QSizePolicy

from gui.assets import apply_card_shadow, apply_cta_glow, icon as make_icon, icon_pixmap
from gui.core import storage
from gui.core.insights import compute_badges
from gui.theme import FOX, ORANGE_TEXT, get_current_theme, icon_color, level_pill_colors, muted_text_color
from gui.widgets.disclaimer import DisclaimerBanner

MILESTONES = [(1, "First Scan"), (5, "5 Scans"), (10, "10 Scans"), (25, "25 Scans")]

CATEGORIES = [
    ("Acne-like Spots", lambda a: a.acne_like_spots),
    ("Redness", lambda a: a.redness),
    ("Skin Texture", lambda a: a.texture),
    ("Dryness Indicators", lambda a: a.dryness_indicators),
]

# (icon, icon color, icon bg, title, body, nav target). Fixed pastel accents
# rather than theme-driven colors -- this dashboard styling targets light
# mode specifically for now.
FEATURES = [
    ("fa5s.camera", "#c2540b", "#fde8da", "Smart Capture",
     "Guided face positioning for accurate results.", "scan"),
    ("fa5s.magic", "#c0397c", "#fbe3ee", "AI Skin Insights",
     "Understand visible skin characteristics.", "about"),
    ("fa5s.user-shield", "#12805c", "#e1f5ea", "Private by Design",
     "Your scans are processed locally and securely.", "privacy"),
    ("fa5s.chart-line", "#5b3fc2", "#eae7fb", "Track Changes",
     "Compare and monitor your skin over time.", "history"),
]

_STAT_ICON_BG = "#fde8da"


def _icon_circle(icon_name: str, fg: str, bg: str, size: int = 44, icon_size: int = 18) -> QFrame:
    circle = QFrame()
    circle.setFixedSize(size, size)
    circle.setStyleSheet(f"background-color: {bg}; border-radius: {size // 2}px; border: none;")
    layout = QVBoxLayout(circle)
    layout.setContentsMargins(0, 0, 0, 0)
    icon_label = QLabel()
    icon_label.setPixmap(icon_pixmap(icon_name, fg, size=icon_size))
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(icon_label)
    return circle


def _milestone_status(total: int) -> str:
    label = MILESTONES[0][1]
    for count, name in MILESTONES:
        if total >= count:
            label = name
    return label


def _journey_progress(total: int) -> tuple[int, int, bool]:
    for count, _ in MILESTONES:
        if total < count:
            return total, count, False
    last = MILESTONES[-1][0]
    return last, last, True


def _link_button(text: str) -> QPushButton:
    btn = QPushButton(f"{text}  →")
    btn.setObjectName("LinkButton")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


class _JourneyStepper(QWidget):
    """Milestone tracker: nodes joined by one continuous line, with the
    reached milestones filled orange (white check / trophy), the next target
    haloed, and the rest greyed -- painted directly so every node and label
    lines up exactly instead of depending on nested-layout metrics."""

    NODE_R = 15
    CENTER_Y = 20

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self._total = total
        self.setFixedHeight(74)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(MILESTONES)
        margin = 38
        span = self.width() - 2 * margin
        xs = [margin + i * span / (n - 1) for i in range(n)]
        cy, r = self.CENTER_Y, self.NODE_R

        achieved_idx = -1
        for i, (count, _) in enumerate(MILESTONES):
            if self._total >= count:
                achieved_idx = i

        for i in range(1, n):
            active = i <= achieved_idx + 1
            pen = QPen(QColor(FOX if active else "#e7e9f0"), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(xs[i - 1] + r, cy), QPointF(xs[i] - r, cy))

        text_color = QColor("#0b1224" if get_current_theme() == "light" else "#e7ecf7")
        label_font = painter.font()
        label_font.setPointSizeF(9)
        label_font.setBold(True)
        painter.setFont(label_font)

        for i, (_, label) in enumerate(MILESTONES):
            x = xs[i]
            is_last = i == n - 1
            achieved = i <= achieved_idx
            target = i == achieved_idx + 1

            if achieved:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(FOX))
                painter.drawEllipse(QPointF(x, cy), r, r)
                glyph, glyph_color = ("fa5s.trophy" if is_last else "fa5s.check"), "white"
            elif target:
                halo = QColor(FOX)
                halo.setAlpha(50)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(halo)
                painter.drawEllipse(QPointF(x, cy), r + 5, r + 5)
                painter.setBrush(QColor(FOX))
                painter.drawEllipse(QPointF(x, cy), r, r)
                painter.setBrush(QColor("white"))
                painter.drawEllipse(QPointF(x, cy), 4.5, 4.5)
                glyph = None
            else:
                painter.setPen(QPen(QColor("#e2e5ee"), 2))
                painter.setBrush(QColor("#f4f5f9"))
                painter.drawEllipse(QPointF(x, cy), r - 1, r - 1)
                glyph, glyph_color = ("fa5s.trophy", "#b8c0d6") if is_last else (None, None)

            if glyph:
                pm = icon_pixmap(glyph, glyph_color, size=13)
                painter.drawPixmap(int(x - pm.width() / pm.devicePixelRatio() / 2),
                                   int(cy - pm.height() / pm.devicePixelRatio() / 2), pm)

            painter.setPen(QColor(ORANGE_TEXT) if target else text_color if achieved else QColor(muted_text_color()))
            painter.drawText(QRectF(x - 44, cy + r + 10, 88, 20), Qt.AlignmentFlag.AlignCenter, label)
        painter.end()


class _HeroVisual(QFrame):
    """The hero card's visual panel: the user's own last saved scan photo
    when there is one (saving images is opt-in and off by default), with a
    translucent scan mesh + viewfinder brackets over it -- otherwise a
    line-art face with the same mesh, drawn in the fox logo's own line-art
    style. Never a stock photo of a real person."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 330)
        self.setStyleSheet("background: transparent; border: none;")
        self._pixmap: Optional[QPixmap] = None

    def set_photo(self, frame_bgr: Optional[np.ndarray]) -> None:
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
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)

        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, 22, 22)
        painter.setClipPath(clip_path)

        if self._pixmap is not None:
            target = rect.size().toSize()
            scaled = self._pixmap.scaled(
                target, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() - (scaled.width() - rect.width()) / 2
            y = rect.y() - (scaled.height() - rect.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
            painter.setClipping(False)
            self._draw_scan_mesh(painter, rect)
            self._draw_viewfinder(painter, rect)
        else:
            self._draw_illustration(painter, rect)
            painter.setClipping(False)
            self._draw_viewfinder(painter, rect)

        painter.restore()
        painter.end()

    @staticmethod
    def _draw_illustration(painter: QPainter, rect: QRectF) -> None:
        """Line-art face + scan mesh on a soft peach wash -- shown until the
        user has a saved scan photo of their own."""
        wash = QRadialGradient(rect.center().x(), rect.top() + rect.height() * 0.42, rect.height() * 0.75)
        wash.setColorAt(0.0, QColor("#fffaf6"))
        wash.setColorAt(1.0, QColor("#ffe2cf"))
        painter.fillRect(rect, wash)

        # Keep the drawing's proportions however tall the panel gets.
        stage_h = min(rect.height(), rect.width() * 1.18)
        w, h = rect.width(), stage_h
        ox, oy = rect.left(), rect.top() + (rect.height() - stage_h) / 2

        def pt(u: float, v: float) -> QPointF:
            return QPointF(ox + u * w, oy + v * h)

        line = QColor(FOX)
        line.setAlpha(210)
        outline_pen = QPen(line, 2.2)
        outline_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(outline_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # head (egg-shaped: fuller at the brow, tapering to the chin), neck, shoulders
        head = QPainterPath()
        head.moveTo(pt(0.50, 0.17))
        head.cubicTo(pt(0.71, 0.17), pt(0.75, 0.40), pt(0.69, 0.55))
        head.cubicTo(pt(0.65, 0.66), pt(0.57, 0.75), pt(0.50, 0.77))
        head.cubicTo(pt(0.43, 0.75), pt(0.35, 0.66), pt(0.31, 0.55))
        head.cubicTo(pt(0.25, 0.40), pt(0.29, 0.17), pt(0.50, 0.17))
        painter.drawPath(head)

        neck = QPainterPath()
        neck.moveTo(pt(0.43, 0.74))
        neck.cubicTo(pt(0.43, 0.82), pt(0.40, 0.85), pt(0.22, 0.92))
        neck.moveTo(pt(0.57, 0.74))
        neck.cubicTo(pt(0.57, 0.82), pt(0.60, 0.85), pt(0.78, 0.92))
        painter.drawPath(neck)

        # eyes, brows, nose, lips
        feature_pen = QPen(line, 1.8)
        feature_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(feature_pen)
        for side in (-1, 1):
            cx = 0.5 + side * 0.09
            painter.drawArc(QRectF(ox + (cx - 0.055) * w, oy + 0.385 * h, 0.11 * w, 0.045 * h), 200 * 16, 140 * 16)
            painter.drawArc(QRectF(ox + (cx - 0.06) * w, oy + 0.33 * h, 0.12 * w, 0.04 * h), 30 * 16 if side < 0 else 110 * 16, 40 * 16)
        painter.drawLine(pt(0.50, 0.43), pt(0.485, 0.53))
        painter.drawArc(QRectF(ox + 0.455 * w, oy + 0.52 * h, 0.09 * w, 0.03 * h), 200 * 16, 140 * 16)
        painter.drawArc(QRectF(ox + 0.44 * w, oy + 0.61 * h, 0.12 * w, 0.045 * h), 200 * 16, 140 * 16)

        # scan mesh: nodes over the face, joined to their near neighbours
        nodes = [
            (0.50, 0.22), (0.41, 0.27), (0.59, 0.27), (0.35, 0.36), (0.65, 0.36), (0.50, 0.33),
            (0.42, 0.44), (0.58, 0.44), (0.36, 0.50), (0.64, 0.50), (0.50, 0.51),
            (0.43, 0.58), (0.57, 0.58), (0.50, 0.66), (0.40, 0.65), (0.60, 0.65), (0.50, 0.73),
        ]
        mesh = QColor(FOX)
        mesh.setAlpha(95)
        painter.setPen(QPen(mesh, 1))
        threshold = 0.155 * min(w, h)
        pts = [pt(u, v) for u, v in nodes]
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if (pts[i] - pts[j]).manhattanLength() < threshold * 1.25:
                    painter.drawLine(pts[i], pts[j])
        painter.setPen(Qt.PenStyle.NoPen)
        for p in pts:
            glow = QColor(FOX)
            glow.setAlpha(60)
            painter.setBrush(glow)
            painter.drawEllipse(p, 6.5, 6.5)
            painter.setBrush(QColor("white"))
            painter.drawEllipse(p, 3.2, 3.2)
            painter.setBrush(QColor(FOX))
            painter.drawEllipse(p, 1.8, 1.8)

    @staticmethod
    def _draw_scan_mesh(painter: QPainter, rect: QRectF) -> None:
        """Decorative triangulated mesh over a real photo -- fixed
        illustrative node positions, not real facial landmarks."""
        mesh_color = QColor(FOX)
        mesh_color.setAlpha(150)
        painter.setPen(QPen(mesh_color, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = rect.center().x(), rect.center().y()
        w, h = rect.width(), rect.height()
        nodes = [
            (cx - w * 0.14, cy - h * 0.22), (cx + w * 0.14, cy - h * 0.22),
            (cx, cy - h * 0.06),
            (cx - w * 0.20, cy + h * 0.02), (cx + w * 0.20, cy + h * 0.02),
            (cx - w * 0.10, cy + h * 0.16), (cx + w * 0.10, cy + h * 0.16),
            (cx, cy + h * 0.26),
        ]
        edges = [(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4), (3, 5), (4, 6), (5, 6), (5, 7), (6, 7)]
        for a, b in edges:
            painter.drawLine(QPointF(*nodes[a]), QPointF(*nodes[b]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(FOX))
        for x, y in nodes:
            painter.drawEllipse(QPointF(x, y), 2.6, 2.6)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    @staticmethod
    def _draw_viewfinder(painter: QPainter, rect: QRectF) -> None:
        bracket = 22.0
        pad = 6.0
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(FOX), 3))
        x0, y0 = rect.left() + pad, rect.top() + pad
        x1, y1 = rect.right() - pad, rect.bottom() - pad
        for sx, sy, dx, dy in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
            painter.drawLine(QPointF(sx, sy), QPointF(sx + dx * bracket, sy))
            painter.drawLine(QPointF(sx, sy), QPointF(sx, sy + dy * bracket))


class _MiniFaceDiagram(QWidget):
    """A small schematic face outline with 4 colored dots for the Latest
    Analysis preview -- illustrative positions, not the real per-scan
    marker coordinates (those live on the full Results page)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(104, 122)
        self._dot_colors: List[str] = []

    def set_levels(self, levels: List[str]) -> None:
        self._dot_colors = [level_pill_colors(level)[1] for level in levels]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(6, 4, self.width() - 12, self.height() - 8)

        outline = QColor(muted_text_color())
        painter.setPen(QPen(outline, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

        cx = rect.center().x()
        painter.setBrush(outline)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx - rect.width() * 0.16, rect.top() + rect.height() * 0.42), 1.6, 1.6)
        painter.drawEllipse(QPointF(cx + rect.width() * 0.16, rect.top() + rect.height() * 0.42), 1.6, 1.6)

        positions = [
            (cx, rect.top() + rect.height() * 0.16),
            (rect.left() + rect.width() * 0.12, rect.top() + rect.height() * 0.55),
            (rect.right() - rect.width() * 0.12, rect.top() + rect.height() * 0.55),
            (cx, rect.bottom() - rect.height() * 0.12),
        ]
        for (x, y), color in zip(positions, self._dot_colors):
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(x, y), 5, 5)
        painter.end()


class HomePage(QWidget):
    def __init__(
        self, on_start_scan, on_view_scan, get_settings: Callable[[], dict],
        on_navigate: Callable[[str], None], parent=None,
    ):
        super().__init__(parent)
        self._on_start_scan = on_start_scan
        self._on_view_scan = on_view_scan
        self._get_settings = get_settings
        self._on_navigate = on_navigate

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(36, 28, 36, 32)
        self._layout.setSpacing(18)

        # --- header: greeting + Start New Scan ---
        header_row = QHBoxLayout()
        greeting_col = QVBoxLayout()
        greeting_col.setSpacing(2)
        self.greeting_label = QLabel()
        self.greeting_label.setObjectName("Heading")
        greeting_col.addWidget(self.greeting_label)
        sub = QLabel("Let's understand your skin today.")
        sub.setObjectName("SubHeading")
        greeting_col.addWidget(sub)
        header_row.addLayout(greeting_col)
        header_row.addStretch()

        start_scan_btn = QPushButton("  Start New Scan")
        start_scan_btn.setIcon(make_icon("fa6s.wand-magic-sparkles", "white"))
        start_scan_btn.setIconSize(QSize(18, 18))
        start_scan_btn.setObjectName("Cta")
        start_scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_scan_btn.setFixedHeight(50)
        start_scan_btn.setMinimumWidth(200)
        apply_cta_glow(start_scan_btn)
        start_scan_btn.clicked.connect(self._on_start_scan)
        header_row.addWidget(start_scan_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(header_row)

        # --- reminder banner (only shown when overdue) ---
        self._reminder_slot = QVBoxLayout()
        self._layout.addLayout(self._reminder_slot)

        # --- stat cards row ---
        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(14)
        self._layout.addLayout(self._stats_row)

        # --- hero (left) + right column ---
        split = QHBoxLayout()
        split.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("HeroGradient")
        hero.setMinimumHeight(430)
        apply_card_shadow(hero, blur=32, y_offset=10, alpha=22)
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(44, 36, 28, 36)
        hero_row.setSpacing(24)

        hero_text_col = QVBoxLayout()
        hero_text_col.setSpacing(14)
        hero_text_col.addStretch()
        heading = QLabel('Understand Your Skin<br>With AI <span style="color:%s;">Vision</span>' % FOX)
        heading.setTextFormat(Qt.TextFormat.RichText)
        heading.setObjectName("Heading")
        heading.setStyleSheet("font-size: 30px; font-weight: 800;")
        hero_text_col.addWidget(heading)
        hero_sub = QLabel("Get visual insights from your facial scan.\nYour analysis stays on your device.")
        hero_sub.setObjectName("SubHeading")
        hero_text_col.addWidget(hero_sub)

        chips_frame = QFrame()
        chips_frame.setObjectName("TrustChips")
        chips_row = QHBoxLayout(chips_frame)
        chips_row.setContentsMargins(16, 12, 16, 12)
        chips_row.setSpacing(18)
        for icon_name, icon_fg, title, body in [
            ("fa5s.lock", "#c2410c", "Private", "Your data stays\non your device"),
            ("fa5s.shield-alt", "#12805c", "Secure", "Processed\nlocally"),
            ("fa6s.wand-magic-sparkles", "#c2410c", "AI Powered", "Advanced visual\nanalysis"),
        ]:
            chip = QHBoxLayout()
            chip.setSpacing(8)
            icon_lbl = QLabel()
            icon_lbl.setPixmap(icon_pixmap(icon_name, icon_fg, size=16))
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
            chip.addWidget(icon_lbl)
            text_col = QVBoxLayout()
            text_col.setSpacing(0)
            t = QLabel(title)
            t.setStyleSheet("font-weight: 800; font-size: 11.5px;")
            text_col.addWidget(t)
            b = QLabel(body)
            b.setObjectName("Muted")
            text_col.addWidget(b)
            chip.addLayout(text_col)
            chips_row.addLayout(chip)
        hero_text_col.addWidget(chips_frame, alignment=Qt.AlignmentFlag.AlignLeft)

        start_ai_btn = QPushButton("  Start AI Skin Scan")
        start_ai_btn.setIcon(make_icon("fa5s.camera", "white"))
        start_ai_btn.setIconSize(QSize(18, 18))
        start_ai_btn.setObjectName("Cta")
        start_ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_ai_btn.setFixedHeight(52)
        start_ai_btn.setMinimumWidth(260)
        apply_cta_glow(start_ai_btn)
        start_ai_btn.clicked.connect(self._on_start_scan)
        hero_text_col.addWidget(start_ai_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        caption_row = QHBoxLayout()
        caption_row.setSpacing(6)
        clock = QLabel()
        clock.setPixmap(icon_pixmap("fa5.clock", muted_text_color(), size=13))
        caption_row.addWidget(clock)
        caption = QLabel("Takes about 30 seconds  •  Camera required")
        caption.setObjectName("Muted")
        caption_row.addWidget(caption)
        caption_row.addStretch()
        hero_text_col.addLayout(caption_row)
        hero_text_col.addStretch()

        hero_row.addLayout(hero_text_col, stretch=3)
        self.hero_visual = _HeroVisual()
        hero_row.addWidget(self.hero_visual, stretch=2)

        split.addWidget(hero, stretch=2)

        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        self.journey_card = QFrame()
        self.journey_card.setObjectName("Card")
        apply_card_shadow(self.journey_card)
        self._journey_layout = QVBoxLayout(self.journey_card)
        right_col.addWidget(self.journey_card)

        self.latest_card = QFrame()
        self.latest_card.setObjectName("Card")
        apply_card_shadow(self.latest_card)
        self._latest_layout = QVBoxLayout(self.latest_card)
        right_col.addWidget(self.latest_card, stretch=1)

        split.addLayout(right_col, stretch=1)
        self._layout.addLayout(split)

        # --- bottom quick-link feature cards ---
        features_grid = QGridLayout()
        features_grid.setSpacing(14)
        for i, (icon_name, fg, bg, title, body, target) in enumerate(FEATURES):
            card = QFrame()
            card.setObjectName("Card")
            apply_card_shadow(card, blur=18, y_offset=4, alpha=20)
            h = QHBoxLayout(card)
            h.setContentsMargins(20, 18, 18, 18)
            h.setSpacing(16)
            h.addWidget(_icon_circle(icon_name, fg, bg, size=58, icon_size=24), alignment=Qt.AlignmentFlag.AlignTop)
            v = QVBoxLayout()
            v.setSpacing(3)
            t = QLabel(title)
            t.setObjectName("CardTitle")
            v.addWidget(t)
            b = QLabel(body)
            b.setObjectName("SubHeading")
            b.setWordWrap(True)
            v.addWidget(b)
            v.addSpacing(2)
            link = _link_button("Learn more")
            link.clicked.connect(lambda _, k=target: self._on_navigate(k))
            v.addWidget(link, alignment=Qt.AlignmentFlag.AlignLeft)
            v.addStretch()
            h.addLayout(v, stretch=1)
            features_grid.addWidget(card, 0, i)
        self._layout.addLayout(features_grid)

        self._achievements_slot = QVBoxLayout()
        self._layout.addLayout(self._achievements_slot)

        self._layout.addWidget(DisclaimerBanner())
        self._layout.addStretch(1)

        self.refresh()

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        self.greeting_label.setText(f"{greeting}, Fox! \U0001F44B")

        self._clear_layout(self._reminder_slot)
        reminder_days = self._get_settings().get("reminder_days", 0)
        days_since = storage.days_since_last_scan()
        if reminder_days and days_since is not None and days_since >= reminder_days:
            self._reminder_slot.addWidget(self._build_reminder_banner(days_since))

        records = storage.list_scans()
        total = len(records)
        latest = records[0] if records else None

        self._clear_layout(self._stats_row, is_hbox=True)
        last_scan_text = (
            datetime.fromisoformat(latest.timestamp).strftime("%b %d, %Y") if latest else "—"
        )
        for icon_name, title, sub_label in [
            ("fa5s.expand", f"{total:02d}", "Total Scans"),
            ("fa5.calendar-alt", last_scan_text, "Last Scan"),
            ("fa5.star", _milestone_status(total), "Current Status"),
        ]:
            self._stats_row.addWidget(self._build_stat_card(icon_name, title, sub_label))

        photo = None
        photo_record = next((r for r in records if r.image_path), None)
        if photo_record:
            photo = cv2.imread(photo_record.image_path)
        self.hero_visual.set_photo(photo)

        self._clear_layout(self._journey_layout)
        self._build_journey(total)

        self._clear_layout(self._latest_layout)
        self._build_latest_analysis(latest)

        self._clear_layout(self._achievements_slot)
        badges = compute_badges(records)
        earned = [b for b in badges if b.earned]
        if earned:
            self._achievements_slot.addWidget(self._build_badges_card(earned, badges))

    @staticmethod
    def _clear_layout(layout, is_hbox: bool = False) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout():
                HomePage._clear_layout(item.layout())

    def _build_stat_card(self, icon_name: str, value: str, label: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        apply_card_shadow(card, blur=18, y_offset=4, alpha=20)
        row = QHBoxLayout(card)
        row.setContentsMargins(22, 18, 22, 18)
        row.setSpacing(16)
        row.addWidget(_icon_circle(icon_name, FOX, _STAT_ICON_BG, size=54, icon_size=22))
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        value_label = QLabel(value)
        value_label.setObjectName("CardTitle")
        value_label.setStyleSheet("font-size: 21px; font-weight: 800;")
        text_col.addWidget(value_label)
        sub_label = QLabel(label)
        sub_label.setObjectName("SubHeading")
        text_col.addWidget(sub_label)
        row.addLayout(text_col, stretch=1)
        return card

    def _build_journey(self, total: int) -> None:
        self._journey_layout.setContentsMargins(22, 20, 22, 20)
        self._journey_layout.setSpacing(0)

        header = QHBoxLayout()
        title = QLabel("Your Skin Journey")
        title.setObjectName("CardTitle")
        title.setStyleSheet("font-size: 15px;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(_icon_circle("fa5s.crown", FOX, _STAT_ICON_BG, size=32, icon_size=14))
        self._journey_layout.addLayout(header)

        self._journey_layout.addSpacing(14)
        self._journey_layout.addWidget(_JourneyStepper(total))
        self._journey_layout.addSpacing(6)

        current, target, maxed = _journey_progress(total)
        bar = QProgressBar()
        bar.setObjectName("JourneyBar")
        bar.setRange(0, target)
        bar.setValue(current)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        self._journey_layout.addWidget(bar)
        self._journey_layout.addSpacing(10)

        fraction = QLabel(
            f'<span style="color:{ORANGE_TEXT}; font-weight:800;">{current} / {target}</span> scans completed'
        )
        fraction.setTextFormat(Qt.TextFormat.RichText)
        fraction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fraction.setStyleSheet("font-size: 12px;")
        self._journey_layout.addWidget(fraction)
        self._journey_layout.addSpacing(4)

        note = QLabel(
            "You've unlocked every milestone so far!" if maxed
            else "Keep scanning to track changes\nand unlock new insights."
        )
        note.setObjectName("Muted")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._journey_layout.addWidget(note)

    def _build_latest_analysis(self, latest) -> None:
        self._latest_layout.setContentsMargins(22, 20, 22, 20)
        self._latest_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Latest Analysis")
        title.setObjectName("CardTitle")
        title.setStyleSheet("font-size: 15px;")
        header.addWidget(title)
        header.addStretch()
        if latest:
            view_link = _link_button("View Details")
            view_link.clicked.connect(lambda: self._on_view_scan(latest.id))
            header.addWidget(view_link)
        self._latest_layout.addLayout(header)

        if not latest:
            empty = QLabel("No scans yet — start your first scan to see insights here.")
            empty.setObjectName("SubHeading")
            empty.setWordWrap(True)
            self._latest_layout.addWidget(empty)
            self._latest_layout.addStretch()
            return

        when_row = QHBoxLayout()
        when_row.setSpacing(6)
        cal = QLabel()
        cal.setPixmap(icon_pixmap("fa5.calendar-alt", muted_text_color(), size=12))
        when_row.addWidget(cal)
        when = QLabel(datetime.fromisoformat(latest.timestamp).strftime("%b %d, %Y  ·  %I:%M %p"))
        when.setObjectName("Muted")
        when_row.addWidget(when)
        when_row.addStretch()
        self._latest_layout.addLayout(when_row)
        self._latest_layout.addSpacing(4)

        body_row = QHBoxLayout()
        body_row.setSpacing(16)
        diagram = _MiniFaceDiagram()
        levels = [getter(latest.analysis).level for _, getter in CATEGORIES]
        diagram.set_levels(levels)
        body_row.addWidget(diagram, alignment=Qt.AlignmentFlag.AlignTop)

        list_col = QVBoxLayout()
        list_col.setSpacing(9)
        for (label, _getter), level in zip(CATEGORIES, levels):
            row = QHBoxLayout()
            row.setSpacing(8)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {level_pill_colors(level)[1]}; font-size: 9px;")
            row.addWidget(dot)
            name = QLabel(label)
            row.addWidget(name, stretch=1)
            value = QLabel(level.title())
            value.setStyleSheet(f"color: {level_pill_colors(level)[1]}; font-weight: 800; font-size: 12px;")
            row.addWidget(value)
            list_col.addLayout(row)
        list_col.addStretch()
        body_row.addLayout(list_col, stretch=1)
        self._latest_layout.addLayout(body_row)

        self._latest_layout.addSpacing(6)
        view_btn = QPushButton("View Full Analysis")
        view_btn.setObjectName("SoftButton")
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.clicked.connect(lambda: self._on_view_scan(latest.id))
        self._latest_layout.addWidget(view_btn)
        self._latest_layout.addStretch()

    def _build_badges_card(self, earned: list, all_badges: list) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        apply_card_shadow(card, blur=18, y_offset=4, alpha=22)
        v = QVBoxLayout(card)

        title = QLabel("Achievements")
        title.setObjectName("CardTitle")
        v.addWidget(title)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        for badge in earned:
            chip = QFrame()
            chip.setObjectName("TrustChips")
            chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            chip_row = QHBoxLayout(chip)
            chip_row.setContentsMargins(12, 7, 14, 7)
            chip_row.setSpacing(8)
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap(badge.icon, ORANGE_TEXT, size=13))
            chip_row.addWidget(icon_label)
            text = QLabel(badge.label)
            text.setStyleSheet("font-size: 11.5px; font-weight: 700;")
            chip_row.addWidget(text)
            chips.addWidget(chip)
        chips.addStretch()
        v.addLayout(chips)

        next_badge = next((b for b in all_badges if not b.earned), None)
        if next_badge:
            next_label = QLabel(f"Next up: {next_badge.label}")
            next_label.setObjectName("Muted")
            v.addWidget(next_label)

        return card

    def _build_reminder_banner(self, days_since: int) -> QFrame:
        banner = QFrame()
        banner.setObjectName("Disclaimer")
        apply_card_shadow(banner, blur=18, y_offset=4, alpha=20)
        row = QHBoxLayout(banner)
        row.setContentsMargins(16, 12, 16, 12)

        icon_label = QLabel()
        icon_label.setPixmap(icon_pixmap("fa5s.bell", icon_color("warning"), size=16))
        row.addWidget(icon_label)

        text = QLabel(f"It's been {days_since} days since your last scan — time for a check-in?")
        text.setWordWrap(True)
        row.addWidget(text, stretch=1)

        scan_btn = QPushButton("Scan Now")
        scan_btn.setObjectName("Secondary")
        scan_btn.clicked.connect(self._on_start_scan)
        row.addWidget(scan_btn)

        return banner
