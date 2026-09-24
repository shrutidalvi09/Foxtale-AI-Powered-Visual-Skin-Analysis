"""Dashboard-style Home page: greeting header, at-a-glance stats, a hero
scan-CTA card, a "Skin Journey" milestone tracker, a Latest Analysis
preview, and quick links into the rest of the app.
"""

from datetime import datetime
from typing import Callable, List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow, icon as make_icon, icon_pixmap, logo_mark_pixmap
from gui.core import storage
from gui.core.insights import compute_badges
from gui.theme import FOX, icon_color, level_pill_colors, muted_text_color
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


class _HeroVisual(QFrame):
    """The hero card's photo panel: the user's own last saved scan photo
    (saving images is opt-in and off by default, so this is often empty)
    with a translucent triangulated "scan mesh" + viewfinder brackets drawn
    on top -- the same scanning motif as the live camera view, applied here
    as static decoration. Falls back to the fox mark when no photo exists;
    never a stock photo of a real person."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 300)
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
            # No saved scan photo yet (saving images is opt-in and off by
            # default) -- a clean, static fox mark rather than a mesh
            # overlay with nothing underneath it to justify one.
            painter.fillRect(rect, QColor(255, 243, 234))
            mark = logo_mark_pixmap(int(rect.height() * 0.34))
            mx = rect.x() + (rect.width() - mark.width()) / 2
            my = rect.y() + (rect.height() - mark.height()) / 2
            painter.drawPixmap(int(mx), int(my), mark)

        painter.restore()
        painter.end()

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
        self.setFixedSize(92, 108)
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

        start_scan_btn = QPushButton(" Start New Scan")
        start_scan_btn.setIcon(make_icon("fa5s.magic", icon_color("on_primary")))
        start_scan_btn.setObjectName("Primary")
        start_scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_scan_btn.clicked.connect(self._on_start_scan)
        header_row.addWidget(start_scan_btn)
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
        apply_card_shadow(hero, blur=32, y_offset=10, alpha=22)
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(40, 36, 32, 36)
        hero_row.setSpacing(28)

        hero_text_col = QVBoxLayout()
        hero_text_col.setSpacing(12)
        heading = QLabel('Understand Your Skin\nWith AI <span style="color:%s;">Vision</span>' % FOX)
        heading.setTextFormat(Qt.TextFormat.RichText)
        heading.setObjectName("Heading")
        heading.setStyleSheet("font-size: 27px;")
        hero_text_col.addWidget(heading)
        hero_sub = QLabel("Get visual insights from your facial scan.\nYour analysis stays on your device.")
        hero_sub.setObjectName("SubHeading")
        hero_text_col.addWidget(hero_sub)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(18)
        for icon_name, title, body in [
            ("fa5s.lock", "Private", "Your data stays\non your device"),
            ("fa5s.shield-alt", "Secure", "End-to-end\nprotection"),
            ("fa5s.magic", "AI Powered", "Advanced visual\nanalysis"),
        ]:
            chip = QHBoxLayout()
            chip.setSpacing(8)
            icon_lbl = QLabel()
            icon_lbl.setPixmap(icon_pixmap(icon_name, icon_color("primary"), size=14))
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
            chip.addWidget(icon_lbl)
            text_col = QVBoxLayout()
            text_col.setSpacing(0)
            t = QLabel(title)
            t.setStyleSheet("font-weight: 700; font-size: 11.5px;")
            text_col.addWidget(t)
            b = QLabel(body)
            b.setObjectName("Muted")
            text_col.addWidget(b)
            chip.addLayout(text_col)
            chips_row.addLayout(chip)
        chips_row.addStretch()
        hero_text_col.addLayout(chips_row)

        start_ai_btn = QPushButton(" Start AI Skin Scan")
        start_ai_btn.setIcon(make_icon("fa5s.camera", icon_color("on_primary")))
        start_ai_btn.setObjectName("Primary")
        start_ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_ai_btn.setMinimumHeight(42)
        start_ai_btn.clicked.connect(self._on_start_scan)
        hero_text_col.addWidget(start_ai_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        caption = QLabel()
        caption.setObjectName("Muted")
        caption.setTextFormat(Qt.TextFormat.RichText)
        caption.setText(
            '<span>\U0001F551 Takes about 30 seconds &nbsp;•&nbsp; Camera required</span>'
        )
        hero_text_col.addWidget(caption)
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
            v = QVBoxLayout(card)
            v.addWidget(_icon_circle(icon_name, fg, bg))
            t = QLabel(title)
            t.setObjectName("CardTitle")
            v.addWidget(t)
            b = QLabel(body)
            b.setObjectName("Muted")
            b.setWordWrap(True)
            v.addWidget(b)
            link = _link_button("Learn more")
            link.clicked.connect(lambda _, k=target: self._on_navigate(k))
            v.addWidget(link, alignment=Qt.AlignmentFlag.AlignLeft)
            features_grid.addWidget(card, 0, i)
        self._layout.addLayout(features_grid)

        self._achievements_slot = QVBoxLayout()
        self._layout.addLayout(self._achievements_slot)

        self._layout.addWidget(DisclaimerBanner())

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
            ("fa5s.crop-alt", f"{total:02d}", "Total Scans"),
            ("fa5s.calendar-alt", last_scan_text, "Last Scan"),
            ("fa5s.star", _milestone_status(total), "Current Status"),
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
        row.setContentsMargins(18, 16, 18, 16)
        row.addWidget(_icon_circle(icon_name, FOX, _STAT_ICON_BG))
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        value_label = QLabel(value)
        value_label.setObjectName("CardTitle")
        value_label.setStyleSheet("font-size: 16px;")
        text_col.addWidget(value_label)
        sub_label = QLabel(label)
        sub_label.setObjectName("Muted")
        text_col.addWidget(sub_label)
        row.addLayout(text_col, stretch=1)
        return card

    def _build_journey(self, total: int) -> None:
        header = QHBoxLayout()
        title = QLabel("Your Skin Journey")
        title.setObjectName("CardTitle")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(_icon_circle("fa5s.crown", FOX, _STAT_ICON_BG, size=30, icon_size=13))
        self._journey_layout.addLayout(header)

        self._journey_layout.addSpacing(10)
        self._journey_layout.addWidget(self._build_stepper(total))
        self._journey_layout.addSpacing(10)

        current, target, maxed = _journey_progress(total)
        bar = QProgressBar()
        bar.setRange(0, target)
        bar.setValue(current)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        self._journey_layout.addWidget(bar)

        fraction = QLabel(f"{current} / {target} scans completed")
        fraction.setStyleSheet(f"color: {FOX}; font-weight: 700; font-size: 11.5px;")
        self._journey_layout.addWidget(fraction)

        note = QLabel(
            "You've unlocked every milestone so far!" if maxed
            else "Keep scanning to track changes and unlock new insights."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        self._journey_layout.addWidget(note)

    def _build_stepper(self, total: int) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        achieved_idx = -1
        for i, (count, _) in enumerate(MILESTONES):
            if total >= count:
                achieved_idx = i

        for i, (count, label) in enumerate(MILESTONES):
            if i > 0:
                line = QFrame()
                line.setFixedHeight(2)
                line.setStyleSheet(
                    f"background-color: {FOX if i <= achieved_idx else '#e7e9f0'}; border: none;"
                )
                row.addWidget(line, stretch=1)

            is_last = i == len(MILESTONES) - 1
            is_achieved = i <= achieved_idx
            is_next_target = i == achieved_idx + 1

            circle = QFrame()
            icon_lbl = QLabel()
            if is_achieved and not is_last:
                circle.setFixedSize(30, 30)
                circle.setStyleSheet(f"background-color: {FOX}; border-radius: 15px; border: none;")
                icon_lbl.setPixmap(icon_pixmap("fa5s.check", "white", size=12))
            elif is_next_target and not is_last:
                circle.setFixedSize(34, 34)
                circle.setStyleSheet(f"background-color: {FOX}; border-radius: 17px; border: none;")
            else:
                circle.setFixedSize(30, 30)
                circle.setStyleSheet("background-color: #f2f3f7; border-radius: 15px; border: 2px solid #e7e9f0;")
                if is_last:
                    icon_lbl.setPixmap(
                        icon_pixmap("fa5s.trophy", FOX if is_achieved else "#b8c0d6", size=12)
                    )
            circle_layout = QVBoxLayout(circle)
            circle_layout.setContentsMargins(0, 0, 0, 0)
            circle_layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

            node_col = QVBoxLayout()
            node_col.setSpacing(6)
            circle_wrap = QHBoxLayout()
            circle_wrap.addStretch()
            circle_wrap.addWidget(circle)
            circle_wrap.addStretch()
            node_col.addLayout(circle_wrap)

            text = QLabel(label)
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {FOX if is_achieved else muted_text_color()};"
            )
            node_col.addWidget(text)

            row.addLayout(node_col)

        return container

    def _build_latest_analysis(self, latest) -> None:
        header = QHBoxLayout()
        title = QLabel("Latest Analysis")
        title.setObjectName("CardTitle")
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
            return

        when = QLabel(datetime.fromisoformat(latest.timestamp).strftime("%b %d, %Y · %I:%M %p"))
        when.setObjectName("Muted")
        self._latest_layout.addWidget(when)

        body_row = QHBoxLayout()
        diagram = _MiniFaceDiagram()
        levels = [getter(latest.analysis).level for _, getter in CATEGORIES]
        diagram.set_levels(levels)
        body_row.addWidget(diagram)

        list_col = QVBoxLayout()
        list_col.setSpacing(6)
        for (label, getter), level in zip(CATEGORIES, levels):
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {level_pill_colors(level)[1]};")
            row.addWidget(dot)
            name = QLabel(label)
            row.addWidget(name, stretch=1)
            value = QLabel(level.title())
            value.setStyleSheet(f"color: {level_pill_colors(level)[1]}; font-weight: 700; font-size: 11.5px;")
            row.addWidget(value)
            list_col.addLayout(row)
        body_row.addLayout(list_col, stretch=1)
        self._latest_layout.addLayout(body_row)

        view_btn = QPushButton("View Full Analysis")
        view_btn.setObjectName("Secondary")
        view_btn.clicked.connect(lambda: self._on_view_scan(latest.id))
        self._latest_layout.addWidget(view_btn)

    def _build_badges_card(self, earned: list, all_badges: list) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        apply_card_shadow(card, blur=18, y_offset=4, alpha=22)
        v = QVBoxLayout(card)

        title = QLabel("Achievements")
        title.setObjectName("CardTitle")
        v.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)
        columns = 5
        for i, badge in enumerate(earned):
            chip = QFrame()
            chip.setObjectName("Card")
            chip_row = QHBoxLayout(chip)
            chip_row.setContentsMargins(10, 6, 10, 6)
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap(badge.icon, icon_color("accent"), size=13))
            chip_row.addWidget(icon_label)
            text = QLabel(badge.label)
            text.setStyleSheet("font-size: 11px; font-weight: 700;")
            chip_row.addWidget(text)
            grid.addWidget(chip, i // columns, i % columns)
        v.addLayout(grid)

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
