"""A dedicated page showing exactly what Foxtale has stored locally, so the
app's "nothing leaves this device" claim is verifiable rather than just
asserted -- plus a live offline check, one-click export and a scoped,
confirmed data wipe."""

from typing import Callable, Dict, List, Tuple

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow, apply_cta_glow, icon as make_icon, icon_circle, icon_pixmap
from gui.core import storage
from gui.core.offline_check import run_offline_verification
from gui.theme import FOX, get_current_theme, muted_text_color

WIDE_FROM = 1300  # page width from which stat tiles sit in one row

# tone -> (circle background, icon color), per theme
TONES = {
    "light": {
        "blue": ("#e4efff", "#3b6fe0"), "lavender": ("#efe8fc", "#7c4dcc"), "mint": ("#d6f1e3", "#12a06a"),
        "peach": ("#fde8da", "#e54a00"), "rose": ("#ffe3ea", "#d6336c"),
    },
    "dark": {
        "blue": ("#17233d", "#8db4ff"), "lavender": ("#2a2145", "#b79bf0"), "mint": ("#12281f", "#6ee7b7"),
        "peach": ("#3a2818", "#ff8a4c"), "rose": ("#3a1523", "#ff8fab"),
    },
}
# panel -> (background, border), per theme
PANELS = {
    "light": {"mint": ("#eefaf4", "#cdeadb"), "rose": ("#fff1f4", "#fbd3dc")},
    "dark": {"mint": ("#12281f", "#1b3d2e"), "rose": ("#2a1220", "#5b2331")},
}


def _theme() -> str:
    return "light" if get_current_theme() == "light" else "dark"


def _tone(name: str) -> Tuple[str, str]:
    return TONES[_theme()][name]


def _format_bytes(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class _StatCell(QWidget):
    """A tinted icon, a small label, and a bold value."""

    def __init__(self, icon_name: str, tone: str, label: str, value: str = "—", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        circle_bg, icon_fg = _tone(tone)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(12)
        row.addWidget(icon_circle(icon_name, icon_fg, circle_bg, size=46, icon_size=19), alignment=Qt.AlignmentFlag.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel(label)
        name.setObjectName("SubHeading")
        name.setStyleSheet("font-size: 12px;")
        col.addWidget(name)
        self.value_label = QLabel(value)
        self.value_label.setTextFormat(Qt.TextFormat.RichText)
        self.value_label.setStyleSheet("font-size: 18px; font-weight: 800;")
        col.addWidget(self.value_label)
        row.addLayout(col, stretch=1)

    def set_value(self, html: str) -> None:
        self.value_label.setText(html)


class _ActionRow(QFrame):
    """A large, clickable action: tinted icon, title, description, chevron."""

    clicked = Signal()

    def __init__(self, panel: str, icon_name: str, tone: str, title: str, body: str, title_color: str = "", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        bg, border = PANELS[_theme()][panel]
        self.setObjectName("ActionRow")
        self.setStyleSheet(
            f"QFrame#ActionRow {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
        )
        circle_bg, icon_fg = _tone(tone)
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 16, 18, 16)
        row.setSpacing(16)
        badge = QFrame()
        badge.setFixedSize(50, 50)
        badge.setStyleSheet(f"background-color: {icon_fg}; border-radius: 14px; border: none;")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        glyph = QLabel()
        glyph.setPixmap(icon_pixmap(icon_name, "white", size=20))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(glyph)
        row.addWidget(badge)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 14px; font-weight: 800; {('color: ' + title_color + ';') if title_color else ''}")
        col.addWidget(t)
        b = QLabel(body)
        b.setObjectName("SubHeading")
        b.setStyleSheet("font-size: 12px;")
        b.setWordWrap(True)
        col.addWidget(b)
        row.addLayout(col, stretch=1)

        chevron = QLabel()
        chevron.setPixmap(icon_pixmap("fa5s.chevron-right", muted_text_color(), size=13))
        row.addWidget(chevron)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _card() -> Tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    apply_card_shadow(frame, blur=20, y_offset=5, alpha=18)
    v = QVBoxLayout(frame)
    v.setContentsMargins(24, 20, 24, 22)
    v.setSpacing(16)
    return frame, v


def _card_header(icon_name: str, tone: str, title: str, subtitle: str, right: QWidget = None) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(14)
    circle_bg, icon_fg = _tone(tone)
    row.addWidget(icon_circle(icon_name, icon_fg, circle_bg, size=46, icon_size=19), alignment=Qt.AlignmentFlag.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("CardTitle")
    t.setStyleSheet("font-size: 16px;")
    col.addWidget(t)
    s = QLabel(subtitle)
    s.setObjectName("SubHeading")
    s.setStyleSheet("font-size: 12px;")
    s.setWordWrap(True)
    col.addWidget(s)
    row.addLayout(col, stretch=1)
    if right is not None:
        row.addWidget(right, alignment=Qt.AlignmentFlag.AlignTop)
    return row


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


class PrivacyPage(QWidget):
    def __init__(self, show_toast: Callable[[str], None], parent=None):
        super().__init__(parent)
        self._show_toast = show_toast
        self._wide: bool = False

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
        layout.setSpacing(18)

        self._build_header(layout)
        self._build_local_data_card(layout)
        self._build_network_card(layout)
        self._build_actions_card(layout)
        layout.addStretch(1)

        self._arrange(wide=False)
        self.refresh()

    # ------------------------------------------------------------- layout

    def _build_header(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(16)
        badge = QFrame()
        badge.setFixedSize(52, 52)
        light = _theme() == "light"
        badge.setStyleSheet(
            f"background-color: {'#fde8da' if light else '#3a2818'}; border-radius: 14px; border: none;"
        )
        inner = QVBoxLayout(badge)
        inner.setContentsMargins(0, 0, 0, 0)
        glyph = QLabel()
        glyph.setPixmap(icon_pixmap("fa5s.lock", FOX, size=22))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(glyph)
        row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(4)
        heading = QLabel("Privacy Dashboard")
        heading.setObjectName("Heading")
        col.addWidget(heading)
        sub = QLabel(
            "Exactly what exists on this device — nothing more, <b>nothing hidden</b>."
        )
        sub.setTextFormat(Qt.TextFormat.RichText)
        sub.setObjectName("SubHeading")
        sub.setWordWrap(True)
        col.addWidget(sub)
        row.addLayout(col, stretch=1)
        layout.addLayout(row)

    def _build_local_data_card(self, layout: QVBoxLayout) -> None:
        card, v = _card()
        v.addLayout(_card_header(
            "fa5s.database", "peach", "Local Data", "Scan records, saved images, and device storage information.",
        ))
        v.addWidget(_divider())

        self._stat_cells: Dict[str, _StatCell] = {}
        specs = [
            ("scans", "fa5s.file-alt", "blue", "Scan records"),
            ("trash", "fa5.image", "lavender", "Recently deleted"),
            ("images", "fa5.image", "mint", "Saved images"),
            ("db", "fa5s.database", "peach", "Database size"),
            ("images_size", "fa5s.crosshairs", "lavender", "Images size"),
            ("calibration", "mdi6.shield-check-outline", "mint", "Calibration"),
        ]
        for key, icon_name, tone, label in specs:
            self._stat_cells[key] = _StatCell(icon_name, tone, label)
        self._local_order = [key for key, *_ in specs]
        self._local_separators = [self._separator() for _ in range(len(specs) - 1)]
        self._local_grid = QGridLayout()
        self._local_grid.setHorizontalSpacing(20)
        self._local_grid.setVerticalSpacing(14)
        v.addLayout(self._local_grid)
        layout.addWidget(card)

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setObjectName("VerticalRule")
        line.setFixedWidth(1)
        line.setStyleSheet("QFrame#VerticalRule { background-color: rgba(128,128,128,0.25); border: none; }")
        line.setMinimumHeight(44)
        return line

    def _build_network_card(self, layout: QVBoxLayout) -> None:
        light = _theme() == "light"
        self.status_badge = QFrame()
        self.status_badge.setObjectName("StatusBadge")
        badge_row = QHBoxLayout(self.status_badge)
        badge_row.setContentsMargins(14, 7, 14, 7)
        badge_row.setSpacing(8)
        self._badge_dot = QLabel()
        self._badge_dot.setFixedSize(8, 8)
        badge_row.addWidget(self._badge_dot)
        self._badge_text = QLabel("Offline")
        badge_row.addWidget(self._badge_text)
        self._badge_icon = QLabel()
        badge_row.addWidget(self._badge_icon)
        self._set_badge(ok=True, text="Offline")

        card, v = _card()
        v.addLayout(_card_header(
            "mdi6.cloud-outline", "lavender", "Network & Cloud", "Network requests and cloud usage.",
            right=self.status_badge,
        ))
        v.addWidget(_divider())

        self._net_cells: List[QWidget] = [
            _StatCell("fa5s.broadcast-tower", "blue", "Telemetry", "Disabled"),
            _StatCell("mdi6.cloud-outline", "blue", "Cloud storage", "None"),
            _StatCell("fa5s.map-marker-alt", "mint", "Analysis location", "Entirely on this device"),
        ]
        self._net_separators = [self._separator() for _ in range(3)]
        self._callout = self._build_callout()
        self._net_grid = QGridLayout()
        self._net_grid.setHorizontalSpacing(20)
        self._net_grid.setVerticalSpacing(14)
        v.addLayout(self._net_grid)

        v.addWidget(self._build_verify_row())
        layout.addWidget(card)

    def _set_badge(self, ok: bool, text: str) -> None:
        light = _theme() == "light"
        if ok:
            bg, border, fg, dot = ("#eaf8f1", "#cfe9dc", "#0f7a55", "#12a06a") if light else ("#12281f", "#1b3d2e", "#6ee7b7", "#10b981")
        else:
            bg, border, fg, dot = ("#ffe4e6", "#f5b5bd", "#be123c", "#e11d48") if light else ("#4c0519", "#8a3348", "#fda4af", "#f43f5e")
        self.status_badge.setStyleSheet(
            f"QFrame#StatusBadge {{ background-color: {bg}; border: 1px solid {border}; border-radius: 17px; }}"
        )
        self._badge_dot.setStyleSheet(f"background-color: {dot}; border-radius: 4px;")
        self._badge_text.setText(text)
        self._badge_text.setStyleSheet(f"color: {fg}; font-weight: 700; font-size: 12px;")
        self._badge_icon.setPixmap(icon_pixmap("mdi6.wifi-off", fg, size=15))
        self.status_badge.setFixedHeight(34)

    def _build_callout(self) -> QFrame:
        bg, border = PANELS[_theme()]["rose"]
        box = QFrame()
        box.setObjectName("NoRequestsCallout")
        box.setStyleSheet(
            f"QFrame#NoRequestsCallout {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
        )
        row = QHBoxLayout(box)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(14)
        circle_bg, icon_fg = _tone("rose")
        row.addWidget(icon_circle("mdi6.wifi-off", icon_fg, circle_bg, size=44, icon_size=20), alignment=Qt.AlignmentFlag.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel("Foxtale never makes one network request.")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 13px; font-weight: 800;")
        col.addWidget(title)
        body = QLabel("Your data stays on your device — no external access, no tracking.")
        body.setObjectName("SubHeading")
        body.setStyleSheet("font-size: 12px;")
        body.setWordWrap(True)
        col.addWidget(body)
        row.addLayout(col, stretch=1)
        return box

    def _build_verify_row(self) -> QFrame:
        bg, border = PANELS[_theme()]["mint"]
        box = QFrame()
        box.setObjectName("VerifyRow")
        box.setStyleSheet(
            f"QFrame#VerifyRow {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
        )
        row = QHBoxLayout(box)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(16)
        shield = QLabel()
        shield.setPixmap(icon_pixmap("mdi6.shield-check", "#12805c" if _theme() == "light" else "#6ee7b7", size=34))
        row.addWidget(shield)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel("Run Offline Verification")
        title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {'#0f6b4a' if _theme() == 'light' else '#6ee7b7'};")
        col.addWidget(title)
        note = QLabel(
            "Runs a real analysis pass with network access blocked at the socket layer — "
            "a live check, not just a claim."
        )
        note.setObjectName("SubHeading")
        note.setStyleSheet("font-size: 12px;")
        note.setWordWrap(True)
        col.addWidget(note)
        row.addLayout(col, stretch=1)

        run_btn = QPushButton("  Run Check")
        run_btn.setIcon(make_icon("fa5s.play", "white"))
        run_btn.setIconSize(QSize(13, 13))
        run_btn.setObjectName("Cta")
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.setFixedHeight(46)
        run_btn.setMinimumWidth(140)
        apply_cta_glow(run_btn)
        run_btn.clicked.connect(self._run_offline_verification)
        row.addWidget(run_btn)
        return box

    def _build_actions_card(self, layout: QVBoxLayout) -> None:
        card, v = _card()
        v.addLayout(_card_header(
            "fa5.folder", "rose", "Data Actions", "Manage your local data and history.",
        ))
        v.addWidget(_divider())

        row = QHBoxLayout()
        row.setSpacing(16)
        export_row = _ActionRow(
            "mint", "fa5s.upload", "mint", "Export Everything",
            "Save your full data (history, images, calibration, etc.).",
            title_color="#0f6b4a" if _theme() == "light" else "#6ee7b7",
        )
        export_row.clicked.connect(self._export_everything)
        row.addWidget(export_row, stretch=1)

        delete_row = _ActionRow(
            "rose", "fa5s.trash-alt", "rose", "Delete All Data",
            "Permanently remove your scan history, saved images and calibration. "
            "Your app preferences are kept.",
            title_color="#be123c" if _theme() == "light" else "#fda4af",
        )
        delete_row.clicked.connect(self._delete_all_data)
        row.addWidget(delete_row, stretch=1)
        v.addLayout(row)
        layout.addWidget(card)

    # ---------------------------------------------------------- responsive

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        wide = self.width() >= WIDE_FROM
        if wide != self._wide:
            self._arrange(wide)

    @staticmethod
    def _detach(grid: QGridLayout) -> None:
        while grid.count():
            grid.takeAt(0)
        for i in range(grid.columnCount() + 1):
            grid.setColumnStretch(i, 0)

    def _arrange(self, wide: bool) -> None:
        """One row of tiles with dividers when there is room; otherwise
        wrap to three per row so nothing forces the window wider."""
        self._wide = wide

        cells = [self._stat_cells[k] for k in self._local_order]
        self._detach(self._local_grid)
        if wide:
            for i, cell in enumerate(cells):
                self._local_grid.addWidget(cell, 0, i * 2)
                self._local_grid.setColumnStretch(i * 2, 1)
                if i < len(cells) - 1:
                    sep = self._local_separators[i]
                    sep.setVisible(True)
                    self._local_grid.addWidget(sep, 0, i * 2 + 1)
        else:
            for sep in self._local_separators:
                sep.setVisible(False)
            for i, cell in enumerate(cells):
                self._local_grid.addWidget(cell, i // 3, i % 3)
            for c in range(3):
                self._local_grid.setColumnStretch(c, 1)

        self._detach(self._net_grid)
        if wide:
            for i, cell in enumerate(self._net_cells):
                self._net_grid.addWidget(cell, 0, i * 2, alignment=Qt.AlignmentFlag.AlignVCenter)
                self._net_grid.setColumnStretch(i * 2, 1)
                self._net_separators[i].setVisible(True)
                self._net_grid.addWidget(self._net_separators[i], 0, i * 2 + 1)
            self._net_grid.addWidget(self._callout, 0, 6)
            self._net_grid.setColumnStretch(6, 2)
        else:
            for sep in self._net_separators:
                sep.setVisible(False)
            for i, cell in enumerate(self._net_cells):
                self._net_grid.addWidget(cell, 0, i)
                self._net_grid.setColumnStretch(i, 1)
            self._net_grid.addWidget(self._callout, 1, 0, 1, 3)

    # ------------------------------------------------------------- data

    def refresh(self) -> None:
        stats = storage.get_data_stats()
        muted = "font-size:12px; font-weight:400;"
        values = {
            "scans": str(stats["scan_count"]),
            "trash": f'{stats["trashed_count"]} <span style="{muted}">(kept {storage.TRASH_RETENTION_DAYS} days)</span>',
            "images": str(stats["image_count"]),
            "db": _format_bytes(stats["db_size_bytes"]),
            "images_size": _format_bytes(stats["images_size_bytes"]),
            "calibration": "Enabled" if stats["calibration_enabled"] else "Not set",
        }
        for key, value in values.items():
            self._stat_cells[key].set_value(value)

    def _run_offline_verification(self) -> None:
        ok, message = run_offline_verification()
        self._set_badge(ok, "Verified offline" if ok else "Network attempt blocked")
        if ok:
            QMessageBox.information(self, "Offline verification passed", message)
        else:
            QMessageBox.warning(self, "Offline verification failed", message)

    def _export_everything(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Everything", "foxtale-backup.zip", "Zip files (*.zip)")
        if not path:
            return
        storage.export_full_backup(path)
        self._show_toast("Everything exported.")

    def _delete_all_data(self) -> None:
        if QMessageBox.question(
            self, "Delete all data",
            "This permanently deletes your scan history, saved images, and calibration profile. "
            "Your app preferences are kept. This cannot be undone. Continue?",
        ) != QMessageBox.StandardButton.Yes:
            return
        storage.delete_all_personal_data()
        self._show_toast("All personal data deleted.")
        self.refresh()
