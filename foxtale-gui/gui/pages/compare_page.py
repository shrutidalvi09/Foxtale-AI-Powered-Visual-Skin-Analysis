"""Compare page: pick two saved scans and see how each category and each
facial region changed (region levels are derived from how many visible
observations fell in that region), plus a before/after photo view -- an
interactive slider when both scans have a saved photo."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from engine.schemas import LEVEL_SCORE
from gui.assets import apply_card_shadow, apply_cta_glow, icon as make_icon, icon_circle, icon_pixmap
from gui.core import storage
from gui.theme import FOX, ORANGE_TEXT, delta_color, get_current_theme, muted_text_color, pill_stylesheet
from gui.widgets.before_after_slider import BeforeAfterSlider

STANDARD_REGIONS = ["FOREHEAD", "LEFT CHEEK", "RIGHT CHEEK", "NOSE", "CHIN"]

CATEGORIES = [
    ("Acne-like Spots", lambda a: a.acne_like_spots),
    ("Visible Redness", lambda a: a.redness),
    ("Skin Texture", lambda a: a.texture),
    ("Dryness Indicators", lambda a: a.dryness_indicators),
]

# (icon, icon color, label) for the "How comparison works" chips.
COMPARED_ASPECTS = [
    ("fa5.dot-circle", "#e2601a", "Spots"),
    ("fa5s.heartbeat", "#d6336c", "Redness"),
    ("fa5s.border-all", "#7c4dcc", "Texture"),
    ("fa5s.tint", "#3b6fe0", "Dryness"),
]

# Change direction -> (dot color, light text, dark text)
CHANGE_STYLES = {
    "increase": ("#f97316", "#c2410c", "#fdba74"),
    "same": ("#9aa3b8", "#6b7280", "#8993a8"),
    "decrease": ("#10b981", "#047857", "#10b981"),
}


def _region_level(record, region_label: str) -> str:
    """An approximate per-region severity derived from how many visible
    observations were flagged there -- not a re-run of the analysis engine,
    just a count-based read of data already stored with the scan."""
    count = sum(1 for r in record.regions if r.region == region_label)
    return {0: "minimal", 1: "mild", 2: "moderate"}.get(count, "noticeable")


def _change(a_level: str, b_level: str) -> Tuple[str, str, str]:
    """(label, dot color, text color) for going from level a to level b."""
    da, db = LEVEL_SCORE[a_level], LEVEL_SCORE[b_level]
    key = "increase" if db > da else "decrease" if db < da else "same"
    label = {"increase": "Increase", "decrease": "Decrease", "same": "No change"}[key]
    dot, light_text, dark_text = CHANGE_STYLES[key]
    return label, dot, light_text if get_current_theme() == "light" else dark_text


def _scan_label(record) -> str:
    return datetime.fromisoformat(record.timestamp).strftime("%b %d, %Y  ·  %I:%M %p")


def _photo_pixmap(image_bgr: np.ndarray, max_w: int = 440, max_h: int = 250) -> QPixmap:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
    scaled = QPixmap.fromImage(qimg).scaled(
        max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    rounded = QPixmap(scaled.size())
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, scaled.width(), scaled.height(), 14, 14)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return rounded


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


def _card() -> Tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    apply_card_shadow(frame, blur=20, y_offset=5, alpha=18)
    v = QVBoxLayout(frame)
    v.setContentsMargins(24, 20, 24, 22)
    v.setSpacing(14)
    return frame, v


def _section_header(icon_name: str, title: str, subtitle: str) -> Tuple[QHBoxLayout, QVBoxLayout]:
    row = QHBoxLayout()
    row.setSpacing(14)
    row.addWidget(icon_circle(icon_name, FOX, "#fde8da" if get_current_theme() == "light" else "#3a2818",
                              size=36, icon_size=15), alignment=Qt.AlignmentFlag.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(3)
    t = QLabel(title)
    t.setObjectName("CardTitle")
    t.setStyleSheet("font-size: 15px;")
    col.addWidget(t)
    s = QLabel(subtitle)
    s.setObjectName("SubHeading")
    s.setStyleSheet("font-size: 12px;")
    s.setWordWrap(True)
    col.addWidget(s)
    row.addLayout(col, stretch=1)
    return row, col


class _PhotoSlot(QFrame):
    """One side of the before/after view: a photo when the scan has one,
    otherwise a friendly placeholder with a "Select Scan" button."""

    select_clicked = Signal()

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self._role = role
        self.setObjectName("Card")
        self.setMinimumHeight(250)
        light = get_current_theme() == "light"
        if role == "before":
            self._fg, self._circle_bg = FOX, "#fde8da" if light else "#3a2818"
            self._badge_style = f"background-color: {'#fff1e7' if light else '#2a1d10'}; color: {ORANGE_TEXT if light else '#ff8a4c'};"
            self._button_color = "#e54a00" if light else "#ff8a4c"
        else:
            self._fg, self._circle_bg = "#12a06a", "#d9f3e6" if light else "#1b3d2e"
            self._badge_style = f"background-color: {'#e1f5ea' if light else '#12281f'}; color: {'#0f7a55' if light else '#6ee7b7'};"
            self._button_color = "#12a06a" if light else "#6ee7b7"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(6)
        badge = QLabel("Before" if role == "before" else "After")
        badge.setFixedHeight(24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"{self._badge_style} border-radius: 12px; padding: 0 12px; font-size: 11px; font-weight: 800;")
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        outer.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)

        self._body = QVBoxLayout()
        self._body.setSpacing(6)
        outer.addLayout(self._body, stretch=1)
        self.show_placeholder("No photo selected", "Select a scan with a saved photo")

    def show_placeholder(self, title: str, body: str) -> None:
        _clear(self._body)
        self._body.addStretch()
        self._body.addWidget(
            icon_circle("fa5.image", self._fg, self._circle_bg, size=62, icon_size=26),
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        self._body.addSpacing(6)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("font-size: 14px; font-weight: 800;")
        self._body.addWidget(t)
        b = QLabel(body)
        b.setObjectName("SubHeading")
        b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b.setStyleSheet("font-size: 12px;")
        self._body.addWidget(b)
        self._body.addSpacing(6)

        btn = QPushButton("  Select Scan")
        btn.setIcon(make_icon("fa5.calendar-alt", self._button_color))
        btn.setIconSize(QSize(14, 14))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(38)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {self._button_color}; "
            f"border: 1.5px solid {self._button_color}; border-radius: 18px; padding: 0 18px; "
            "font-weight: 700; font-size: 12px; }}"
            "QPushButton:hover { background-color: rgba(128,128,128,0.10); }"
        )
        btn.clicked.connect(self.select_clicked)
        self._body.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._body.addStretch()

    def show_photo(self, image_bgr: np.ndarray, caption: str) -> None:
        _clear(self._body)
        photo = QLabel()
        photo.setPixmap(_photo_pixmap(image_bgr))
        photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.addWidget(photo, stretch=1)
        cap = QLabel(caption)
        cap.setObjectName("Muted")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.addWidget(cap)


class ComparePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: List = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        self._build_header(layout)
        self._build_pickers(layout)
        self._build_status_banner(layout)

        self.category_card, category_v = _card()
        head, _ = _section_header(
            "fa5s.chart-bar", "Category Comparison", "How each visible category changed between the two scans.",
        )
        category_v.addLayout(head)
        self.category_body = QVBoxLayout()
        category_v.addLayout(self.category_body)
        layout.addWidget(self.category_card)

        self._build_region_card(layout)
        layout.addStretch(1)

        self.combo_a.currentIndexChanged.connect(self._render)
        self.combo_b.currentIndexChanged.connect(self._render)
        self.refresh()

    # ------------------------------------------------------------- layout

    def _build_header(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(16)
        title_col = QVBoxLayout()
        title_col.setSpacing(5)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap("fa5s.exchange-alt", FOX, size=24))
        title_row.addWidget(icon_lbl)
        heading = QLabel("Compare Scans")
        heading.setObjectName("Heading")
        title_row.addWidget(heading)
        title_row.addStretch()
        title_col.addLayout(title_row)
        sub = QLabel("Compare your skin scans to track changes and progress over time.")
        sub.setObjectName("SubHeading")
        sub.setWordWrap(True)
        title_col.addWidget(sub)
        row.addLayout(title_col, stretch=1)

        pill = QFrame()
        pill.setObjectName("TipPill")
        pill.setMinimumHeight(42)
        pill_row = QHBoxLayout(pill)
        pill_row.setContentsMargins(16, 9, 18, 9)
        pill_row.setSpacing(10)
        bulb = QLabel()
        bulb.setPixmap(icon_pixmap("fa5.lightbulb", FOX, size=15))
        pill_row.addWidget(bulb)
        tip = QLabel("Tip: Select any two saved scans to see a detailed comparison.")
        pill_row.addWidget(tip)
        row.addWidget(pill, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(row)

    def _make_combo(self, placeholder: str) -> QComboBox:
        combo = QComboBox()
        combo.setFixedHeight(52)
        combo.setMinimumWidth(190)
        combo.setPlaceholderText(placeholder)
        combo.setIconSize(QSize(16, 16))
        return combo

    def _build_pickers(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(14)
        self.combo_a = self._make_combo("Select start scan")
        self.combo_b = self._make_combo("Select end scan")
        for text, combo in (("From", self.combo_a), ("To", self.combo_b)):
            label = QLabel(text)
            label.setStyleSheet("font-weight: 600;")
            row.addWidget(label)
            row.addWidget(combo, stretch=1)

        refresh_btn = QPushButton("  Refresh")
        refresh_btn.setIcon(make_icon("fa5s.sync-alt", "white"))
        refresh_btn.setIconSize(QSize(16, 16))
        refresh_btn.setObjectName("Cta")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setFixedHeight(52)
        apply_cta_glow(refresh_btn)
        refresh_btn.clicked.connect(self.refresh)
        row.addWidget(refresh_btn)
        layout.addLayout(row)

    def _build_status_banner(self, layout: QVBoxLayout) -> None:
        self.status_banner = QFrame()
        self.status_banner.setObjectName("Disclaimer")
        row = QHBoxLayout(self.status_banner)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(14)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap("mdi6.information-outline", FOX, size=22))
        row.addWidget(icon_lbl)
        self.status_label = QLabel("Need at least two saved scans to compare.")
        row.addWidget(self.status_label, stretch=1)
        layout.addWidget(self.status_banner)

    def _build_region_card(self, layout: QVBoxLayout) -> None:
        card, v = _card()
        v.setSpacing(16)

        head, _ = _section_header(
            "fa5s.th-large", "Facial Region Comparison",
            "Approximate — based on how many visible observations were flagged in each region, "
            "not a separate analysis pass.",
        )
        legend = QHBoxLayout()
        legend.setSpacing(18)
        for key, text in (("increase", "Increase"), ("same", "No change"), ("decrease", "Decrease")):
            dot = QLabel()
            dot.setFixedSize(9, 9)
            dot.setStyleSheet(f"background-color: {CHANGE_STYLES[key][0]}; border-radius: 4px;")
            legend.addWidget(dot)
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 12px;")
            legend.addWidget(lbl)
        head.addLayout(legend)
        v.addLayout(head)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        v.addWidget(divider)

        self.region_body = QVBoxLayout()
        v.addLayout(self.region_body)

        title = QLabel("Before / After Photo")
        title.setObjectName("CardTitle")
        title.setStyleSheet("font-size: 15px;")
        v.addWidget(title)
        self.photo_hint = QLabel("Both scans need a saved photo to compare visually.")
        self.photo_hint.setObjectName("SubHeading")
        self.photo_hint.setStyleSheet("font-size: 12px;")
        v.addWidget(self.photo_hint)

        self.slots_widget = QWidget()
        self.slots_widget.setStyleSheet("background: transparent;")
        slots_row = QHBoxLayout(self.slots_widget)
        slots_row.setContentsMargins(0, 0, 0, 0)
        slots_row.setSpacing(16)
        self.slot_before = _PhotoSlot("before")
        self.slot_after = _PhotoSlot("after")
        self.slot_before.select_clicked.connect(lambda: self.combo_a.showPopup())
        self.slot_after.select_clicked.connect(lambda: self.combo_b.showPopup())
        vs = QLabel("VS")
        vs.setFixedSize(46, 46)
        vs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        border = "#e2e5ee" if get_current_theme() == "light" else "#263457"
        vs.setStyleSheet(f"border: 1.5px solid {border}; border-radius: 23px; font-weight: 800; font-size: 12px;")
        slots_row.addWidget(self.slot_before, stretch=1)
        slots_row.addWidget(vs, alignment=Qt.AlignmentFlag.AlignVCenter)
        slots_row.addWidget(self.slot_after, stretch=1)
        v.addWidget(self.slots_widget)

        self.slider_card = QFrame()
        self.slider_card.setObjectName("Card")
        slider_v = QVBoxLayout(self.slider_card)
        slider_v.setContentsMargins(12, 12, 12, 12)
        self.slider = BeforeAfterSlider()
        slider_v.addWidget(self.slider)
        self.slider_card.setVisible(False)
        v.addWidget(self.slider_card)

        v.addWidget(self._how_it_works_box())
        v.addWidget(self._privacy_banner())
        layout.addWidget(card)

    def _how_it_works_box(self) -> QFrame:
        light = get_current_theme() == "light"
        box = QFrame()
        box.setObjectName("InfoTintLavender")
        bg, border = ("#f6f2fe", "#e6dcfa") if light else ("#241c3a", "#33285a")
        box.setStyleSheet(
            f"QFrame#InfoTintLavender {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
        )
        row = QHBoxLayout(box)
        row.setContentsMargins(20, 18, 20, 18)
        row.setSpacing(16)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap("fa6s.wand-magic-sparkles", "#7c4dcc" if light else "#b79bf0", size=24))
        row.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(5)
        title = QLabel("How comparison works")
        title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {'#3b1d7a' if light else '#d9c9ff'};")
        col.addWidget(title)
        body = QLabel(
            "We compare the visible skin observations stored with each scan, by category and by facial "
            "region, and show how they changed between the two scans you picked."
        )
        body.setWordWrap(True)
        body.setStyleSheet("font-size: 12px;")
        col.addWidget(body)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        for icon_name, color, text in COMPARED_ASPECTS:
            chip = QFrame()
            chip.setObjectName("AspectChip")
            chip_bg, chip_border = ("white", "#ece6fa") if light else ("#131b30", "#33285a")
            chip.setStyleSheet(
                f"QFrame#AspectChip {{ background-color: {chip_bg}; border: 1px solid {chip_border}; border-radius: 12px; }}"
            )
            chip_row = QHBoxLayout(chip)
            chip_row.setContentsMargins(12, 8, 14, 8)
            chip_row.setSpacing(8)
            chip_icon = QLabel()
            chip_icon.setPixmap(icon_pixmap(icon_name, color, size=14))
            chip_row.addWidget(chip_icon)
            chip_label = QLabel(text)
            chip_label.setStyleSheet("font-size: 12px; font-weight: 600;")
            chip_row.addWidget(chip_label)
            chips.addWidget(chip)
        chips.addStretch()
        col.addSpacing(4)
        col.addLayout(chips)
        row.addLayout(col, stretch=1)
        return box

    def _privacy_banner(self) -> QFrame:
        light = get_current_theme() == "light"
        banner = QFrame()
        banner.setObjectName("PrivacyTint")
        bg, border = ("#eaf8f1", "#cfe9dc") if light else ("#12281f", "#1b3d2e")
        banner.setStyleSheet(
            f"QFrame#PrivacyTint {{ background-color: {bg}; border: 1px solid {border}; border-radius: 14px; }}"
        )
        row = QHBoxLayout(banner)
        row.setContentsMargins(18, 13, 18, 13)
        row.setSpacing(14)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap("mdi6.shield-check-outline", "#12a06a", size=22))
        row.addWidget(icon_lbl)
        text = QLabel("Your data stays private and secure. Comparisons are processed locally and not shared.")
        text.setWordWrap(True)
        row.addWidget(text, stretch=1)
        return banner

    # ------------------------------------------------------------- state

    def refresh(self) -> None:
        records = storage.list_scans()
        previous = (self.combo_a.currentData(), self.combo_b.currentData())
        self._records = records
        for combo in (self.combo_a, self.combo_b):
            combo.blockSignals(True)
            combo.clear()
            for r in records:
                combo.addItem(make_icon("fa5.calendar-alt", muted_text_color()), _scan_label(r), r.id)

        ids = [r.id for r in records]
        if previous[0] in ids and previous[1] in ids and previous[0] != previous[1]:
            self.combo_a.setCurrentIndex(ids.index(previous[0]))
            self.combo_b.setCurrentIndex(ids.index(previous[1]))
        elif len(records) >= 2:
            self.combo_a.setCurrentIndex(1)  # the scan before the latest
            self.combo_b.setCurrentIndex(0)  # the latest
        else:
            self.combo_a.setCurrentIndex(-1)
            self.combo_b.setCurrentIndex(-1)
        for combo in (self.combo_a, self.combo_b):
            combo.blockSignals(False)
        self._render()

    def _find(self, scan_id: Optional[str]):
        return next((r for r in self._records if r.id == scan_id), None)

    @staticmethod
    def _load(record) -> Optional[np.ndarray]:
        return cv2.imread(record.image_path) if record and record.image_path else None

    def _render(self, *_args) -> None:
        record_a = self._find(self.combo_a.currentData())
        record_b = self._find(self.combo_b.currentData())
        ready = bool(record_a and record_b and record_a.id != record_b.id)

        if len(self._records) < 2:
            message = "Need at least two saved scans to compare."
        elif not (record_a and record_b):
            message = "Select a start scan and an end scan to compare."
        elif record_a.id == record_b.id:
            message = "Choose two different scans to compare."
        else:
            message = ""
        self.status_banner.setVisible(bool(message))
        self.status_label.setText(message)

        _clear(self.category_body)
        _clear(self.region_body)
        self.category_card.setVisible(ready)
        if ready:
            self.category_body.addWidget(self._table(
                "Category", [(title, getter(record_a.analysis).level, getter(record_b.analysis).level)
                             for title, getter in CATEGORIES],
            ))
            self.region_body.addWidget(self._table(
                "Region", [(region.title(), _region_level(record_a, region), _region_level(record_b, region))
                           for region in STANDARD_REGIONS],
            ))

        image_a, image_b = self._load(record_a), self._load(record_b)
        self._render_photos(record_a, record_b, image_a, image_b)

    def _render_photos(self, record_a, record_b, image_a, image_b) -> None:
        both = image_a is not None and image_b is not None and record_a.id != record_b.id
        self.slider_card.setVisible(both)
        self.slots_widget.setVisible(not both)
        if both:
            self.photo_hint.setText("Drag the divider to compare the two photos.")
            self.slider.set_images(
                image_a, image_b, before_label=_scan_label(record_a), after_label=_scan_label(record_b),
            )
            return

        self.photo_hint.setText("Both scans need a saved photo to compare visually.")
        self.slider.set_images(None, None)
        for slot, record, image in ((self.slot_before, record_a, image_a), (self.slot_after, record_b, image_b)):
            if image is not None:
                slot.show_photo(image, _scan_label(record))
            elif record is not None:
                slot.show_placeholder("No saved photo", "This scan has no saved photo")
            else:
                slot.show_placeholder("No photo selected", "Select a scan with a saved photo")

    # ------------------------------------------------------------- tables

    def _table(self, first_header: str, rows: List[Tuple[str, str, str]]) -> QWidget:
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(0)
        for col, stretch in enumerate((3, 2, 2, 3)):
            grid.setColumnStretch(col, stretch)

        for col, text in enumerate((first_header, "From", "To", "Change")):
            header = QLabel(text)
            header.setStyleSheet(f"font-weight: 800; color: {muted_text_color()}; font-size: 11px;")
            header.setMinimumHeight(28)
            grid.addWidget(header, 0, col)

        for i, (name, a_level, b_level) in enumerate(rows):
            grid_row = 1 + i * 2
            grid.setRowMinimumHeight(grid_row, 46)
            label = QLabel(name)
            label.setStyleSheet("font-weight: 600;")
            grid.addWidget(label, grid_row, 0)
            grid.addWidget(self._level_pill(a_level), grid_row, 1, alignment=Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(self._level_pill(b_level), grid_row, 2, alignment=Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(self._change_cell(a_level, b_level), grid_row, 3)
            if i < len(rows) - 1:
                divider = QFrame()
                divider.setObjectName("Divider")
                divider.setFixedHeight(1)
                grid.addWidget(divider, grid_row + 1, 0, 1, 4)
        return host

    @staticmethod
    def _level_pill(level: str) -> QLabel:
        lbl = QLabel(level.title())
        lbl.setStyleSheet(pill_stylesheet(level))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedHeight(26)
        lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        return lbl

    @staticmethod
    def _change_cell(a_level: str, b_level: str) -> QWidget:
        label, dot_color, text_color = _change(a_level, b_level)
        cell = QWidget()
        cell.setStyleSheet("background: transparent;")
        row = QHBoxLayout(cell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        dot = QLabel()
        dot.setFixedSize(9, 9)
        dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 4px;")
        row.addWidget(dot)
        text = QLabel(label)
        text.setStyleSheet(f"color: {text_color}; font-weight: 700;")
        row.addWidget(text)
        row.addStretch()
        return cell
