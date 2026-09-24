"""Results dashboard: summary cards, clickable face markers, region
breakdown, recommendations, and export actions."""

from datetime import datetime
from typing import Callable, Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from engine.schemas import RegionObservation
from gui.assets import apply_card_shadow, icon_pixmap
from gui.assets import icon as make_icon
from gui.core import storage
from gui.core.insights import compute_baseline
from gui.core.recommendations import build_recommendations
from gui.core.report_export import build_pdf_report, build_summary_card_image, save_annotated_image
from gui.core.storage import ScanRecord
from gui.theme import CATEGORY_QCOLOR, icon_color, muted_text_color
from gui.widgets.analysis_card import AnalysisCard
from gui.widgets.disclaimer import DisclaimerBanner
from gui.widgets.face_report import FaceReportView
from gui.widgets.quality_card import QualityCard


class ResultsPage(QWidget):
    def __init__(
        self,
        on_new_scan: Callable[[], None],
        on_delete: Callable[[str], None],
        show_toast: Callable[[str], None],
        parent=None,
    ):
        super().__init__(parent)
        self._on_new_scan = on_new_scan
        self._on_delete = on_delete
        self._show_toast = show_toast
        self._record: Optional[ScanRecord] = None
        self._image: Optional[np.ndarray] = None
        self._persisted = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self.layout_ = QVBoxLayout(content)
        self.layout_.setContentsMargins(36, 28, 36, 28)
        self.layout_.setSpacing(16)

        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        heading = QLabel("Your Skin Analysis")
        heading.setObjectName("Heading")
        title_col.addWidget(heading)
        sub = QLabel("AI-powered visual skin observations")
        sub.setObjectName("SubHeading")
        title_col.addWidget(sub)
        header_row.addLayout(title_col)
        header_row.addStretch()

        self.timestamp_label = QLabel("")
        self.timestamp_label.setObjectName("Muted")
        header_row.addWidget(self.timestamp_label)

        self.prev_btn = QPushButton()
        self.prev_btn.setObjectName("Secondary")
        self.prev_btn.setFixedWidth(40)
        self.prev_btn.setToolTip("Older scan")
        self.prev_btn.setIcon(make_icon("fa5s.step-backward", icon_color("primary")))
        self.prev_btn.clicked.connect(lambda: self._go_relative(1))
        self.prev_btn.setEnabled(False)
        header_row.addWidget(self.prev_btn)

        self.next_btn = QPushButton()
        self.next_btn.setObjectName("Secondary")
        self.next_btn.setFixedWidth(40)
        self.next_btn.setToolTip("Newer scan")
        self.next_btn.setIcon(make_icon("fa5s.step-forward", icon_color("primary")))
        self.next_btn.clicked.connect(lambda: self._go_relative(-1))
        self.next_btn.setEnabled(False)
        header_row.addWidget(self.next_btn)

        self.star_btn = QPushButton()
        self.star_btn.setObjectName("Secondary")
        self.star_btn.setFixedWidth(40)
        self.star_btn.setToolTip("Star this scan")
        self.star_btn.clicked.connect(self._toggle_star)
        self.star_btn.setIcon(make_icon("fa5.star", icon_color("primary")))
        header_row.addWidget(self.star_btn)
        self.layout_.addLayout(header_row)

        self.layout_.addWidget(DisclaimerBanner())

        self.cards_row = QHBoxLayout()
        self.layout_.addLayout(self.cards_row)

        heatmap_row = QHBoxLayout()
        self.heatmap_btn = QPushButton(" Heatmap")
        self.heatmap_btn.setIcon(make_icon("fa5s.fire", icon_color("primary")))
        self.heatmap_btn.setObjectName("Secondary")
        self.heatmap_btn.setCheckable(True)
        self.heatmap_btn.toggled.connect(self._update_heatmap)
        heatmap_row.addWidget(self.heatmap_btn)
        self.heatmap_category_combo = QComboBox()
        self.heatmap_category_combo.addItem("All categories", None)
        for category in ("Acne-like spots", "Redness", "Texture", "Dryness indicators"):
            self.heatmap_category_combo.addItem(category, category)
        self.heatmap_category_combo.currentIndexChanged.connect(self._update_heatmap)
        heatmap_row.addWidget(self.heatmap_category_combo)
        heatmap_row.addStretch()
        self.layout_.addLayout(heatmap_row)

        split = QHBoxLayout()
        self.face_report = FaceReportView()
        apply_card_shadow(self.face_report)
        self.face_report.marker_clicked.connect(self._on_marker_clicked)
        split.addWidget(self.face_report, stretch=1)

        right_col = QVBoxLayout()
        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("Card")
        apply_card_shadow(self.detail_panel)
        self.detail_layout = QVBoxLayout(self.detail_panel)
        self.detail_title = QLabel("Visible observation")
        self.detail_title.setObjectName("CardTitle")
        self.detail_body = QLabel("Click a marker on the photo to see details.")
        self.detail_body.setWordWrap(True)
        self.detail_layout.addWidget(self.detail_title)
        self.detail_layout.addWidget(self.detail_body)
        right_col.addWidget(self.detail_panel)

        self.regions_panel = QFrame()
        self.regions_panel.setObjectName("Card")
        apply_card_shadow(self.regions_panel)
        self.regions_layout = QVBoxLayout(self.regions_panel)
        regions_title = QLabel("Region Breakdown")
        regions_title.setObjectName("CardTitle")
        self.regions_layout.addWidget(regions_title)
        self.regions_body = QVBoxLayout()
        self.regions_layout.addLayout(self.regions_body)
        right_col.addWidget(self.regions_panel, stretch=1)

        split.addLayout(right_col, stretch=1)
        self.layout_.addLayout(split)

        self.notes_panel = QFrame()
        self.notes_panel.setObjectName("Card")
        apply_card_shadow(self.notes_panel)
        notes_layout = QVBoxLayout(self.notes_panel)
        notes_title = QLabel("Notes")
        notes_title.setObjectName("CardTitle")
        notes_layout.addWidget(notes_title)
        notes_row = QHBoxLayout()
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Add a personal note (e.g. new product, routine change)…")
        self.notes_edit.returnPressed.connect(self._save_note)
        notes_row.addWidget(self.notes_edit, stretch=1)
        self.notes_save_btn = QPushButton("Save")
        self.notes_save_btn.setObjectName("Secondary")
        self.notes_save_btn.clicked.connect(self._save_note)
        notes_row.addWidget(self.notes_save_btn)
        notes_layout.addLayout(notes_row)
        self.notes_hint = QLabel("")
        self.notes_hint.setObjectName("Muted")
        self.notes_hint.setWordWrap(True)
        notes_layout.addWidget(self.notes_hint)
        self.layout_.addWidget(self.notes_panel)

        self.journal_panel = QFrame()
        self.journal_panel.setObjectName("Card")
        apply_card_shadow(self.journal_panel)
        journal_layout = QVBoxLayout(self.journal_panel)
        journal_title = QLabel("Scan Journal")
        journal_title.setObjectName("CardTitle")
        journal_layout.addWidget(journal_title)

        routine_label = QLabel("Routine")
        routine_label.setObjectName("Muted")
        journal_layout.addWidget(routine_label)
        routine_row = QHBoxLayout()
        self.routine_checks: dict[str, QCheckBox] = {}
        for option in storage.ROUTINE_OPTIONS:
            box = QCheckBox(option)
            box.stateChanged.connect(self._save_journal)
            routine_row.addWidget(box)
            self.routine_checks[option] = box
        routine_row.addStretch()
        journal_layout.addLayout(routine_row)

        env_label = QLabel("Environment")
        env_label.setObjectName("Muted")
        journal_layout.addWidget(env_label)
        env_row = QHBoxLayout()
        self.environment_checks: dict[str, QCheckBox] = {}
        for option in storage.ENVIRONMENT_OPTIONS:
            box = QCheckBox(option)
            box.stateChanged.connect(self._save_journal)
            env_row.addWidget(box)
            self.environment_checks[option] = box
        env_row.addStretch()
        journal_layout.addLayout(env_row)
        self.layout_.addWidget(self.journal_panel)

        self.reco_panel = QFrame()
        self.reco_panel.setObjectName("Card")
        apply_card_shadow(self.reco_panel)
        reco_layout = QVBoxLayout(self.reco_panel)
        reco_title = QLabel("Recommendations")
        reco_title.setObjectName("CardTitle")
        reco_layout.addWidget(reco_title)
        self.reco_body = QVBoxLayout()
        reco_layout.addLayout(self.reco_body)
        self.layout_.addWidget(self.reco_panel)

        actions = QHBoxLayout()
        privacy_icon = QLabel()
        privacy_icon.setPixmap(icon_pixmap("fa5s.lock", icon_color("accent"), size=13))
        actions.addWidget(privacy_icon)
        privacy_label = QLabel("Your face image is processed only for this analysis.")
        privacy_label.setObjectName("Muted")
        actions.addWidget(privacy_label)
        actions.addStretch()

        export_pdf_btn = QPushButton(" Export PDF")
        export_pdf_btn.setIcon(make_icon("fa5s.file-pdf", icon_color("primary")))
        export_pdf_btn.setObjectName("Secondary")
        export_pdf_btn.clicked.connect(self._export_pdf)
        export_png_btn = QPushButton(" Export Annotated Image")
        export_png_btn.setIcon(make_icon("fa5s.file-export", icon_color("primary")))
        export_png_btn.setObjectName("Secondary")
        export_png_btn.clicked.connect(self._export_png)
        export_share_btn = QPushButton(" Export Share Card")
        export_share_btn.setIcon(make_icon("fa5s.share-square", icon_color("primary")))
        export_share_btn.setObjectName("Secondary")
        export_share_btn.setToolTip("A summary card with levels only — no photo — for sharing.")
        export_share_btn.clicked.connect(self._export_share_card)
        delete_btn = QPushButton(" Delete Scan")
        delete_btn.setIcon(make_icon("fa5s.trash-alt", icon_color("primary")))
        delete_btn.setObjectName("Secondary")
        delete_btn.clicked.connect(self._delete)
        new_scan_btn = QPushButton(" New Scan")
        new_scan_btn.setIcon(make_icon("fa5s.camera", icon_color("on_primary")))
        new_scan_btn.setObjectName("Primary")
        new_scan_btn.clicked.connect(self._on_new_scan)

        for b in (export_pdf_btn, export_png_btn, export_share_btn, delete_btn, new_scan_btn):
            actions.addWidget(b)
        self.layout_.addLayout(actions)

    def show_record(self, record: ScanRecord, image: Optional[np.ndarray]) -> None:
        self._record = record
        self._image = image
        self._persisted = storage.get_scan(record.id) is not None

        self.timestamp_label.setText(datetime.fromisoformat(record.timestamp).strftime("%b %d, %Y · %I:%M %p"))
        self._update_star_button()
        self._update_nav_buttons()

        self.notes_edit.setText(record.note)
        self.notes_edit.setEnabled(self._persisted)
        self.notes_save_btn.setEnabled(self._persisted)
        self.star_btn.setEnabled(self._persisted)
        self.notes_hint.setText(
            "" if self._persisted else
            "Notes and starring are available for saved scans — enable \"Save scan history\" in Settings."
        )

        all_journal_checks = list(self.routine_checks.values()) + list(self.environment_checks.values())
        for box in all_journal_checks:
            box.blockSignals(True)
        for option, box in self.routine_checks.items():
            box.setChecked(option in record.journal.get("routine", []))
            box.setEnabled(self._persisted)
        for option, box in self.environment_checks.items():
            box.setChecked(option in record.journal.get("environment", []))
            box.setEnabled(self._persisted)
        for box in all_journal_checks:
            box.blockSignals(False)

        while self.cards_row.count():
            item = self.cards_row.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        analysis = record.analysis
        acne_count = analysis.acne_like_spots.count or len(
            [r for r in record.regions if r.category == "Acne-like spots"]
        )
        redness_count = len([r for r in record.regions if r.category == "Redness"])
        dry_count = len([r for r in record.regions if r.category == "Dryness indicators"])

        baseline = compute_baseline(storage.list_scans()) if self._persisted else {}

        self.cards_row.addWidget(AnalysisCard(
            "Acne-like Spots", analysis.acne_like_spots, f"{acne_count} area(s) flagged",
            baseline_level=baseline.get("Acne-like spots"),
            category_key="Acne-like spots", regions=record.regions,
        ))
        self.cards_row.addWidget(AnalysisCard(
            "Visible Redness", analysis.redness, f"{redness_count} area(s) found",
            baseline_level=baseline.get("Redness"),
            category_key="Redness", regions=record.regions,
        ))
        self.cards_row.addWidget(AnalysisCard(
            "Skin Texture", analysis.texture, "Facial areas assessed",
            baseline_level=baseline.get("Texture"),
            category_key="Texture", regions=record.regions,
        ))
        self.cards_row.addWidget(AnalysisCard(
            "Dryness Indicators", analysis.dryness_indicators, f"{dry_count} area(s) found",
            baseline_level=baseline.get("Dryness indicators"),
            category_key="Dryness indicators", regions=record.regions,
        ))
        if record.quality:
            self.cards_row.addWidget(QualityCard(record.quality))

        self.face_report.set_image(image, record.regions)
        self.detail_body.setText("Click a marker on the photo to see details.")

        while self.regions_body.count():
            item = self.regions_body.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        grouped: dict[str, list[RegionObservation]] = {}
        for r in record.regions:
            grouped.setdefault(r.region, []).append(r)

        if not grouped:
            lbl = QLabel("No notable visible observations in any region.")
            lbl.setObjectName("SubHeading")
            self.regions_body.addWidget(lbl)
        else:
            for region, obs_list in grouped.items():
                region_label = QLabel(region)
                region_label.setStyleSheet(f"font-weight: 700; font-size: 10.5px; color: {muted_text_color()};")
                self.regions_body.addWidget(region_label)
                for o in obs_list:
                    color = CATEGORY_QCOLOR.get(o.category, "#3b8dff")
                    item_label = QLabel(f"<span style='color:{color};'>●</span>  {o.observation}")
                    self.regions_body.addWidget(item_label)

        while self.reco_body.count():
            item = self.reco_body.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        for tip in build_recommendations(analysis):
            lbl = QLabel(f"• {tip}")
            lbl.setWordWrap(True)
            self.reco_body.addWidget(lbl)

    def _on_marker_clicked(self, region: RegionObservation) -> None:
        self.detail_body.setText(
            f"<b>Area:</b> {region.region}<br>"
            f"<b>Observation:</b> {region.observation}<br>"
            f"<b>Confidence:</b> {int(region.confidence * 100)}%<br><br>"
            f"<span style='color:{muted_text_color()}; font-size: 10.5px;'>This is a visual observation "
            "and does not establish a medical diagnosis.</span>"
        )

    def _update_heatmap(self, *_args) -> None:
        self.face_report.set_heatmap_mode(
            self.heatmap_btn.isChecked(), self.heatmap_category_combo.currentData(),
        )

    def _export_pdf(self) -> None:
        if not self._record:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF Report", "foxtale-report.pdf", "PDF files (*.pdf)")
        if not path:
            return
        annotated_path = None
        if self._image is not None:
            annotated_path = path.rsplit(".", 1)[0] + "_annotated_tmp.jpg"
            save_annotated_image(self._image, self._record.regions, annotated_path)
        build_pdf_report(
            path,
            self._record.analysis,
            self._record.regions,
            build_recommendations(self._record.analysis),
            annotated_image_path=annotated_path,
            timestamp=datetime.fromisoformat(self._record.timestamp).strftime("%Y-%m-%d %H:%M"),
        )
        self._show_toast("PDF report exported.")

    def _export_png(self) -> None:
        if not self._record or self._image is None:
            self._show_toast("No captured image available to export for this scan.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Annotated Image", "foxtale-scan.png", "PNG files (*.png)")
        if not path:
            return
        save_annotated_image(self._image, self._record.regions, path)
        self._show_toast("Annotated image exported.")

    def _export_share_card(self) -> None:
        if not self._record:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Share Card", "foxtale-summary.png", "PNG files (*.png)")
        if not path:
            return
        build_summary_card_image(path, self._record)
        self._show_toast("Share card exported — no photo included.")

    def _delete(self) -> None:
        if self._record:
            self._on_delete(self._record.id)

    def _update_star_button(self) -> None:
        starred = self._record.starred if self._record else False
        icon_name = "fa5s.star" if starred else "fa5.star"
        self.star_btn.setIcon(make_icon(icon_name, icon_color("primary")))
        self.star_btn.setToolTip("Unstar this scan" if starred else "Star this scan")

    def _update_nav_buttons(self) -> None:
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        if not self._record or not self._persisted:
            return
        all_scans = storage.list_scans()  # newest first
        ids = [r.id for r in all_scans]
        if self._record.id not in ids:
            return
        idx = ids.index(self._record.id)
        self.prev_btn.setEnabled(idx + 1 < len(ids))  # an older scan exists
        self.next_btn.setEnabled(idx - 1 >= 0)  # a newer scan exists

    def _go_relative(self, offset: int) -> None:
        if not self._record:
            return
        all_scans = storage.list_scans()
        ids = [r.id for r in all_scans]
        if self._record.id not in ids:
            return
        idx = ids.index(self._record.id) + offset
        if not (0 <= idx < len(all_scans)):
            return
        target = all_scans[idx]
        image = cv2.imread(target.image_path) if target.image_path else None
        self.show_record(target, image)

    def _toggle_star(self) -> None:
        if not self._record or not self._persisted:
            return
        self._record.starred = not self._record.starred
        storage.set_scan_starred(self._record.id, self._record.starred)
        self._update_star_button()
        self._show_toast("Scan starred." if self._record.starred else "Scan unstarred.")

    def _save_note(self) -> None:
        if not self._record or not self._persisted:
            return
        note = self.notes_edit.text().strip()
        self._record.note = note
        storage.set_scan_note(self._record.id, note)
        self._show_toast("Note saved.")

    def _save_journal(self) -> None:
        if not self._record or not self._persisted:
            return
        routine = [opt for opt, box in self.routine_checks.items() if box.isChecked()]
        environment = [opt for opt, box in self.environment_checks.items() if box.isChecked()]
        self._record.journal = {"routine": routine, "environment": environment}
        storage.set_scan_journal(self._record.id, routine, environment)
