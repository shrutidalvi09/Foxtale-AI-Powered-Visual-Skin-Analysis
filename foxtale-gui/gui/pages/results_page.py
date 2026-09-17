"""Results dashboard: summary cards, clickable face markers, region
breakdown, recommendations, and export actions."""

from datetime import datetime
from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from engine.schemas import RegionObservation
from gui.assets import apply_card_shadow
from gui.core import storage
from gui.core.recommendations import build_recommendations
from gui.core.report_export import build_pdf_report, save_annotated_image
from gui.core.storage import ScanRecord
from gui.theme import CATEGORY_QCOLOR
from gui.widgets.analysis_card import AnalysisCard
from gui.widgets.disclaimer import DisclaimerBanner
from gui.widgets.face_report import FaceReportView


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

        heading = QLabel("Your Skin Analysis")
        heading.setObjectName("Heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_.addWidget(heading)

        sub = QLabel("AI-powered visual skin observations")
        sub.setObjectName("SubHeading")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_.addWidget(sub)

        self.layout_.addWidget(DisclaimerBanner())

        self.cards_row = QHBoxLayout()
        self.layout_.addLayout(self.cards_row)

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
        self.detail_title.setStyleSheet("font-weight: 700;")
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
        regions_title.setStyleSheet("font-weight: 700;")
        self.regions_layout.addWidget(regions_title)
        self.regions_body = QVBoxLayout()
        self.regions_layout.addLayout(self.regions_body)
        right_col.addWidget(self.regions_panel, stretch=1)

        split.addLayout(right_col, stretch=1)
        self.layout_.addLayout(split)

        self.reco_panel = QFrame()
        self.reco_panel.setObjectName("Card")
        apply_card_shadow(self.reco_panel)
        reco_layout = QVBoxLayout(self.reco_panel)
        reco_title = QLabel("Recommendations")
        reco_title.setStyleSheet("font-weight: 700; font-size: 14px;")
        reco_layout.addWidget(reco_title)
        self.reco_body = QVBoxLayout()
        reco_layout.addLayout(self.reco_body)
        self.layout_.addWidget(self.reco_panel)

        actions = QHBoxLayout()
        privacy_label = QLabel("🔒 Your face image is processed only for this analysis.")
        privacy_label.setObjectName("Muted")
        actions.addWidget(privacy_label)
        actions.addStretch()

        export_pdf_btn = QPushButton("Export PDF")
        export_pdf_btn.setObjectName("Secondary")
        export_pdf_btn.clicked.connect(self._export_pdf)
        export_png_btn = QPushButton("Export Annotated Image")
        export_png_btn.setObjectName("Secondary")
        export_png_btn.clicked.connect(self._export_png)
        delete_btn = QPushButton("Delete Scan")
        delete_btn.setObjectName("Secondary")
        delete_btn.clicked.connect(self._delete)
        new_scan_btn = QPushButton("New Scan")
        new_scan_btn.setObjectName("Primary")
        new_scan_btn.clicked.connect(self._on_new_scan)

        for b in (export_pdf_btn, export_png_btn, delete_btn, new_scan_btn):
            actions.addWidget(b)
        self.layout_.addLayout(actions)

    def show_record(self, record: ScanRecord, image: Optional[np.ndarray]) -> None:
        self._record = record
        self._image = image

        while self.cards_row.count():
            item = self.cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        analysis = record.analysis
        acne_count = analysis.acne_like_spots.count or len(
            [r for r in record.regions if r.category == "Acne-like spots"]
        )
        redness_count = len([r for r in record.regions if r.category == "Redness"])
        dry_count = len([r for r in record.regions if r.category == "Dryness indicators"])

        self.cards_row.addWidget(AnalysisCard("Acne-like Spots", analysis.acne_like_spots, f"{acne_count} area(s) flagged"))
        self.cards_row.addWidget(AnalysisCard("Visible Redness", analysis.redness, f"{redness_count} area(s) found"))
        self.cards_row.addWidget(AnalysisCard("Skin Texture", analysis.texture, "Facial areas assessed"))
        self.cards_row.addWidget(AnalysisCard("Dryness Indicators", analysis.dryness_indicators, f"{dry_count} area(s) found"))

        self.face_report.set_image(image, record.regions)
        self.detail_body.setText("Click a marker on the photo to see details.")

        while self.regions_body.count():
            item = self.regions_body.takeAt(0)
            if item.widget():
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
                region_label.setStyleSheet("font-weight: 700; font-size: 10.5px; color: #8993a8;")
                self.regions_body.addWidget(region_label)
                for o in obs_list:
                    color = CATEGORY_QCOLOR.get(o.category, "#3b8dff")
                    item_label = QLabel(f"<span style='color:{color};'>●</span>  {o.observation}")
                    self.regions_body.addWidget(item_label)

        while self.reco_body.count():
            item = self.reco_body.takeAt(0)
            if item.widget():
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
            "<span style='color:#8993a8; font-size: 10.5px;'>This is a visual observation "
            "and does not establish a medical diagnosis.</span>"
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

    def _delete(self) -> None:
        if self._record:
            self._on_delete(self._record.id)
