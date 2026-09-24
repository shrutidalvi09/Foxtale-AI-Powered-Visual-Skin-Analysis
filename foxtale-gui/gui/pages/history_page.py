"""Scan history: searchable, filterable table of past scans, a
trend-over-time chart, and a rule-based Insights summary. Only analysis
summaries are stored -- images only if the user opted in."""

import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow, icon as make_icon, icon_pixmap
from gui.core import storage
from gui.core.insights import compute_baseline, compute_insights
from gui.core.report_export import build_progress_report
from gui.core.storage import ScanRecord
from gui.theme import FOX, icon_color, muted_text_color, pill_stylesheet
from gui.widgets.history_table import CATEGORY_GETTERS, HistoryListCard, StatTile
from gui.widgets.trend_chart import TrendChart

LEVEL_FILTER_OPTIONS = ["All levels", "Minimal", "Mild", "Moderate", "Noticeable"]
TAB_ICONS = ["fa5s.list", "fa5.calendar-alt", "fa5s.chart-line", "fa5s.chart-bar", "fa5s.tasks", "fa5s.trash-restore"]
WIDE_HEADER_FROM = 1240  # page width from which the header buttons sit beside the title


class HistoryPage(QWidget):
    def __init__(self, on_open_record: Callable[[str], None], show_toast: Callable[[str], None], parent=None):
        super().__init__(parent)
        self._on_open_record = on_open_record
        self._show_toast = show_toast
        self._records: List[ScanRecord] = []
        self._filtered_records: List[ScanRecord] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(16)

        # ---- header: title + subtitle on the left, actions on the right ----
        self._header_grid = QGridLayout()
        self._header_grid.setHorizontalSpacing(16)
        self._header_grid.setVerticalSpacing(14)
        self._header_grid.setColumnStretch(0, 1)
        self._header_compact = True  # starts stacked; widens only when there is room

        title_widget = QWidget()
        title_widget.setStyleSheet("background: transparent;")
        title_col = QVBoxLayout(title_widget)
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(6)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        header_icon = QLabel()
        header_icon.setPixmap(icon_pixmap("fa5s.history", FOX, size=24))
        title_row.addWidget(header_icon)
        heading = QLabel("Scan History")
        heading.setObjectName("Heading")
        title_row.addWidget(heading)
        title_row.addStretch()
        title_col.addLayout(title_row)
        sub = QLabel("Review your past skin scans and track changes over time.")
        sub.setObjectName("SubHeading")
        sub.setWordWrap(True)
        title_col.addWidget(sub)
        self._header_grid.addWidget(title_widget, 0, 0)

        self._actions_widget = QWidget()
        self._actions_widget.setStyleSheet("background: transparent;")
        actions = QHBoxLayout(self._actions_widget)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        for text, icon_name, handler, kind in [
            ("Progress Report (PDF)", "fa5s.file-pdf", self._export_progress_report, "Secondary"),
            ("Export CSV", "fa5s.file-csv", self._export_csv, "Secondary"),
            ("Export JSON", "fa5s.file-export", self._export_json, "Secondary"),
            ("Import JSON", "fa5s.file-import", self._import_json, "Secondary"),
            ("Delete All History", "fa5s.trash-alt", self._delete_all, "DangerButton"),
        ]:
            btn = QPushButton(f"  {text}")
            btn.setIcon(make_icon(icon_name, "#be123c" if kind == "DangerButton" else icon_color("primary")))
            btn.setIconSize(QSize(15, 15))
            btn.setObjectName(kind)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(44)
            btn.setStyleSheet("padding: 0 16px; font-size: 12.5px;")
            btn.clicked.connect(handler)
            actions.addWidget(btn)
        self._header_grid.addWidget(self._actions_widget, 1, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(self._header_grid)

        # ---- search + filters ----
        filter_row = QHBoxLayout()
        filter_row.setSpacing(14)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by date, note, or keyword\u2026")
        self.search_edit.setFixedHeight(50)
        self.search_edit.addAction(
            make_icon("fa5s.search", muted_text_color()), QLineEdit.ActionPosition.TrailingPosition,
        )
        self.search_edit.textChanged.connect(self._on_filters_changed)
        filter_row.addWidget(self.search_edit, stretch=1)

        self.level_filter = QComboBox()
        self.level_filter.setFixedHeight(50)
        self.level_filter.setMinimumWidth(170)
        for option in LEVEL_FILTER_OPTIONS:
            self.level_filter.addItem(make_icon("fa5s.list", muted_text_color()), option)
        self.level_filter.currentIndexChanged.connect(self._on_filters_changed)
        filter_row.addWidget(self.level_filter)

        self.starred_only_check = QCheckBox("Starred only")
        self.starred_only_check.stateChanged.connect(self._on_filters_changed)
        filter_row.addWidget(self.starred_only_check)
        layout.addLayout(filter_row)

        # ---- at-a-glance stats ----
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.stat_tiles = {}
        for key, icon_name, label, tone in [
            ("total", "fa5.calendar-alt", "Total Scans", "peach"),
            ("starred", "fa5.star", "Starred Scans", "lavender"),
            ("month", "fa5s.chart-line", "This Month", "mint"),
            ("priority", "fa5s.chart-bar", "High Priority", "blue"),
            ("images", "fa5.image", "With Images", "yellow"),
        ]:
            tile = StatTile(icon_name, label, tone)
            stats_row.addWidget(tile, 1)
            self.stat_tiles[key] = tile
        layout.addLayout(stats_row)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("PageTabs")
        layout.addWidget(self.tabs, stretch=1)

        # --- list tab ---
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)
        list_layout.setContentsMargins(0, 10, 0, 0)
        self.list_card = HistoryListCard()
        self.list_card.open_record.connect(self._on_open_record)
        self.list_card.toggle_star.connect(self._toggle_star)
        self.list_card.delete_scan.connect(self._delete_one)
        list_layout.addWidget(self.list_card)
        self.tabs.addTab(list_tab, "List")

        # --- calendar tab ---
        calendar_tab = QWidget()
        calendar_layout = QHBoxLayout(calendar_tab)
        self.calendar = QCalendarWidget()
        self.calendar.clicked.connect(self._on_calendar_date_clicked)
        calendar_layout.addWidget(self.calendar, stretch=2)

        day_container = QFrame()
        day_container.setObjectName("Card")
        apply_card_shadow(day_container)
        self.calendar_day_layout = QVBoxLayout(day_container)
        self.calendar_day_title = QLabel("Select a date")
        self.calendar_day_title.setObjectName("CardTitle")
        self.calendar_day_layout.addWidget(self.calendar_day_title)
        self.calendar_day_rows = QVBoxLayout()
        self.calendar_day_layout.addLayout(self.calendar_day_rows)
        self.calendar_day_layout.addStretch()
        calendar_layout.addWidget(day_container, stretch=1)
        self.tabs.addTab(calendar_tab, "Calendar")

        # --- trends tab ---
        trends_tab = QWidget()
        trends_layout = QVBoxLayout(trends_tab)
        self.chart = TrendChart()
        trends_layout.addWidget(self.chart)
        self.tabs.addTab(trends_tab, "Trends")

        # --- insights tab ---
        insights_tab = QWidget()
        self.insights_layout = QVBoxLayout(insights_tab)
        self.insights_layout.setSpacing(12)
        self.insights_layout.addStretch()
        self.tabs.addTab(insights_tab, "Insights")

        # --- routine tab ---
        routine_tab = QWidget()
        routine_layout = QVBoxLayout(routine_tab)
        routine_layout.setSpacing(12)

        today_card = QFrame()
        today_card.setObjectName("Card")
        apply_card_shadow(today_card)
        today_v = QVBoxLayout(today_card)
        today_title = QLabel("Today's Routine")
        today_title.setObjectName("CardTitle")
        today_v.addWidget(today_title)
        today_note = QLabel("What did you use today? Independent of scanning — helps spot patterns over time.")
        today_note.setObjectName("Muted")
        today_note.setWordWrap(True)
        today_v.addWidget(today_note)
        self.routine_today_checks: dict[str, QCheckBox] = {}
        today_row = QHBoxLayout()
        for item in storage.ROUTINE_OPTIONS:
            cb = QCheckBox(item)
            cb.stateChanged.connect(self._on_routine_today_changed)
            today_row.addWidget(cb)
            self.routine_today_checks[item] = cb
        today_row.addStretch()
        today_v.addLayout(today_row)
        routine_layout.addWidget(today_card)

        streak_card = QFrame()
        streak_card.setObjectName("Card")
        apply_card_shadow(streak_card)
        streak_v = QVBoxLayout(streak_card)
        streak_title = QLabel("Routine Streaks")
        streak_title.setObjectName("CardTitle")
        streak_v.addWidget(streak_title)
        self.routine_streak_layout = QVBoxLayout()
        streak_v.addLayout(self.routine_streak_layout)
        routine_layout.addWidget(streak_card)

        log_card = QFrame()
        log_card.setObjectName("Card")
        apply_card_shadow(log_card)
        log_v = QVBoxLayout(log_card)
        log_title = QLabel("Recent Log")
        log_title.setObjectName("CardTitle")
        log_v.addWidget(log_title)
        self.routine_log_layout = QVBoxLayout()
        log_v.addLayout(self.routine_log_layout)
        routine_layout.addWidget(log_card)

        routine_layout.addStretch()
        self.tabs.addTab(routine_tab, "Routine")

        # --- recently deleted tab ---
        trash_tab = QWidget()
        trash_layout = QVBoxLayout(trash_tab)
        trash_note = QLabel(
            f"Deleted scans stay here for {storage.TRASH_RETENTION_DAYS} days before being "
            "permanently removed."
        )
        trash_note.setObjectName("Muted")
        trash_note.setWordWrap(True)
        trash_layout.addWidget(trash_note)
        self.trash_rows_layout = QVBoxLayout()
        trash_layout.addLayout(self.trash_rows_layout)
        trash_layout.addStretch()
        self.tabs.addTab(trash_tab, "Recently Deleted")

        self.tabs.tabBar().setIconSize(QSize(16, 16))
        self.tabs.currentChanged.connect(self._refresh_tab_icons)
        self._refresh_tab_icons()

        privacy_note = QLabel(
            "Only analysis summaries are stored locally \u2014 never images, unless you opt in under Settings."
        )
        privacy_note.setObjectName("Muted")
        layout.addWidget(privacy_note)

        self.refresh()

    def _refresh_tab_icons(self, *_args) -> None:
        current = self.tabs.currentIndex()
        for i, name in enumerate(TAB_ICONS[: self.tabs.count()]):
            self.tabs.setTabIcon(i, make_icon(name, FOX if i == current else muted_text_color()))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reflow_header()

    def _reflow_header(self) -> None:
        compact = self.width() < WIDE_HEADER_FROM
        if compact == self._header_compact:
            return
        self._header_compact = compact
        self._header_grid.removeWidget(self._actions_widget)
        if compact:
            self._header_grid.addWidget(self._actions_widget, 1, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            self._header_grid.addWidget(
                self._actions_widget, 0, 1, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            )

    def refresh(self) -> None:
        storage.purge_expired_trash()
        self._records = storage.list_scans()
        self._render_stats()
        self._apply_filters()
        self.chart.plot(self._records)
        self._render_insights()
        self._mark_calendar_dates()
        self._render_routine()
        self._render_trash()

    def _render_trash(self) -> None:
        while self.trash_rows_layout.count():
            item = self.trash_rows_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        trashed = storage.list_trashed_scans()
        if not trashed:
            empty = QLabel("Recently Deleted is empty.")
            empty.setObjectName("Muted")
            self.trash_rows_layout.addWidget(empty)
            return

        for record in trashed:
            row = QFrame()
            row.setObjectName("Card")
            apply_card_shadow(row)
            h = QHBoxLayout(row)
            deleted_dt = datetime.fromisoformat(record.deleted_at)
            days_left = max(0, storage.TRASH_RETENTION_DAYS - (datetime.now() - deleted_dt).days)
            when = datetime.fromisoformat(record.timestamp).strftime("%b %d, %Y · %I:%M %p")
            label = QLabel(f"{when}  —  {days_left} day(s) left")
            h.addWidget(label, stretch=1)
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("Secondary")
            restore_btn.clicked.connect(lambda _, sid=record.id: self._restore_scan(sid))
            h.addWidget(restore_btn)
            forever_btn = QPushButton("Delete Forever")
            forever_btn.setObjectName("Secondary")
            forever_btn.clicked.connect(lambda _, sid=record.id: self._delete_forever(sid))
            h.addWidget(forever_btn)
            self.trash_rows_layout.addWidget(row)

    def _restore_scan(self, scan_id: str) -> None:
        storage.restore_scan(scan_id)
        self._show_toast("Scan restored.")
        self.refresh()

    def _delete_forever(self, scan_id: str) -> None:
        if QMessageBox.question(
            self, "Delete forever", "This permanently removes this scan and its image. Continue?",
        ) != QMessageBox.StandardButton.Yes:
            return
        storage.permanently_delete_scan(scan_id)
        self._show_toast("Scan permanently deleted.")
        self.refresh()

    def _on_routine_today_changed(self, *_args) -> None:
        today = date.today().isoformat()
        selected = [item for item, cb in self.routine_today_checks.items() if cb.isChecked()]
        storage.set_daily_routine(today, selected)
        self._render_routine_streaks()
        self._render_routine_log()

    def _render_routine(self) -> None:
        today = date.today().isoformat()
        todays_items = set(storage.get_daily_routine(today))
        for item, cb in self.routine_today_checks.items():
            cb.blockSignals(True)
            cb.setChecked(item in todays_items)
            cb.blockSignals(False)
        self._render_routine_streaks()
        self._render_routine_log()

    def _render_routine_streaks(self) -> None:
        while self.routine_streak_layout.count():
            item = self.routine_streak_layout.takeAt(0)
            row = item.layout()
            if row is not None:
                while row.count():
                    sub_item = row.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().hide()
                        sub_item.widget().deleteLater()
                row.deleteLater()
            elif item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        for name in storage.ROUTINE_OPTIONS:
            streak = storage.routine_streak(name)
            row = QHBoxLayout()
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap("fa5s.fire", icon_color("accent"), size=13))
            row.addWidget(icon_label)
            label = QLabel(name)
            row.addWidget(label, stretch=1)
            val = QLabel(f"{streak}-day streak" if streak else "No current streak")
            if streak:
                val.setStyleSheet("font-weight: 700;")
            else:
                val.setObjectName("Muted")
            row.addWidget(val)
            self.routine_streak_layout.addLayout(row)

    def _render_routine_log(self) -> None:
        while self.routine_log_layout.count():
            item = self.routine_log_layout.takeAt(0)
            row = item.layout()
            if row is not None:
                while row.count():
                    sub_item = row.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().hide()
                        sub_item.widget().deleteLater()
                row.deleteLater()
            elif item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        logs = storage.list_routine_logs(14)
        if not logs:
            empty = QLabel("No routine entries yet.")
            empty.setObjectName("Muted")
            self.routine_log_layout.addWidget(empty)
            return

        for date_str, items in logs:
            row = QHBoxLayout()
            day_label = QLabel(datetime.fromisoformat(date_str).strftime("%b %d"))
            day_label.setObjectName("Muted")
            day_label.setFixedWidth(60)
            row.addWidget(day_label)
            text = QLabel(", ".join(items) if items else "—")
            row.addWidget(text, stretch=1)
            self.routine_log_layout.addLayout(row)

    def _mark_calendar_dates(self) -> None:
        # setDateTextFormat() has no bulk-clear call, so explicitly reset
        # whatever we marked last time before applying the new set --
        # otherwise a date with all its scans deleted stays highlighted.
        blank_format = QTextCharFormat()
        for qdate in getattr(self, "_marked_calendar_dates", []):
            self.calendar.setDateTextFormat(qdate, blank_format)

        marked_format = QTextCharFormat()
        marked_format.setBackground(QColor(icon_color("accent")))
        marked_format.setForeground(QColor("white"))
        seen_dates = set()
        marked_qdates = []
        for record in self._records:
            day = datetime.fromisoformat(record.timestamp).date()
            if day in seen_dates:
                continue
            seen_dates.add(day)
            qdate = QDate(day.year, day.month, day.day)
            self.calendar.setDateTextFormat(qdate, marked_format)
            marked_qdates.append(qdate)
        self._marked_calendar_dates = marked_qdates

    def _on_calendar_date_clicked(self, qdate: QDate) -> None:
        target = qdate.toPython()
        day_records = [r for r in self._records if datetime.fromisoformat(r.timestamp).date() == target]

        while self.calendar_day_rows.count():
            item = self.calendar_day_rows.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        self.calendar_day_title.setText(target.strftime("%B %d, %Y"))
        if not day_records:
            empty = QLabel("No scans on this date.")
            empty.setObjectName("Muted")
            self.calendar_day_rows.addWidget(empty)
            return

        for record in day_records:
            btn = QPushButton(datetime.fromisoformat(record.timestamp).strftime("%I:%M %p"))
            btn.setObjectName("Secondary")
            btn.clicked.connect(lambda _, sid=record.id: self._on_open_record(sid))
            self.calendar_day_rows.addWidget(btn)

    def _render_insights(self) -> None:
        while self.insights_layout.count():
            item = self.insights_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        result = compute_insights(self._records)

        headline_card = QFrame()
        headline_card.setObjectName("Card")
        apply_card_shadow(headline_card)
        hv = QVBoxLayout(headline_card)
        headline_label = QLabel(result.headline)
        headline_label.setWordWrap(True)
        headline_label.setObjectName("CardTitle")
        hv.addWidget(headline_label)
        if result.total_scans:
            stats_bits = [f"{result.total_scans} scan(s)", f"{result.span_days} day span"]
            if result.avg_days_between_scans:
                stats_bits.append(f"~{result.avg_days_between_scans:.1f} days between scans")
            stats_label = QLabel("  ·  ".join(stats_bits))
            stats_label.setObjectName("Muted")
            hv.addWidget(stats_label)
        self.insights_layout.addWidget(headline_card)

        if result.trends:
            trend_card = QFrame()
            trend_card.setObjectName("Card")
            apply_card_shadow(trend_card)
            tv = QVBoxLayout(trend_card)
            title = QLabel("Per-category trend (first scans vs. most recent)")
            title.setObjectName("CardTitle")
            tv.addWidget(title)
            for t in result.trends:
                row = QHBoxLayout()
                icon_name = {"improved": "fa5s.arrow-down", "worsened": "fa5s.arrow-up", "stable": "fa5s.minus"}[t.direction]
                color_kind = {"improved": "success", "worsened": "warning", "stable": "accent"}[t.direction]
                icon_label = QLabel()
                icon_label.setPixmap(icon_pixmap(icon_name, icon_color(color_kind), size=12))
                row.addWidget(icon_label)
                label = QLabel(f"{t.label}: {t.early_level.title()} → {t.recent_level.title()} ({t.direction})")
                row.addWidget(label, stretch=1)
                tv.addLayout(row)
            self.insights_layout.addWidget(trend_card)

        if result.total_scans:
            stats_card = QFrame()
            stats_card.setObjectName("Card")
            apply_card_shadow(stats_card)
            sv = QVBoxLayout(stats_card)
            stats_title = QLabel("More Stats")
            stats_title.setObjectName("CardTitle")
            sv.addWidget(stats_title)
            advanced_rows = [
                ("Scans analysed", str(result.total_scans)),
                ("Tracking period", f"{result.span_days} day(s)"),
                ("Current streak", f"{result.longest_streak} scan(s)"),
            ]
            if result.most_frequent_region:
                advanced_rows.append(("Most-flagged region", result.most_frequent_region))
            if result.most_frequent_category:
                advanced_rows.append(("Most-flagged category", result.most_frequent_category))
            if result.best_scan_date:
                best_when = datetime.fromisoformat(result.best_scan_date).strftime("%b %d, %Y")
                advanced_rows.append(("Best scan so far", best_when))
            for label, value in advanced_rows:
                row = QHBoxLayout()
                name = QLabel(label)
                name.setObjectName("Muted")
                row.addWidget(name)
                row.addStretch()
                val = QLabel(value)
                val.setStyleSheet("font-weight: 700;")
                row.addWidget(val)
                sv.addLayout(row)
            self.insights_layout.addWidget(stats_card)

        baseline_card = QFrame()
        baseline_card.setObjectName("Card")
        apply_card_shadow(baseline_card)
        bv = QVBoxLayout(baseline_card)
        baseline_title = QLabel("Your Personal Baseline")
        baseline_title.setObjectName("CardTitle")
        bv.addWidget(baseline_title)
        baseline_note = QLabel("Your most common visible level per category, across your own history.")
        baseline_note.setObjectName("Muted")
        baseline_note.setWordWrap(True)
        bv.addWidget(baseline_note)
        baseline = compute_baseline(self._records)
        for label, level in baseline.items():
            row = QHBoxLayout()
            name = QLabel(label)
            row.addWidget(name)
            row.addStretch()
            pill = QLabel(level.title())
            pill.setStyleSheet(pill_stylesheet(level))
            row.addWidget(pill)
            bv.addLayout(row)
        self.insights_layout.addWidget(baseline_card)

        self.insights_layout.addStretch()

    def _render_stats(self) -> None:
        now = datetime.now()
        records = self._records

        def in_this_month(record: ScanRecord) -> bool:
            when = datetime.fromisoformat(record.timestamp)
            return when.year == now.year and when.month == now.month

        def is_high_priority(record: ScanRecord) -> bool:
            return any(getter(record.analysis).level == "noticeable" for getter in CATEGORY_GETTERS.values())

        self.stat_tiles["total"].set_value(len(records))
        self.stat_tiles["starred"].set_value(sum(1 for r in records if r.starred))
        self.stat_tiles["month"].set_value(sum(1 for r in records if in_this_month(r)))
        self.stat_tiles["priority"].set_value(sum(1 for r in records if is_high_priority(r)))
        self.stat_tiles["images"].set_value(sum(1 for r in records if r.image_path))

    def _on_filters_changed(self, *_args) -> None:
        self.list_card.reset_page()
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self.search_edit.text().strip().lower()
        level = self.level_filter.currentText()
        starred_only = self.starred_only_check.isChecked()

        filtered = []
        for r in self._records:
            if starred_only and not r.starred:
                continue
            levels = {getter(r.analysis).level for getter in CATEGORY_GETTERS.values()}
            if level != "All levels" and level.lower() not in levels:
                continue
            if query:
                when = datetime.fromisoformat(r.timestamp)
                haystack = " ".join([
                    r.timestamp.lower(), when.strftime("%b %d, %Y %I:%M %p").lower(),
                    when.strftime("%B").lower(), r.note.lower(), " ".join(sorted(levels)),
                ])
                if query not in haystack:
                    continue
            filtered.append(r)

        self._filtered_records = filtered
        message = (
            "No scans yet \u2014 start a scan and it will appear here."
            if not self._records else "No scans match your filters yet."
        )
        self.list_card.set_records(filtered, message)

    def _toggle_star(self, scan_id: str) -> None:
        current = next((r for r in self._records if r.id == scan_id), None)
        if current is None:
            return
        storage.set_scan_starred(scan_id, not current.starred)
        self.refresh()

    def _delete_one(self, scan_id: str) -> None:
        storage.delete_scan(scan_id)
        self._show_toast("Moved to Recently Deleted.")
        self.refresh()

    def _delete_all(self) -> None:
        if QMessageBox.question(self, "Delete all history", "This removes every saved scan summary (and any saved images). Continue?") != QMessageBox.StandardButton.Yes:
            return
        storage.delete_all_scans()
        self._show_toast("All history deleted.")
        self.refresh()

    def _export_progress_report(self) -> None:
        records = self._filtered_records or self._records
        if not records:
            self._show_toast("No scans to include in a progress report yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Progress Report", "foxtale-progress-report.pdf", "PDF files (*.pdf)"
        )
        if not path:
            return

        chart_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                chart_path = tmp.name
            self.chart.fig.savefig(chart_path, dpi=150, bbox_inches="tight")
            headline = compute_insights(records).headline
            build_progress_report(path, records, chart_image_path=chart_path, headline=headline)
        finally:
            if chart_path:
                Path(chart_path).unlink(missing_ok=True)

        self._show_toast(f"Progress report exported ({len(records)} scan(s)).")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export History as CSV", "foxtale-history.csv", "CSV files (*.csv)")
        if not path:
            return
        count = storage.export_history_csv(path)
        self._show_toast(f"Exported {count} scan(s) to CSV.")

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
