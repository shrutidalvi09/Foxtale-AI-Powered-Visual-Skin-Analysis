"""Side-by-side comparison of two past scans, with a delta indicator per
category (improved / unchanged / worsened) -- useful for tracking a
skincare routine over time."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from engine.schemas import LEVEL_SCORE
from gui.core import storage
from gui.theme import LEVEL_COLORS

CATEGORIES = [
    ("Acne-like Spots", lambda a: a.acne_like_spots),
    ("Visible Redness", lambda a: a.redness),
    ("Skin Texture", lambda a: a.texture),
    ("Dryness Indicators", lambda a: a.dryness_indicators),
]


def _delta_text(a_level: str, b_level: str) -> tuple[str, str]:
    da, db = LEVEL_SCORE[a_level], LEVEL_SCORE[b_level]
    if db < da:
        return "▼ Improved", "#10b981"
    if db > da:
        return "▲ Worsened", "#f43f5e"
    return "— Unchanged", "#8993a8"


class ComparePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(14)

        heading = QLabel("Compare Scans")
        heading.setObjectName("Heading")
        layout.addWidget(heading)

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
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        record_a = self._find(self.combo_a.currentData())
        record_b = self._find(self.combo_b.currentData())

        if not record_a or not record_b:
            self.grid.addWidget(QLabel("Need at least two saved scans to compare."), 0, 0)
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

    @staticmethod
    def _header_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 800; color: #8993a8; font-size: 11px;")
        return lbl

    @staticmethod
    def _level_pill(level: str) -> QLabel:
        color = LEVEL_COLORS.get(level, "#3b8dff")
        lbl = QLabel(level.title())
        lbl.setStyleSheet(
            f"background-color: {color}22; color: {color}; border-radius: 8px; padding: 3px 10px; font-weight: 700;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl
