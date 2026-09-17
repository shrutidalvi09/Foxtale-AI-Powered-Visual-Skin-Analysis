from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from engine.schemas import AnalyzeResult
from gui.assets import brand_pixmap
from gui.core import storage
from gui.pages.about_page import AboutPage
from gui.pages.compare_page import ComparePage
from gui.pages.history_page import HistoryPage
from gui.pages.home_page import HomePage
from gui.pages.results_page import ResultsPage
from gui.pages.scan_page import ScanPage
from gui.pages.settings_page import SettingsPage
from gui.theme import stylesheet_for
from gui.widgets.toast import Toast

NAV_ITEMS = [
    ("home", "🏠  Home"),
    ("scan", "🔍  Scan"),
    ("results", "📊  Analysis"),
    ("history", "🕘  History"),
    ("compare", "🔁  Compare"),
    ("settings", "⚙️  Settings"),
    ("about", "ℹ️  About"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Foxtale — AI-Powered Visual Skin Analysis")
        self.resize(1180, 780)

        self._settings = storage.load_settings()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 12)
        sb_layout.setSpacing(2)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(18, 20, 18, 4)
        brand_row.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(brand_pixmap(30))
        brand_row.addWidget(icon_label)
        brand_text_col = QVBoxLayout()
        brand_text_col.setSpacing(0)
        brand = QLabel("Foxtale")
        brand.setObjectName("Brand")
        brand_text_col.addWidget(brand)
        tag = QLabel("SKIN ANALYSIS")
        tag.setObjectName("BrandTag")
        brand_text_col.addWidget(tag)
        brand_row.addLayout(brand_text_col)
        brand_row.addStretch()
        sb_layout.addLayout(brand_row)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        sb_layout.addSpacing(10)
        sb_layout.addWidget(divider)
        sb_layout.addSpacing(10)

        self._nav_buttons: dict[str, QPushButton] = {}
        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("SidebarButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self.navigate(k))
            sb_layout.addWidget(btn)
            self._nav_buttons[key] = btn
        sb_layout.addStretch()

        version_label = QLabel("v1.0 · Desktop")
        version_label.setObjectName("Muted")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb_layout.addWidget(version_label)

        root.addWidget(sidebar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.home_page = HomePage(on_start_scan=lambda: self.navigate("scan"))
        self.scan_page = ScanPage(
            get_settings=lambda: self._settings,
            on_scan_complete=self._on_scan_complete,
            show_toast=self._toast,
        )
        self.results_page = ResultsPage(
            on_new_scan=lambda: self.navigate("scan"),
            on_delete=self._on_delete_scan,
            show_toast=self._toast,
        )
        self.history_page = HistoryPage(on_open_record=self._open_history_record, show_toast=self._toast)
        self.compare_page = ComparePage()
        self.settings_page = SettingsPage(
            get_settings=lambda: self._settings,
            on_settings_changed=self._on_settings_changed,
            show_toast=self._toast,
        )
        self.about_page = AboutPage()

        self._pages = {
            "home": self.home_page,
            "scan": self.scan_page,
            "results": self.results_page,
            "history": self.history_page,
            "compare": self.compare_page,
            "settings": self.settings_page,
            "about": self.about_page,
        }
        for page in self._pages.values():
            self.stack.addWidget(page)

        self.toast = Toast(central)

        self._register_shortcuts()
        self.navigate("home")
        self.apply_theme(self._settings.get("theme", "light"))

    def _register_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.navigate("scan"))
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.navigate("settings"))
        QShortcut(QKeySequence("Ctrl+H"), self, activated=lambda: self.navigate("history"))
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=lambda: self.navigate("home"))

    def navigate(self, key: str) -> None:
        if key == "scan":
            self.scan_page.reset()
        if key == "history":
            self.history_page.refresh()
        if key == "compare":
            self.compare_page.refresh()
        if key == "settings":
            self.settings_page.reload()

        self.stack.setCurrentWidget(self._pages[key])
        for k, btn in self._nav_buttons.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_scan_complete(self, result: AnalyzeResult, image: np.ndarray) -> None:
        if self._settings.get("save_history", True):
            record = storage.save_scan(
                result.analysis, result.regions, image,
                save_image=self._settings.get("save_images", False),
            )
        else:
            record = storage.make_transient_record(result.analysis, result.regions)
        self.results_page.show_record(record, image)
        self.navigate("results")
        self._toast("Scan complete.")

    def _open_history_record(self, scan_id: str) -> None:
        record = storage.get_scan(scan_id)
        if not record:
            return
        image = cv2.imread(record.image_path) if record.image_path else None
        self.results_page.show_record(record, image)
        self.navigate("results")

    def _on_delete_scan(self, scan_id: str) -> None:
        storage.delete_scan(scan_id)
        self._toast("Scan deleted.")
        self.navigate("scan")

    def _on_settings_changed(self, partial: dict) -> None:
        self._settings.update(partial)
        storage.save_settings(self._settings)
        self.apply_theme(self._settings.get("theme", "light"))

    def apply_theme(self, theme: str) -> None:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet_for(theme))

    def _toast(self, message: str) -> None:
        self.toast.show_message(message)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.scan_page.shutdown()
        super().closeEvent(event)
