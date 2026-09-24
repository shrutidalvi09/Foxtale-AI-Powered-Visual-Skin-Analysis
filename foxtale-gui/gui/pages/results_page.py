"""Analysis page: summary cards, the annotated photo (or an empty state),
a visible-observation panel, region breakdown, personal notes, a scan
journal, recommendations, and export actions."""

from datetime import datetime
from typing import Callable, Dict, Optional

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from engine.schemas import RegionObservation
from gui.assets import apply_card_shadow, apply_cta_glow, icon_circle, icon_pixmap
from gui.assets import icon as make_icon
from gui.core import storage
from gui.core.insights import compute_baseline
from gui.core.recommendations import build_recommendations
from gui.core.report_export import build_pdf_report, build_summary_card_image, save_annotated_image
from gui.core.storage import ScanRecord
from gui.theme import FOX, icon_color, muted_text_color
from gui.widgets.analysis_card import AnalysisCard
from gui.widgets.analysis_widgets import FaceSketch, PhotoPanel, RegionDonut
from gui.widgets.disclaimer import DisclaimerBanner
from gui.widgets.quality_card import QualityCard

REGION_BUCKETS = ["Forehead", "Cheeks", "Nose", "Chin", "Others"]
REGION_COLORS = ["#e54a00", "#f5a524", "#3b8dff", "#12a06a", "#8b7fd6"]
EMPTY_DOT = "#c3c9d8"

ROUTINE_ICONS = {
    "Cleanser": "fa5s.pump-soap", "Moisturiser": "fa5s.tint", "Sunscreen": "fa5s.sun",
    "Treatment": "fa6s.wand-magic-sparkles", "Exfoliator": "fa5s.hand-sparkles", "Other": "fa5s.ellipsis-h",
}
ENVIRONMENT_ICONS = {
    "Travel": "fa5s.plane", "Outdoor exposure": "fa5s.tree",
    "High humidity": "fa5s.cloud-rain", "Low humidity": "fa5s.wind",
}
DETAIL_HINT = "Click a marker on the photo to see details."


def _region_bucket(region_name: str) -> str:
    name = region_name.upper()
    if "FOREHEAD" in name:
        return "Forehead"
    if "CHEEK" in name:
        return "Cheeks"
    if "NOSE" in name:
        return "Nose"
    if "CHIN" in name:
        return "Chin"
    return "Others"


def _make_chip(text: str, icon_name: str) -> QPushButton:
    btn = QPushButton(f"  {text}")
    btn.setObjectName("RoutineChip")
    btn.setCheckable(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setIconSize(QSize(15, 15))

    def refresh_icon(*_args) -> None:
        btn.setIcon(make_icon(icon_name, FOX if btn.isChecked() else muted_text_color()))

    btn.toggled.connect(refresh_icon)
    btn.refresh_icon = refresh_icon  # type: ignore[attr-defined]
    refresh_icon()
    return btn


def _card_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    apply_card_shadow(frame, blur=20, y_offset=5, alpha=20)
    return frame


def _title_block(title: str, subtitle: Optional[str] = None) -> QVBoxLayout:
    col = QVBoxLayout()
    col.setSpacing(3)
    t = QLabel(title)
    t.setObjectName("CardTitle")
    t.setStyleSheet("font-size: 14.5px;")
    col.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("SubHeading")
        s.setWordWrap(True)
        col.addWidget(s)
    return col


class ResultsPage(QWidget):
    def __init__(
        self,
        on_new_scan: Callable[[], None],
        on_delete: Callable[[str], None],
        show_toast: Callable[[str], None],
        on_upload_image: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_new_scan = on_new_scan
        self._on_delete = on_delete
        self._show_toast = show_toast
        self._on_upload_image = on_upload_image or on_new_scan
        self._record: Optional[ScanRecord] = None
        self._image: Optional[np.ndarray] = None
        self._persisted = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self._scroll)

        content = QWidget()
        self._scroll.setWidget(content)
        self.layout_ = QVBoxLayout(content)
        self.layout_.setContentsMargins(36, 28, 36, 28)
        self.layout_.setSpacing(16)

        self._build_header()
        self.layout_.addWidget(DisclaimerBanner())

        self.cards_container = QWidget()
        self.cards_row = QHBoxLayout(self.cards_container)
        self.cards_row.setContentsMargins(0, 0, 0, 0)
        self.cards_row.setSpacing(14)
        self.layout_.addWidget(self.cards_container)

        self._build_heatmap_row()
        self._build_main_split()
        self._build_notes_card()
        self._build_journal_card()
        self._build_reco_card()
        self._build_actions_row()
        self.layout_.addStretch(1)

        self.show_empty()

    # ------------------------------------------------------------- layout

    def _nav_button(self, text: str, icon_name: str, icon_on_right: bool = False) -> QPushButton:
        btn = QPushButton(f" {text} ")
        btn.setIcon(make_icon(icon_name, icon_color("primary")))
        btn.setIconSize(QSize(15, 15))
        btn.setObjectName("Secondary")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(48)
        btn.setMinimumWidth(124)
        if icon_on_right:
            btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        apply_card_shadow(btn, blur=14, y_offset=3, alpha=16)
        return btn

    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        heading = QLabel("Your Skin Analysis")
        heading.setObjectName("Heading")
        title_col.addWidget(heading)
        self.sub_label = QLabel()
        self.sub_label.setObjectName("SubHeading")
        title_col.addWidget(self.sub_label)
        header.addLayout(title_col)
        header.addStretch()

        self.prev_btn = self._nav_button("Previous", "fa5s.step-backward")
        self.prev_btn.setToolTip("Older scan")
        self.prev_btn.clicked.connect(lambda: self._go_relative(1))
        header.addWidget(self.prev_btn, alignment=Qt.AlignmentFlag.AlignTop)

        self.next_btn = self._nav_button("Next", "fa5s.step-forward", icon_on_right=True)
        self.next_btn.setToolTip("Newer scan")
        self.next_btn.clicked.connect(lambda: self._go_relative(-1))
        header.addWidget(self.next_btn, alignment=Qt.AlignmentFlag.AlignTop)

        self.save_btn = self._nav_button("Save Report", "fa5.star")
        self.save_btn.setMinimumWidth(150)
        self.save_btn.clicked.connect(self._show_report_menu)
        header.addWidget(self.save_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self.layout_.addLayout(header)

    def _build_heatmap_row(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        self.heatmap_btn = QPushButton("  Heatmap")
        self.heatmap_btn.setIcon(make_icon("fa5s.fire", FOX))
        self.heatmap_btn.setIconSize(QSize(16, 16))
        self.heatmap_btn.setObjectName("ToggleChip")
        self.heatmap_btn.setCheckable(True)
        self.heatmap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.heatmap_btn.toggled.connect(self._update_heatmap)
        apply_card_shadow(self.heatmap_btn, blur=14, y_offset=3, alpha=16)
        row.addWidget(self.heatmap_btn)

        self.heatmap_category_combo = QComboBox()
        self.heatmap_category_combo.setMinimumWidth(170)
        self.heatmap_category_combo.setFixedHeight(46)
        self.heatmap_category_combo.addItem("All Categories", None)
        for category in ("Acne-like spots", "Redness", "Texture", "Dryness indicators"):
            self.heatmap_category_combo.addItem(category, category)
        self.heatmap_category_combo.currentIndexChanged.connect(self._update_heatmap)
        row.addWidget(self.heatmap_category_combo)
        row.addStretch()
        self.layout_.addLayout(row)

    def _build_main_split(self) -> None:
        split = QHBoxLayout()
        split.setSpacing(18)

        self.photo_panel = PhotoPanel()
        self.photo_panel.marker_clicked.connect(self._on_marker_clicked)
        self.photo_panel.start_scan.connect(self._on_new_scan)
        self.photo_panel.upload_image.connect(self._on_upload_image)
        split.addWidget(self.photo_panel, stretch=1)

        right = QVBoxLayout()
        right.setSpacing(16)

        # --- visible observation ---
        self.detail_panel = _card_frame()
        detail_row = QHBoxLayout(self.detail_panel)
        detail_row.setContentsMargins(20, 18, 14, 18)
        detail_row.setSpacing(14)
        detail_row.addWidget(icon_circle("fa5.eye", FOX, "#fde8da", size=42, icon_size=18), alignment=Qt.AlignmentFlag.AlignTop)
        detail_col = _title_block("Visible Observation")
        self.detail_body = QLabel(DETAIL_HINT)
        self.detail_body.setObjectName("SubHeading")
        self.detail_body.setWordWrap(True)
        self.detail_body.setTextFormat(Qt.TextFormat.RichText)
        detail_col.addWidget(self.detail_body)
        detail_col.addStretch()
        detail_row.addLayout(detail_col, stretch=1)
        detail_row.addWidget(FaceSketch(), alignment=Qt.AlignmentFlag.AlignVCenter)
        right.addWidget(self.detail_panel, stretch=1)

        # --- region breakdown ---
        self.regions_panel = _card_frame()
        regions_row = QHBoxLayout(self.regions_panel)
        regions_row.setContentsMargins(20, 18, 20, 18)
        regions_row.setSpacing(14)
        regions_row.addWidget(icon_circle("fa5s.th-large", FOX, "#fde8da", size=42, icon_size=17), alignment=Qt.AlignmentFlag.AlignTop)
        regions_col = _title_block("Region Breakdown", "Detailed breakdown of different facial regions.")
        regions_col.addStretch()
        regions_row.addLayout(regions_col, stretch=1)

        self.donut = RegionDonut()
        regions_row.addWidget(self.donut, alignment=Qt.AlignmentFlag.AlignVCenter)

        legend = QVBoxLayout()
        legend.setSpacing(7)
        self._legend_dots: Dict[str, QLabel] = {}
        self._legend_values: Dict[str, QLabel] = {}
        for name in REGION_BUCKETS:
            line = QHBoxLayout()
            line.setSpacing(8)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {EMPTY_DOT}; font-size: 10px;")
            line.addWidget(dot)
            label = QLabel(name)
            label.setStyleSheet("font-size: 12px;")
            line.addWidget(label, stretch=1)
            value = QLabel("--")
            value.setObjectName("Muted")
            value.setStyleSheet("font-weight: 700; font-size: 12px;")
            line.addWidget(value)
            legend.addLayout(line)
            self._legend_dots[name] = dot
            self._legend_values[name] = value
        legend_wrap = QWidget()
        legend_wrap.setMinimumWidth(118)
        legend_wrap.setStyleSheet("background: transparent;")
        legend_wrap.setLayout(legend)
        regions_row.addWidget(legend_wrap, alignment=Qt.AlignmentFlag.AlignVCenter)
        right.addWidget(self.regions_panel, stretch=1)

        right_wrap = QWidget()
        right_wrap.setLayout(right)
        right.setContentsMargins(0, 0, 0, 0)
        split.addWidget(right_wrap, stretch=1)
        self.layout_.addLayout(split)

    def _build_notes_card(self) -> None:
        self.notes_panel = _card_frame()
        v = QVBoxLayout(self.notes_panel)
        v.setContentsMargins(22, 18, 22, 18)
        v.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap("fa5.sticky-note", FOX, size=20))
        header.addWidget(icon_lbl)
        title = QLabel("Notes")
        title.setObjectName("CardTitle")
        title.setStyleSheet("font-size: 14.5px;")
        header.addWidget(title)
        header.addStretch()
        v.addLayout(header)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Add a personal note (e.g. new product, routine change, skin concerns)…")
        self.notes_edit.setFixedHeight(48)
        self.notes_edit.returnPressed.connect(self._save_note)
        row.addWidget(self.notes_edit, stretch=1)
        self.notes_save_btn = QPushButton("Save Note")
        self.notes_save_btn.setObjectName("SoftButton")
        self.notes_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notes_save_btn.setFixedSize(116, 44)
        self.notes_save_btn.clicked.connect(self._save_note)
        row.addWidget(self.notes_save_btn)
        v.addLayout(row)

        self.notes_hint = QLabel("")
        self.notes_hint.setObjectName("Muted")
        self.notes_hint.setWordWrap(True)
        v.addWidget(self.notes_hint)
        self.layout_.addWidget(self.notes_panel)

    def _build_journal_card(self) -> None:
        self.journal_panel = _card_frame()
        v = QVBoxLayout(self.journal_panel)
        v.setContentsMargins(22, 18, 22, 20)
        v.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap("fa5.calendar-alt", FOX, size=20))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        header.addLayout(_title_block("Scan Journal", "Track your skincare routine and habits for better insights."), stretch=1)
        add_note_btn = QPushButton("  Add Note")
        add_note_btn.setIcon(make_icon("fa5s.plus", icon_color("primary")))
        add_note_btn.setIconSize(QSize(13, 13))
        add_note_btn.setObjectName("Secondary")
        add_note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_note_btn.setFixedHeight(44)
        add_note_btn.clicked.connect(self._focus_notes)
        header.addWidget(add_note_btn, alignment=Qt.AlignmentFlag.AlignTop)
        v.addLayout(header)

        v.addSpacing(4)
        routine_label = QLabel("Routine")
        routine_label.setObjectName("Muted")
        v.addWidget(routine_label)
        routine_row = QHBoxLayout()
        routine_row.setSpacing(10)
        self.routine_checks: Dict[str, QPushButton] = {}
        for option in storage.ROUTINE_OPTIONS:
            chip = _make_chip(option, ROUTINE_ICONS.get(option, "fa5s.ellipsis-h"))
            chip.toggled.connect(self._save_journal)
            routine_row.addWidget(chip)
            self.routine_checks[option] = chip
        routine_row.addStretch()
        v.addLayout(routine_row)

        v.addSpacing(4)
        env_label = QLabel("Environment")
        env_label.setObjectName("Muted")
        v.addWidget(env_label)
        env_row = QHBoxLayout()
        env_row.setSpacing(10)
        self.environment_checks: Dict[str, QPushButton] = {}
        for option in storage.ENVIRONMENT_OPTIONS:
            chip = _make_chip(option, ENVIRONMENT_ICONS.get(option, "fa5s.ellipsis-h"))
            chip.toggled.connect(self._save_journal)
            env_row.addWidget(chip)
            self.environment_checks[option] = chip
        env_row.addStretch()
        v.addLayout(env_row)
        self.layout_.addWidget(self.journal_panel)

    def _build_reco_card(self) -> None:
        self.reco_panel = _card_frame()
        v = QVBoxLayout(self.reco_panel)
        v.setContentsMargins(22, 18, 22, 18)
        v.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap("fa5.lightbulb", FOX, size=20))
        header.addWidget(icon_lbl)
        title = QLabel("Recommendations")
        title.setObjectName("CardTitle")
        title.setStyleSheet("font-size: 14.5px;")
        header.addWidget(title)
        header.addStretch()
        v.addLayout(header)
        self.reco_body = QVBoxLayout()
        self.reco_body.setSpacing(6)
        v.addLayout(self.reco_body)
        self.layout_.addWidget(self.reco_panel)

    def _build_actions_row(self) -> None:
        actions = QHBoxLayout()
        actions.setSpacing(12)
        privacy_icon = QLabel()
        privacy_icon.setPixmap(icon_pixmap("fa5s.lock", icon_color("accent"), size=13))
        actions.addWidget(privacy_icon)
        privacy_label = QLabel("Your face image is processed only for this analysis.")
        privacy_label.setObjectName("Muted")
        actions.addWidget(privacy_label)
        actions.addStretch()

        self.delete_btn = QPushButton("  Delete Scan")
        self.delete_btn.setIcon(make_icon("fa5s.trash-alt", icon_color("primary")))
        self.delete_btn.setObjectName("Secondary")
        self.delete_btn.setFixedHeight(48)
        self.delete_btn.clicked.connect(self._delete)
        actions.addWidget(self.delete_btn)

        new_scan_btn = QPushButton("  New Scan")
        new_scan_btn.setIcon(make_icon("fa5s.camera", "white"))
        new_scan_btn.setObjectName("Cta")
        new_scan_btn.setFixedHeight(48)
        apply_cta_glow(new_scan_btn)
        new_scan_btn.clicked.connect(self._on_new_scan)
        actions.addWidget(new_scan_btn)
        self.layout_.addLayout(actions)

    # -------------------------------------------------------------- state

    def has_record(self) -> bool:
        return self._record is not None

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def _set_chips(self, chips: Dict[str, QPushButton], selected: list, enabled: bool) -> None:
        for option, chip in chips.items():
            chip.blockSignals(True)
            chip.setChecked(option in selected)
            chip.setEnabled(enabled)
            chip.blockSignals(False)
            chip.refresh_icon()

    def _update_regions(self, regions: list) -> None:
        counts = {name: 0 for name in REGION_BUCKETS}
        for r in regions:
            counts[_region_bucket(r.region)] += 1
        total = sum(counts.values())
        self.donut.set_segments(
            [(REGION_COLORS[i], counts[name]) for i, name in enumerate(REGION_BUCKETS)],
            center_text=str(total),
        )
        for i, name in enumerate(REGION_BUCKETS):
            self._legend_dots[name].setStyleSheet(
                f"color: {REGION_COLORS[i] if counts[name] else EMPTY_DOT}; font-size: 10px;"
            )
            self._legend_values[name].setText(str(counts[name]))

    def show_empty(self) -> None:
        """Nothing to show yet: the dark "no image" panel, placeholder
        breakdown, and disabled note/journal/report controls."""
        self._record = None
        self._image = None
        self._persisted = False

        self.sub_label.setText("AI-powered visual skin observations")
        self._clear_layout(self.cards_row)
        self.cards_container.setVisible(False)
        self.photo_panel.show_empty()
        self.detail_body.setText(DETAIL_HINT)
        self.donut.set_segments([], center_text="")
        for name in REGION_BUCKETS:
            self._legend_dots[name].setStyleSheet(f"color: {EMPTY_DOT}; font-size: 10px;")
            self._legend_values[name].setText("--")

        self.notes_edit.clear()
        self.notes_edit.setEnabled(False)
        self.notes_save_btn.setEnabled(False)
        self.notes_hint.setText("Notes and the journal become available once you have a scan.")
        self._set_chips(self.routine_checks, [], False)
        self._set_chips(self.environment_checks, [], False)

        self._clear_layout(self.reco_body)
        self.reco_panel.setVisible(False)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self._update_star_button()

    def show_record(self, record: ScanRecord, image: Optional[np.ndarray]) -> None:
        self._record = record
        self._image = image
        self._persisted = storage.get_scan(record.id) is not None

        when = datetime.fromisoformat(record.timestamp).strftime("%b %d, %Y  ·  %I:%M %p")
        self.sub_label.setText(f"AI-powered visual skin observations  ·  {when}")
        self._update_star_button()
        self._update_nav_buttons()
        self.save_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

        self.notes_edit.setText(record.note)
        self.notes_edit.setEnabled(self._persisted)
        self.notes_save_btn.setEnabled(self._persisted)
        self.notes_hint.setText(
            "" if self._persisted else
            "Notes and starring are available for saved scans — enable \"Save scan history\" in Settings."
        )
        self._set_chips(self.routine_checks, record.journal.get("routine", []), self._persisted)
        self._set_chips(self.environment_checks, record.journal.get("environment", []), self._persisted)

        self._clear_layout(self.cards_row)
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
        self.cards_container.setVisible(True)

        if image is not None:
            self.photo_panel.show_photo(image, record.regions)
            self.detail_body.setText(DETAIL_HINT)
        else:
            self.photo_panel.show_no_photo()
            self.detail_body.setText(
                "No photo was saved for this scan, so there are no markers to click. "
                "The region counts below still reflect what was found."
            )
        self._update_heatmap()
        self._update_regions(record.regions)

        self._clear_layout(self.reco_body)
        for tip in build_recommendations(analysis):
            lbl = QLabel(f"•  {tip}")
            lbl.setWordWrap(True)
            self.reco_body.addWidget(lbl)
        self.reco_panel.setVisible(True)

    # ------------------------------------------------------------ actions

    def _on_marker_clicked(self, region: RegionObservation) -> None:
        self.detail_body.setText(
            f"<b>Area:</b> {region.region.title()}<br>"
            f"<b>Observation:</b> {region.observation}<br>"
            f"<b>Confidence:</b> {int(region.confidence * 100)}%<br>"
            f"<span style='color:{muted_text_color()}; font-size: 10.5px;'>A visual observation, "
            "not a medical diagnosis.</span>"
        )

    def _update_heatmap(self, *_args) -> None:
        self.photo_panel.set_heatmap_mode(
            self.heatmap_btn.isChecked(), self.heatmap_category_combo.currentData(),
        )

    def _focus_notes(self) -> None:
        self._scroll.ensureWidgetVisible(self.notes_panel)
        if self.notes_edit.isEnabled():
            self.notes_edit.setFocus()

    def _show_report_menu(self) -> None:
        if not self._record:
            return
        menu = QMenu(self)
        menu.addAction("Export PDF report", self._export_pdf)
        png_action = menu.addAction("Export annotated image", self._export_png)
        png_action.setEnabled(self._image is not None)
        menu.addAction("Export share card (no photo)", self._export_share_card)
        menu.addSeparator()
        starred = self._record.starred
        star_action = menu.addAction("Unstar this scan" if starred else "Star this scan", self._toggle_star)
        star_action.setEnabled(self._persisted)
        menu.exec(self.save_btn.mapToGlobal(QPoint(0, self.save_btn.height() + 6)))

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
        self.save_btn.setIcon(make_icon("fa5s.star" if starred else "fa5.star", icon_color("primary")))
        self.save_btn.setToolTip("Starred — open for report options" if starred else "Report options")

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

    def _save_journal(self, *_args) -> None:
        if not self._record or not self._persisted:
            return
        routine = [opt for opt, chip in self.routine_checks.items() if chip.isChecked()]
        environment = [opt for opt, chip in self.environment_checks.items() if chip.isChecked()]
        self._record.journal = {"routine": routine, "environment": environment}
        storage.set_scan_journal(self._record.id, routine, environment)
