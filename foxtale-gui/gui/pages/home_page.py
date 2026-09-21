from datetime import datetime
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow, icon as make_icon, icon_pixmap, logo_full_pixmap
from gui.core import storage
from gui.core.insights import compute_badges
from gui.theme import icon_color
from gui.widgets.disclaimer import DisclaimerBanner

FEATURES = [
    ("fa5s.camera", "Camera-based analysis", "Live face-lock guidance before you even capture"),
    ("fa5s.eye", "Visual skin observations", "Never a diagnosis — always plain, visible findings"),
    ("fa5s.lock", "Private, local processing", "Nothing leaves this device, ever"),
    ("fa5s.chart-line", "Trend tracking over time", "Compare scans and watch your progress"),
]


class HomePage(QWidget):
    def __init__(self, on_start_scan, on_view_scan, get_settings: Callable[[], dict], parent=None):
        super().__init__(parent)
        self._on_start_scan = on_start_scan
        self._on_view_scan = on_view_scan
        self._get_settings = get_settings

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.setSpacing(22)

        self.activity_layout = QVBoxLayout()
        outer.addLayout(self.activity_layout)

        hero = QFrame()
        hero.setObjectName("HeroPanel")
        apply_card_shadow(hero, blur=32, y_offset=10, alpha=25)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(48, 52, 48, 52)
        hero_layout.setSpacing(14)

        logo_label = QLabel()
        logo_label.setPixmap(logo_full_pixmap(96))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(logo_label)

        heading = QLabel("Understand Your Skin\nThrough AI Vision")
        heading.setObjectName("Heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 34px; font-weight: 800;")
        hero_layout.addWidget(heading)

        sub = QLabel(
            "Scan your face with your webcam and get an easy-to-understand, visual skin\n"
            "observation report — processed entirely on this device."
        )
        sub.setObjectName("SubHeading")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(sub)

        start_btn = QPushButton("Start Face Scan")
        start_btn.setObjectName("Primary")
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.setMinimumWidth(220)
        start_btn.setMinimumHeight(40)
        apply_card_shadow(start_btn, blur=20, y_offset=8, alpha=60)
        start_btn.clicked.connect(on_start_scan)
        hero_layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(hero)

        grid = QGridLayout()
        grid.setSpacing(14)
        feature_icon_color = icon_color("accent")
        for i, (icon_name, title, body) in enumerate(FEATURES):
            card = QFrame()
            card.setObjectName("Card")
            apply_card_shadow(card, blur=18, y_offset=4, alpha=22)
            card_layout = QVBoxLayout(card)
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap(icon_name, feature_icon_color, size=22))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(icon_label)
            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setWordWrap(True)
            title_label.setStyleSheet("font-size: 11.5px; font-weight: 700;")
            card_layout.addWidget(title_label)
            body_label = QLabel(body)
            body_label.setObjectName("Muted")
            body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body_label.setWordWrap(True)
            card_layout.addWidget(body_label)
            grid.addWidget(card, 0, i)
        outer.addLayout(grid)

        outer.addWidget(DisclaimerBanner())
        outer.addStretch()

        self.refresh()

    def refresh(self) -> None:
        """Rebuild the "Recent Activity" summary shown to returning users
        who already have scan history -- first-time users just see the
        marketing hero above."""
        while self.activity_layout.count():
            item = self.activity_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        records = storage.list_scans()
        if not records:
            return

        latest = records[0]
        starred_count = sum(1 for r in records if r.starred)

        reminder_days = self._get_settings().get("reminder_days", 0)
        days_since = storage.days_since_last_scan()
        if reminder_days and days_since is not None and days_since >= reminder_days:
            self.activity_layout.addWidget(self._build_reminder_banner(days_since))

        card = QFrame()
        card.setObjectName("Card")
        apply_card_shadow(card, blur=18, y_offset=4, alpha=22)
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 16, 20, 16)

        icon_label = QLabel()
        icon_label.setPixmap(icon_pixmap("fa5s.chart-bar", icon_color("accent"), size=26))
        row.addWidget(icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        when = datetime.fromisoformat(latest.timestamp).strftime("%b %d, %Y · %I:%M %p")
        title = QLabel(f"{len(records)} scan{'s' if len(records) != 1 else ''} recorded")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        text_col.addWidget(title)
        summary_bits = [f"Last scan: {when}"]
        if starred_count:
            summary_bits.append(f"{starred_count} starred")
        summary = QLabel("  ·  ".join(summary_bits))
        summary.setObjectName("Muted")
        text_col.addWidget(summary)
        row.addLayout(text_col, stretch=1)

        view_btn = QPushButton(" View Last Analysis")
        view_btn.setIcon(make_icon("fa5s.chart-bar", icon_color("primary")))
        view_btn.setObjectName("Secondary")
        view_btn.clicked.connect(lambda: self._on_view_scan(latest.id))
        row.addWidget(view_btn)

        self.activity_layout.addWidget(card)

        badges = compute_badges(records)
        earned = [b for b in badges if b.earned]
        if earned:
            self.activity_layout.addWidget(self._build_badges_card(earned, badges))

    def _build_badges_card(self, earned: list, all_badges: list) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        apply_card_shadow(card, blur=18, y_offset=4, alpha=22)
        v = QVBoxLayout(card)

        title = QLabel("Achievements")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        v.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)
        columns = 5
        for i, badge in enumerate(earned):
            chip = QFrame()
            chip.setObjectName("Card")
            chip_row = QHBoxLayout(chip)
            chip_row.setContentsMargins(10, 6, 10, 6)
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap(badge.icon, icon_color("accent"), size=13))
            chip_row.addWidget(icon_label)
            text = QLabel(badge.label)
            text.setStyleSheet("font-size: 11px; font-weight: 700;")
            chip_row.addWidget(text)
            grid.addWidget(chip, i // columns, i % columns)
        v.addLayout(grid)

        next_badge = next((b for b in all_badges if not b.earned), None)
        if next_badge:
            next_label = QLabel(f"Next up: {next_badge.label}")
            next_label.setObjectName("Muted")
            v.addWidget(next_label)

        return card

    def _build_reminder_banner(self, days_since: int) -> QFrame:
        banner = QFrame()
        banner.setObjectName("Disclaimer")
        apply_card_shadow(banner, blur=18, y_offset=4, alpha=20)
        row = QHBoxLayout(banner)
        row.setContentsMargins(16, 12, 16, 12)

        icon_label = QLabel()
        icon_label.setPixmap(icon_pixmap("fa5s.bell", icon_color("warning"), size=16))
        row.addWidget(icon_label)

        text = QLabel(f"It's been {days_since} days since your last scan — time for a check-in?")
        text.setWordWrap(True)
        row.addWidget(text, stretch=1)

        scan_btn = QPushButton("Scan Now")
        scan_btn.setObjectName("Secondary")
        scan_btn.clicked.connect(self._on_start_scan)
        row.addWidget(scan_btn)

        return banner
