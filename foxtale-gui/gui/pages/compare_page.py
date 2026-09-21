"""Side-by-side comparison of two past scans: category deltas, a per-region
breakdown (derived from how many visible observations fell in each facial
region), and -- when both scans have a saved photo -- an interactive
before/after slider."""

import cv2
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from engine.schemas import LEVEL_SCORE
from gui.assets import apply_card_shadow, icon_pixmap
from gui.core import storage
from gui.theme import get_current_theme, icon_color, level_pill_colors
from gui.widgets.before_after_slider import BeforeAfterSlider

STANDARD_REGIONS = ["FOREHEAD", "LEFT CHEEK", "RIGHT CHEEK", "NOSE", "CHIN"]

# (light, dark) text colors -- the vivid base hues read at only ~2.5-3.7:1 on
# a white background (verified by contrast calculation), so light mode gets
# deeper shades of the same hue; dark mode's bg is dark enough that the vivid
# hues already clear WCAG AA on their own.
_DELTA_COLORS = {
    "improved": ("#047857", "#10b981"),
    "worsened": ("#be123c", "#f43f5e"),
    "unchanged": ("#6b7280", "#8993a8"),
}

CATEGORIES = [
    ("Acne-like Spots", lambda a: a.acne_like_spots),
    ("Visible Redness", lambda a: a.redness),
    ("Skin Texture", lambda a: a.texture),
    ("Dryness Indicators", lambda a: a.dryness_indicators),
]


def _region_level(record, region_label: str) -> str:
    """An approximate per-region severity derived from how many visible
    observations were flagged there -- not a re-run of the analysis engine,
    just a count-based read of data already stored with the scan."""
    count = sum(1 for r in record.regions if r.region == region_label)
    return {0: "minimal", 1: "mild", 2: "moderate"}.get(count, "noticeable")


def _delta_text(a_level: str, b_level: str) -> tuple[str, str]:
    da, db = LEVEL_SCORE[a_level], LEVEL_SCORE[b_level]
    light, dark = _DELTA_COLORS["unchanged"]
    label = "— Unchanged"
    if db < da:
        label, (light, dark) = "▼ Improved", _DELTA_COLORS["improved"]
    elif db > da:
        label, (light, dark) = "▲ Worsened", _DELTA_COLORS["worsened"]
    return label, (dark if get_current_theme() == "dark" else light)


class ComparePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_icon = QLabel()
        header_icon.setPixmap(icon_pixmap("fa5s.exchange-alt", icon_color("accent"), size=22))
        header_row.addWidget(header_icon)
        heading = QLabel("Compare Scans")
        heading.setObjectName("Heading")
        header_row.addWidget(heading)
        header_row.addStretch()
        layout.addLayout(header_row)

        picker_row = QHBoxLayout()
        self.combo_a = QComboBox()
        self.combo_b = QComboBox()
        picker_row.addWidget(QLabel("From:"))
        picker_row.addWidget(self.combo_a, stretch=1)
        picker_row.addWidget(QLabel("To:"))
        picker_row.addWidget(self.combo_b, stretch=1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("Secondary")
        refresh_btn.clicked.connect(self.refresh)
        picker_row.addWidget(refresh_btn)
        layout.addLayout(picker_row)

        self.combo_a.currentIndexChanged.connect(self._render)
        self.combo_b.currentIndexChanged.connect(self._render)

        self.grid = QGridLayout()
        layout.addLayout(self.grid)

        region_title = QLabel("Facial Region Comparison")
        region_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        layout.addWidget(region_title)
        region_note = QLabel(
            "Approximate — based on how many visible observations were flagged in each region, "
            "not a separate analysis pass."
        )
        region_note.setObjectName("Muted")
        region_note.setWordWrap(True)
        layout.addWidget(region_note)
        self.region_grid = QGridLayout()
        layout.addLayout(self.region_grid)

        slider_title = QLabel("Before / After Photo")
        slider_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        layout.addWidget(slider_title)
        slider_card = QFrame()
        slider_card.setObjectName("Card")
        apply_card_shadow(slider_card)
        slider_layout = QVBoxLayout(slider_card)
        self.slider = BeforeAfterSlider()
        slider_layout.addWidget(self.slider)
        layout.addWidget(slider_card)

        layout.addStretch()

        self.refresh()

    def refresh(self) -> None:
        records = storage.list_scans()
        self._records = records
        for combo in (self.combo_a, self.combo_b):
            combo.blockSignals(True)
            combo.clear()
            for r in records:
                combo.addItem(r.timestamp.replace("T", " ")[:16], r.id)
            combo.blockSignals(False)
        if len(records) >= 2:
            self.combo_a.setCurrentIndex(1)
            self.combo_b.setCurrentIndex(0)
        self._render()

    def _find(self, scan_id: Optional[str]):
        return next((r for r in self._records if r.id == scan_id), None)

    def _render(self) -> None:
        for grid in (self.grid, self.region_grid):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()

        record_a = self._find(self.combo_a.currentData())
        record_b = self._find(self.combo_b.currentData())

        if not record_a or not record_b:
            self.grid.addWidget(QLabel("Need at least two saved scans to compare."), 0, 0)
            self.slider.set_images(None, None)
            return

        self.grid.addWidget(self._header_label("Category"), 0, 0)
        self.grid.addWidget(self._header_label("From"), 0, 1)
        self.grid.addWidget(self._header_label("To"), 0, 2)
        self.grid.addWidget(self._header_label("Change"), 0, 3)

        for row, (title, getter) in enumerate(CATEGORIES, start=1):
            a_result = getter(record_a.analysis)
            b_result = getter(record_b.analysis)

            self.grid.addWidget(QLabel(title), row, 0)
            self.grid.addWidget(self._level_pill(a_result.level), row, 1)
            self.grid.addWidget(self._level_pill(b_result.level), row, 2)

            text, color = _delta_text(a_result.level, b_result.level)
            delta_label = QLabel(text)
            delta_label.setStyleSheet(f"color: {color}; font-weight: 700;")
            self.grid.addWidget(delta_label, row, 3)

        self.region_grid.addWidget(self._header_label("Region"), 0, 0)
        self.region_grid.addWidget(self._header_label("From"), 0, 1)
        self.region_grid.addWidget(self._header_label("To"), 0, 2)
        self.region_grid.addWidget(self._header_label("Change"), 0, 3)
        for row, region in enumerate(STANDARD_REGIONS, start=1):
            a_level = _region_level(record_a, region)
            b_level = _region_level(record_b, region)
            self.region_grid.addWidget(QLabel(region.title()), row, 0)
            self.region_grid.addWidget(self._level_pill(a_level), row, 1)
            self.region_grid.addWidget(self._level_pill(b_level), row, 2)
            text, color = _delta_text(a_level, b_level)
            delta_label = QLabel(text)
            delta_label.setStyleSheet(f"color: {color}; font-weight: 700;")
            self.region_grid.addWidget(delta_label, row, 3)

        image_a = cv2.imread(record_a.image_path) if record_a.image_path else None
        image_b = cv2.imread(record_b.image_path) if record_b.image_path else None
        self.slider.set_images(
            image_a, image_b,
            before_label=record_a.timestamp.replace("T", " ")[:16],
            after_label=record_b.timestamp.replace("T", " ")[:16],
        )

    @staticmethod
    def _header_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 800; color: #8993a8; font-size: 11px;")
        return lbl

    @staticmethod
    def _level_pill(level: str) -> QLabel:
        bg, text = level_pill_colors(level)
        lbl = QLabel(level.title())
        lbl.setStyleSheet(
            f"background-color: {bg}; color: {text}; border-radius: 8px; padding: 3px 10px; font-weight: 700;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl
