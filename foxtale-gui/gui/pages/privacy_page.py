"""A dedicated page showing exactly what Foxtale has stored locally, so the
app's "nothing leaves this device" claim is verifiable rather than just
asserted -- plus one-click export and a scoped, confirmed data wipe."""

from typing import Callable

from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow, icon as make_icon, icon_pixmap
from gui.core import storage
from gui.core.offline_check import run_offline_verification
from gui.theme import icon_color


def _format_bytes(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class PrivacyPage(QWidget):
    def __init__(self, show_toast: Callable[[str], None], parent=None):
        super().__init__(parent)
        self._show_toast = show_toast

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_icon = QLabel()
        header_icon.setPixmap(icon_pixmap("fa5s.user-shield", icon_color("accent"), size=22))
        header_row.addWidget(header_icon)
        heading = QLabel("Privacy Dashboard")
        heading.setObjectName("Heading")
        header_row.addWidget(heading)
        header_row.addStretch()
        layout.addLayout(header_row)

        sub = QLabel("Exactly what exists on this device — nothing more, nothing hidden.")
        sub.setObjectName("SubHeading")
        layout.addWidget(sub)

        self.stats_card, stats_layout = self._card("Local Data")
        self.stats_rows_layout = QVBoxLayout()
        stats_layout.addLayout(self.stats_rows_layout)
        layout.addWidget(self.stats_card)

        self.status_card, _ = self._card("Network & Cloud")
        status_layout = self.status_card.layout()
        for label, value in [
            ("Network requests", "0 — Foxtale never makes one"),
            ("Telemetry", "Disabled"),
            ("Cloud storage", "None"),
            ("Analysis location", "Entirely on this device"),
        ]:
            status_layout.addLayout(self._stat_row(label, value))

        verify_row = QHBoxLayout()
        verify_btn = QPushButton(" Run Offline Verification")
        verify_btn.setIcon(make_icon("fa5s.satellite-dish", icon_color("primary")))
        verify_btn.setObjectName("Secondary")
        verify_btn.clicked.connect(self._run_offline_verification)
        verify_row.addWidget(verify_btn)
        verify_row.addStretch()
        status_layout.addLayout(verify_row)

        verify_note = QLabel(
            "Runs a real analysis pass with network access blocked at the socket layer — "
            "a live check, not just a claim."
        )
        verify_note.setObjectName("Muted")
        verify_note.setWordWrap(True)
        status_layout.addWidget(verify_note)
        layout.addWidget(self.status_card)

        actions_card, actions_layout = self._card("Data Actions")
        actions_row = QHBoxLayout()
        export_btn = QPushButton(" Export Everything")
        export_btn.setIcon(make_icon("fa5s.file-archive", icon_color("primary")))
        export_btn.setObjectName("Secondary")
        export_btn.clicked.connect(self._export_everything)
        actions_row.addWidget(export_btn)

        delete_btn = QPushButton(" Delete All Data")
        delete_btn.setIcon(make_icon("fa5s.trash-alt", icon_color("warning")))
        delete_btn.setObjectName("Secondary")
        delete_btn.clicked.connect(self._delete_all_data)
        actions_row.addWidget(delete_btn)
        actions_row.addStretch()
        actions_layout.addLayout(actions_row)

        note = QLabel(
            "\"Delete All Data\" removes your scan history, saved images, and calibration profile. "
            "Your app preferences (theme, reminders, etc.) are kept."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        actions_layout.addWidget(note)
        layout.addWidget(actions_card)

        layout.addStretch()
        self.refresh()

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("Card")
        apply_card_shadow(frame)
        v = QVBoxLayout(frame)
        t = QLabel(title)
        t.setStyleSheet("font-weight: 800; font-size: 14px;")
        v.addWidget(t)
        return frame, v

    @staticmethod
    def _stat_row(label: str, value: str) -> QHBoxLayout:
        row = QHBoxLayout()
        name = QLabel(label)
        name.setObjectName("Muted")
        row.addWidget(name)
        row.addStretch()
        val = QLabel(value)
        val.setStyleSheet("font-weight: 700;")
        row.addWidget(val)
        return row

    def refresh(self) -> None:
        while self.stats_rows_layout.count():
            item = self.stats_rows_layout.takeAt(0)
            row = item.layout()
            if row is not None:
                while row.count():
                    sub_item = row.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().hide()
                        sub_item.widget().deleteLater()
                row.deleteLater()

        stats = storage.get_data_stats()
        rows = [
            ("Scan records", str(stats["scan_count"])),
            ("Saved images", str(stats["image_count"])),
            ("Database size", _format_bytes(stats["db_size_bytes"])),
            ("Images size", _format_bytes(stats["images_size_bytes"])),
            ("Calibration", "Enabled" if stats["calibration_enabled"] else "Not set"),
        ]
        for label, value in rows:
            self.stats_rows_layout.addLayout(self._stat_row(label, value))

    def _run_offline_verification(self) -> None:
        ok, message = run_offline_verification()
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
