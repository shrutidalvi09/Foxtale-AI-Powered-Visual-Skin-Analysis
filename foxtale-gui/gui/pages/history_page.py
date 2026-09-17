"""Scan history: sortable table of past scans plus a trend-over-time chart.
Only analysis summaries are stored -- images only if the user opted in."""

from typing import Callable

from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from gui.core import storage
from gui.widgets.trend_chart import TrendChart


class HistoryPage(QWidget):
    def __init__(self, on_open_record: Callable[[str], None], show_toast: Callable[[str], None], parent=None):
        super().__init__(parent)
        self._on_open_record = on_open_record
        self._show_toast = show_toast

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        heading = QLabel("Scan History")
        heading.setObjectName("Heading")
        header_row.addWidget(heading)
        header_row.addStretch()

        export_btn = QPushButton("Export JSON")
        export_btn.setObjectName("Secondary")
        export_btn.clicked.connect(self._export_json)
        import_btn = QPushButton("Import JSON")
        import_btn.setObjectName("Secondary")
        import_btn.clicked.connect(self._import_json)
        delete_all_btn = QPushButton("Delete All History")
        delete_all_btn.setObjectName("Secondary")
        delete_all_btn.clicked.connect(self._delete_all)
        for b in (export_btn, import_btn, delete_all_btn):
            header_row.addWidget(b)
        layout.addLayout(header_row)

        note = QLabel("Only analysis summaries are stored locally — never images, unless you opt in under Settings.")
        note.setObjectName("Muted")
        layout.addWidget(note)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        # --- list tab ---
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Spots", "Redness", "Texture", "Dryness", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._open_row)
        list_layout.addWidget(self.table)
        self.tabs.addTab(list_tab, "List")

        # --- trends tab ---
        trends_tab = QWidget()
        trends_layout = QVBoxLayout(trends_tab)
        self.chart = TrendChart()
        trends_layout.addWidget(self.chart)
        self.tabs.addTab(trends_tab, "Trends")

        self.refresh()

    def refresh(self) -> None:
        records = storage.list_scans()
        self.table.setRowCount(len(records))
        self._row_ids = []

        for row, record in enumerate(records):
            self._row_ids.append(record.id)
            a = record.analysis
            values = [
                record.timestamp.replace("T", " ")[:16],
                a.acne_like_spots.level.title(),
                a.redness.level.title(),
                a.texture.level.title(),
                a.dryness_indicators.level.title(),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

            delete_btn = QPushButton("Delete")
            delete_btn.setObjectName("Secondary")
            delete_btn.clicked.connect(lambda _, sid=record.id: self._delete_one(sid))
            self.table.setCellWidget(row, 5, delete_btn)

        self.chart.plot(records)

    def _open_row(self, row: int, _col: int) -> None:
        scan_id = self._row_ids[row]
        self._on_open_record(scan_id)

    def _delete_one(self, scan_id: str) -> None:
        storage.delete_scan(scan_id)
        self._show_toast("Scan deleted.")
        self.refresh()

    def _delete_all(self) -> None:
        if QMessageBox.question(self, "Delete all history", "This removes every saved scan summary (and any saved images). Continue?") != QMessageBox.StandardButton.Yes:
            return
        storage.delete_all_scans()
        self._show_toast("All history deleted.")
        self.refresh()

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export History", "foxtale-history.json", "JSON files (*.json)")
        if not path:
            return
        count = storage.export_history_json(path)
        self._show_toast(f"Exported {count} scan(s) to JSON.")

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import History", "", "JSON files (*.json)")
        if not path:
            return
        try:
            count = storage.import_history_json(path)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self._show_toast(f"Imported {count} scan(s).")
        self.refresh()
