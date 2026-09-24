"""The History page's building blocks: pastel stat tiles and the scan list
card -- a sortable, paginated table with photo thumbnails, level + priority
chips per category, a star toggle and a row menu.
"""

from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from engine.schemas import LEVEL_SCORE
from gui.assets import apply_card_shadow, icon as make_icon, icon_circle
from gui.core.storage import ScanRecord
from gui.theme import FOX, LEVEL_COLORS, ORANGE_TEXT, get_current_theme, muted_text_color

THUMB_W, THUMB_H = 46, 56

# Table columns: (key, stretch). "star", "note" and "actions" are not sortable.
COLUMNS = [
    ("star", 5), ("date", 22), ("spots", 17), ("redness", 17),
    ("texture", 17), ("dryness", 17), ("note", 20), ("actions", 9),
]
SORTABLE = {"date": "Date", "spots": "Spots", "redness": "Redness", "texture": "Texture", "dryness": "Dryness"}
CATEGORY_GETTERS = {
    "spots": lambda a: a.acne_like_spots,
    "redness": lambda a: a.redness,
    "texture": lambda a: a.texture,
    "dryness": lambda a: a.dryness_indicators,
}

# How prominent a level is on the page: (label, light (bg, text), dark (bg, text)).
PRIORITY = {
    "minimal": ("Low", ("#dff5e8", "#12805c"), ("#0f3a2b", "#6ee7b7")),
    "mild": ("Low", ("#dff5e8", "#12805c"), ("#0f3a2b", "#6ee7b7")),
    "moderate": ("Medium", ("#ffedd5", "#c2410c"), ("#431407", "#fdba74")),
    "noticeable": ("High", ("#ffe4e6", "#be123c"), ("#4c0519", "#fda4af")),
}

# (tile background, icon circle background, icon color) per tile, per theme.
TILE_STYLES = {
    "light": {
        "peach": ("#fff3ea", "#fde2cf", "#e54a00"),
        "lavender": ("#f4effd", "#e6dcfa", "#7c4dcc"),
        "mint": ("#eaf8f1", "#d3f0e2", "#12805c"),
        "blue": ("#eef4ff", "#dbe7ff", "#3b6fe0"),
        "yellow": ("#fff7e3", "#fdebbd", "#c98a0a"),
    },
    "dark": {
        "peach": ("#2a1d10", "#3a2818", "#ff8a4c"),
        "lavender": ("#241c3a", "#33285a", "#b79bf0"),
        "mint": ("#12281f", "#1b3d2e", "#6ee7b7"),
        "blue": ("#17233d", "#233560", "#8db4ff"),
        "yellow": ("#2b2410", "#3d3315", "#f5c451"),
    },
}

_thumb_cache: Dict[str, Optional[QPixmap]] = {}


def _thumbnail(image_path: Optional[str]) -> Optional[QPixmap]:
    if not image_path:
        return None
    if image_path in _thumb_cache:
        return _thumb_cache[image_path]
    source = QPixmap(image_path)
    result: Optional[QPixmap] = None
    if not source.isNull():
        scaled = source.scaled(
            THUMB_W, THUMB_H, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QPixmap(THUMB_W, THUMB_H)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, THUMB_W, THUMB_H, 10, 10)
        painter.setClipPath(clip)
        painter.drawPixmap((THUMB_W - scaled.width()) // 2, (THUMB_H - scaled.height()) // 2, scaled)
        painter.end()
        result = canvas
    _thumb_cache[image_path] = result
    return result


class StatTile(QFrame):
    """A soft pastel stat card: tinted icon badge, big number, small label."""

    def __init__(self, icon_name: str, label: str, tone: str, parent=None):
        super().__init__(parent)
        theme = "light" if get_current_theme() == "light" else "dark"
        tile_bg, circle_bg, icon_fg = TILE_STYLES[theme][tone]
        self.setObjectName("StatTile")
        self.setStyleSheet(f"QFrame#StatTile {{ background-color: {tile_bg}; border: none; border-radius: 16px; }}")

        self.setMinimumWidth(0)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 14, 8, 14)
        row.setSpacing(10)
        row.addWidget(icon_circle(icon_name, icon_fg, circle_bg, size=44, icon_size=18))
        col = QVBoxLayout()
        col.setSpacing(0)
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet("font-size: 22px; font-weight: 800;")
        col.addWidget(self.value_label)
        text = QLabel(label)
        text.setObjectName("SubHeading")
        text.setStyleSheet("font-size: 12px;")
        text.setMinimumWidth(0)
        text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        col.addWidget(text)
        row.addLayout(col, stretch=1)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class _ClickableCell(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class HistoryListCard(QFrame):
    open_record = Signal(str)
    toggle_star = Signal(str)
    delete_scan = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        apply_card_shadow(self, blur=20, y_offset=5, alpha=18)

        self._records: List[ScanRecord] = []
        self._empty_message = "No scans match your filters yet."
        self._sort_key = "date"
        self._sort_desc = True
        self._page = 1
        self._per_page = 10

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(10)

        self._grid_host = QWidget()
        self._grid_host.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(0)
        outer.addWidget(self._grid_host, stretch=1)

        footer = QHBoxLayout()
        self._showing_label = QLabel("")
        self._showing_label.setObjectName("SubHeading")
        footer.addWidget(self._showing_label)
        footer.addStretch()
        self._pager = QHBoxLayout()
        self._pager.setSpacing(8)
        footer.addLayout(self._pager)
        self._per_page_combo = QComboBox()
        self._per_page_combo.setFixedHeight(40)
        for n in (10, 25, 50):
            self._per_page_combo.addItem(f"{n} / page", n)
        self._per_page_combo.currentIndexChanged.connect(self._on_per_page_changed)
        footer.addSpacing(6)
        footer.addWidget(self._per_page_combo)
        outer.addLayout(footer)

    # ---------------------------------------------------------------- api

    def set_records(self, records: List[ScanRecord], empty_message: str = "No scans match your filters yet.") -> None:
        self._records = list(records)
        self._empty_message = empty_message
        self._render()

    def reset_page(self) -> None:
        self._page = 1

    # ------------------------------------------------------------ sorting

    def _sorted(self) -> List[ScanRecord]:
        if self._sort_key == "date":
            key = lambda r: r.timestamp  # noqa: E731
        else:
            getter = CATEGORY_GETTERS[self._sort_key]
            key = lambda r: (LEVEL_SCORE[getter(r.analysis).level], r.timestamp)  # noqa: E731
        return sorted(self._records, key=key, reverse=self._sort_desc)

    def _on_sort(self, key: str) -> None:
        if self._sort_key == key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key, self._sort_desc = key, key == "date"
        self._page = 1
        self._render()

    def _on_per_page_changed(self, *_args) -> None:
        self._per_page = self._per_page_combo.currentData() or 10
        self._page = 1
        self._render()

    def _go_to(self, page: int) -> None:
        self._page = page
        self._render()

    # ---------------------------------------------------------- rendering

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        for i in range(len(COLUMNS)):
            self._grid.setColumnStretch(i, 0)
        for row in range(self._grid.rowCount() + 2):
            self._grid.setRowStretch(row, 0)
            self._grid.setRowMinimumHeight(row, 0)

    def _clear_pager(self) -> None:
        while self._pager.count():
            item = self._pager.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _render(self) -> None:
        self._clear_grid()
        for i, (_key, stretch) in enumerate(COLUMNS):
            self._grid.setColumnStretch(i, stretch)
        self._build_header()

        ordered = self._sorted()
        total = len(ordered)
        pages = max(1, -(-total // self._per_page))
        self._page = max(1, min(self._page, pages))
        start = (self._page - 1) * self._per_page
        page_records = ordered[start:start + self._per_page]

        if not page_records:
            empty = QLabel(self._empty_message)
            empty.setObjectName("SubHeading")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(150)
            self._grid.addWidget(empty, 1, 0, 1, len(COLUMNS))
        for i, record in enumerate(page_records):
            self._add_row(1 + i * 2, record)
            divider = QFrame()
            divider.setObjectName("Divider")
            divider.setFixedHeight(1)
            self._grid.addWidget(divider, 2 + i * 2, 0, 1, len(COLUMNS))

        # Extra card height goes below the last row, not into the rows themselves.
        self._grid.setRowStretch(2 + len(page_records) * 2, 1)

        if total == 0:
            self._showing_label.setText("Showing 0 of 0 scans")
        elif total <= self._per_page:
            self._showing_label.setText(f"Showing {total} of {total} scans")
        else:
            self._showing_label.setText(f"Showing {start + 1}–{start + len(page_records)} of {total} scans")
        self._build_pager(pages)

    def _build_header(self) -> None:
        light = get_current_theme() == "light"
        band = QFrame()
        band.setStyleSheet(f"background-color: {'#f7f8fb' if light else '#0f1526'}; border-radius: 12px;")
        band.setFixedHeight(48)
        self._grid.addWidget(band, 0, 0, 1, len(COLUMNS))

        for col, (key, _stretch) in enumerate(COLUMNS):
            if key == "star":
                cell = QLabel()
                cell.setPixmap(make_icon("fa5.star", muted_text_color()).pixmap(16, 16))
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            elif key in SORTABLE:
                cell = self._sort_header(key)
            else:
                cell = QLabel("Note" if key == "note" else "Actions")
                cell.setStyleSheet(f"font-weight: 700; color: {muted_text_color()}; background: transparent;")
                if key == "actions":
                    cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setFixedHeight(48)
            self._grid.addWidget(cell, 0, col)

    def _sort_header(self, key: str) -> QWidget:
        active = self._sort_key == key
        if not active:
            icon_name = "fa5s.sort"
        else:
            icon_name = "fa5s.sort-down" if self._sort_desc else "fa5s.sort-up"

        cell = _ClickableCell()
        cell.setToolTip(f"Sort by {SORTABLE[key].lower()}")
        row = QHBoxLayout(cell)
        row.setContentsMargins(4, 0, 0, 0)
        row.setSpacing(7)
        label = QLabel(SORTABLE[key])
        label.setStyleSheet(
            f"font-weight: 700; background: transparent; color: {ORANGE_TEXT if active else muted_text_color()};"
        )
        row.addWidget(label)
        arrow = QLabel()
        arrow.setPixmap(make_icon(icon_name, FOX if active else muted_text_color()).pixmap(11, 11))
        row.addWidget(arrow)
        row.addStretch()
        cell.clicked.connect(lambda k=key: self._on_sort(k))
        return cell

    def _add_row(self, grid_row: int, record: ScanRecord) -> None:
        self._grid.setRowMinimumHeight(grid_row, 92)
        rid = record.id

        star = QPushButton()
        star.setObjectName("IconButton")
        star.setCursor(Qt.CursorShape.PointingHandCursor)
        star.setIcon(make_icon("fa5s.star" if record.starred else "fa5.star",
                               FOX if record.starred else muted_text_color()))
        star.setIconSize(QSize(17, 17))
        star.setToolTip("Unstar" if record.starred else "Star")
        star.clicked.connect(lambda _=False, r=rid: self.toggle_star.emit(r))
        self._grid.addWidget(star, grid_row, 0, alignment=Qt.AlignmentFlag.AlignCenter)

        self._grid.addWidget(self._date_cell(record), grid_row, 1)
        for col, key in enumerate(("spots", "redness", "texture", "dryness"), start=2):
            self._grid.addWidget(self._level_cell(CATEGORY_GETTERS[key](record.analysis).level, rid), grid_row, col)
        self._grid.addWidget(self._note_cell(record), grid_row, 6)

        kebab = QPushButton()
        kebab.setObjectName("IconButton")
        kebab.setCursor(Qt.CursorShape.PointingHandCursor)
        kebab.setIcon(make_icon("fa5s.ellipsis-v", muted_text_color()))
        kebab.setIconSize(QSize(15, 15))
        kebab.setToolTip("More actions")
        kebab.clicked.connect(lambda _=False, r=record, b=kebab: self._show_row_menu(r, b))
        self._grid.addWidget(kebab, grid_row, 7, alignment=Qt.AlignmentFlag.AlignCenter)

    def _date_cell(self, record: ScanRecord) -> QWidget:
        cell = _ClickableCell()
        row = QHBoxLayout(cell)
        row.setContentsMargins(4, 8, 4, 8)
        row.setSpacing(12)

        thumb = QLabel()
        thumb.setFixedSize(THUMB_W, THUMB_H)
        pixmap = _thumbnail(record.image_path)
        if pixmap is not None:
            thumb.setPixmap(pixmap)
        else:
            light = get_current_theme() == "light"
            thumb.setStyleSheet(
                f"background-color: {'#fff1e7' if light else '#2a1d10'}; border-radius: 10px;"
            )
            thumb.setPixmap(make_icon("fa5s.image", "#e9b394" if light else "#7a5a44").pixmap(20, 20))
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(thumb)

        when = datetime.fromisoformat(record.timestamp)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addStretch()
        date_label = QLabel(when.strftime("%b %d, %Y"))
        date_label.setStyleSheet("font-weight: 800; font-size: 13px;")
        col.addWidget(date_label)
        time_label = QLabel(when.strftime("%I:%M %p"))
        time_label.setObjectName("SubHeading")
        col.addWidget(time_label)
        col.addStretch()
        row.addLayout(col, stretch=1)
        cell.clicked.connect(lambda r=record.id: self.open_record.emit(r))
        return cell

    def _level_cell(self, level: str, record_id: str) -> QWidget:
        cell = _ClickableCell()
        col = QVBoxLayout(cell)
        col.setContentsMargins(6, 8, 6, 8)
        col.setSpacing(6)
        col.addStretch()

        title_row = QHBoxLayout()
        title_row.setSpacing(7)
        dot = QLabel()
        dot.setFixedSize(9, 9)
        dot.setStyleSheet(f"background-color: {LEVEL_COLORS.get(level, '#9aa3b8')}; border-radius: 4px;")
        title_row.addWidget(dot)
        name = QLabel(level.title())
        name.setStyleSheet("font-size: 13px; font-weight: 600;")
        title_row.addWidget(name)
        title_row.addStretch()
        col.addLayout(title_row)

        label, light_pair, dark_pair = PRIORITY.get(level, PRIORITY["mild"])
        bg, fg = light_pair if get_current_theme() == "light" else dark_pair
        chip = QLabel(label)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setFixedHeight(22)
        chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        chip.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 11px; padding: 0 12px; "
            "font-size: 11px; font-weight: 700;"
        )
        col.addWidget(chip, alignment=Qt.AlignmentFlag.AlignLeft)
        col.addStretch()
        cell.clicked.connect(lambda r=record_id: self.open_record.emit(r))
        return cell

    def _note_cell(self, record: ScanRecord) -> QWidget:
        cell = _ClickableCell()
        col = QVBoxLayout(cell)
        col.setContentsMargins(4, 8, 4, 8)
        note = record.note.strip()
        label = QLabel(note if len(note) <= 60 else note[:57] + "…")
        label.setWordWrap(True)
        if note:
            label.setToolTip(note)
        else:
            label.setText("—")
            label.setObjectName("Muted")
        col.addWidget(label, alignment=Qt.AlignmentFlag.AlignVCenter)
        cell.clicked.connect(lambda r=record.id: self.open_record.emit(r))
        return cell

    def _show_row_menu(self, record: ScanRecord, anchor: QPushButton) -> None:
        menu = QMenu(self)
        menu.addAction("Open analysis", lambda: self.open_record.emit(record.id))
        menu.addAction("Unstar" if record.starred else "Star", lambda: self.toggle_star.emit(record.id))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete_scan.emit(record.id))
        menu.exec(anchor.mapToGlobal(QPoint(0, anchor.height() + 4)))

    # ---------------------------------------------------------- pagination

    def _page_button(self, text: str = "", icon_name: Optional[str] = None, enabled: bool = True,
                     checked: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("PageButton")
        btn.setFixedSize(40, 40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setEnabled(enabled)
        if icon_name:
            btn.setIcon(make_icon(icon_name, muted_text_color() if enabled else "#b8c0d6"))
            btn.setIconSize(QSize(13, 13))
        return btn

    def _build_pager(self, pages: int) -> None:
        self._clear_pager()
        prev_btn = self._page_button(icon_name="fa5s.chevron-left", enabled=self._page > 1)
        prev_btn.clicked.connect(lambda: self._go_to(self._page - 1))
        self._pager.addWidget(prev_btn)

        first = max(1, min(self._page - 2, pages - 4))
        for number in range(first, min(pages, first + 4) + 1):
            btn = self._page_button(text=str(number), checked=number == self._page)
            btn.clicked.connect(lambda _=False, n=number: self._go_to(n))
            self._pager.addWidget(btn)

        next_btn = self._page_button(icon_name="fa5s.chevron-right", enabled=self._page < pages)
        next_btn.clicked.connect(lambda: self._go_to(self._page + 1))
        self._pager.addWidget(next_btn)
