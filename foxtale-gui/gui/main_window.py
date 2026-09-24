from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QEvent, QRect, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton,
    QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from engine.schemas import AnalyzeResult
from gui.assets import app_icon, brand_pixmap, icon as make_icon, icon_pixmap
from gui.core import app_lock, storage
from gui.core.error_handling import LOG_DIR
from gui.pages.about_page import AboutPage
from gui.pages.compare_page import ComparePage
from gui.pages.history_page import HistoryPage
from gui.pages.home_page import HomePage
from gui.pages.privacy_page import PrivacyPage
from gui.pages.results_page import ResultsPage
from gui.pages.scan_page import ScanPage
from gui.pages.settings_page import SettingsPage
from gui.theme import FOX, icon_color, muted_text_color, set_current_theme, stylesheet_for
from gui.version import __version__
from gui.widgets.command_palette import CommandPalette
from gui.widgets.info_dialogs import AboutDialog, ShortcutsDialog
from gui.widgets.lock_screen import LockScreen
from gui.widgets.toast import Toast
from gui.widgets.welcome_dialog import WelcomeDialog

NAV_ITEMS = [
    ("home", "Dashboard", "fa5s.home"),
    ("scan", "Scan", "fa5s.camera"),
    ("results", "Analysis", "fa5s.chart-bar"),
    ("history", "History", "fa5s.history"),
    ("compare", "Compare", "fa5s.exchange-alt"),
    ("privacy", "Privacy", "fa5s.user-shield"),
    ("settings", "Settings", "fa5s.cog"),
    ("about", "About", "fa5s.info-circle"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Foxtale — AI-Powered Visual Skin Analysis")
        self.resize(1180, 780)

        self._settings = storage.load_settings()
        # Bake theme-correct icon colors before any icon-bearing widget is
        # constructed below (icons are flat-color bitmaps, set once).
        set_current_theme(self._settings.get("theme", "light"))
        self._restore_window_geometry()

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
        self._nav_icons: dict[str, str] = {}
        for key, label, icon_name in NAV_ITEMS:
            btn = QPushButton(f"  {label}")
            btn.setIcon(make_icon(icon_name, muted_text_color()))
            btn.setIconSize(QSize(15, 15))
            btn.setObjectName("SidebarButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self.navigate(k))
            sb_layout.addWidget(btn)
            self._nav_buttons[key] = btn
            self._nav_icons[key] = icon_name
        sb_layout.addStretch()

        profile_card = QFrame()
        profile_card.setObjectName("ProfileCard")
        profile_row = QHBoxLayout(profile_card)
        profile_row.setContentsMargins(12, 10, 12, 10)
        profile_row.setSpacing(10)
        avatar = QLabel()
        avatar.setPixmap(brand_pixmap(26))
        profile_row.addWidget(avatar)
        profile_text_col = QVBoxLayout()
        profile_text_col.setSpacing(0)
        profile_name = QLabel("Fox")
        profile_name.setStyleSheet("font-weight: 700; font-size: 12.5px;")
        profile_text_col.addWidget(profile_name)
        profile_sub = QLabel("Local Profile")
        profile_sub.setObjectName("Muted")
        profile_text_col.addWidget(profile_sub)
        profile_row.addLayout(profile_text_col, 1)
        sb_layout.addWidget(profile_card)

        sb_layout.addSpacing(8)

        help_card = QFrame()
        help_card.setObjectName("Card")
        help_card.setStyleSheet("margin: 0 10px;")
        help_col = QVBoxLayout(help_card)
        help_col.setContentsMargins(12, 10, 12, 10)
        help_col.setSpacing(2)
        help_row = QHBoxLayout()
        help_icon = QLabel()
        help_icon.setPixmap(icon_pixmap("fa5s.headset", icon_color("accent"), size=14))
        help_row.addWidget(help_icon)
        help_title = QLabel("Need help?")
        help_title.setStyleSheet("font-weight: 700; font-size: 12px;")
        help_row.addWidget(help_title)
        help_row.addStretch()
        help_col.addLayout(help_row)
        shortcuts_link = QPushButton("Keyboard Shortcuts")
        shortcuts_link.setObjectName("LinkButton")
        shortcuts_link.setCursor(Qt.CursorShape.PointingHandCursor)
        shortcuts_link.clicked.connect(self._show_shortcuts_dialog)
        help_col.addWidget(shortcuts_link)
        sb_layout.addWidget(help_card)

        sb_layout.addSpacing(8)

        version_label = QLabel(f"v{__version__} · Desktop")
        version_label.setObjectName("Muted")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb_layout.addWidget(version_label)

        root.addWidget(sidebar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.home_page = HomePage(
            on_start_scan=lambda: self.navigate("scan"),
            on_view_scan=self._open_history_record,
            get_settings=lambda: self._settings,
            on_navigate=self.navigate,
        )
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
        self.privacy_page = PrivacyPage(show_toast=self._toast)
        self.settings_page = SettingsPage(
            get_settings=lambda: self._settings,
            on_settings_changed=self._on_settings_changed,
            show_toast=self._toast,
        )
        self.about_page = AboutPage(on_replay_tour=self._show_welcome_dialog)

        self._pages = {
            "home": self.home_page,
            "scan": self.scan_page,
            "results": self.results_page,
            "history": self.history_page,
            "compare": self.compare_page,
            "privacy": self.privacy_page,
            "settings": self.settings_page,
            "about": self.about_page,
        }
        for page in self._pages.values():
            self.stack.addWidget(page)

        self.toast = Toast(central)

        self.lock_screen = LockScreen(central)
        self.lock_screen.unlocked.connect(self._on_unlocked)
        self.lock_screen.hide()

        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.timeout.connect(self._on_inactivity_timeout)
        QApplication.instance().installEventFilter(self)
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._on_system_theme_changed)

        self._build_menu_bar()
        self._tray_hint_shown = False
        self._build_tray_icon()
        self.navigate("home")
        self.apply_theme(self._settings.get("theme", "light"))

        if not self._settings.get("onboarding_complete", False):
            self._show_welcome_dialog()

        if (
            self._settings.get("app_lock_enabled", False)
            and self._settings.get("lock_on_start", True)
            and app_lock.has_pin()
        ):
            self._lock()
        else:
            self._reset_inactivity_timer()

    def _restore_window_geometry(self) -> None:
        geometry = self._settings.get("window_geometry")
        if not geometry:
            return
        screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else None

        w = max(900, min(int(geometry.get("w", 1180)), screen_rect.width() if screen_rect else 3840))
        h = max(600, min(int(geometry.get("h", 780)), screen_rect.height() if screen_rect else 2160))
        x, y = int(geometry.get("x", 0)), int(geometry.get("y", 0))
        target = QRect(x, y, w, h)

        if screen_rect and screen_rect.intersects(target):
            self.setGeometry(target)
        else:
            self.resize(w, h)

        if geometry.get("maximized"):
            self.showMaximized()

    def _save_window_geometry(self) -> None:
        geo = self.geometry()
        self._settings["window_geometry"] = {
            "x": geo.x(), "y": geo.y(), "w": geo.width(), "h": geo.height(),
            "maximized": self.isMaximized(),
        }
        storage.save_settings(self._settings)

    def _lock(self) -> None:
        self.lock_screen.setGeometry(self.centralWidget().rect())
        self.lock_screen.show()
        self.lock_screen.raise_()
        self._inactivity_timer.stop()

    def _on_unlocked(self) -> None:
        self.lock_screen.hide()
        self._reset_inactivity_timer()

    def _reset_inactivity_timer(self) -> None:
        minutes = self._settings.get("lock_after_minutes", 0)
        if self._settings.get("app_lock_enabled", False) and minutes and app_lock.has_pin():
            self._inactivity_timer.start(minutes * 60 * 1000)
        else:
            self._inactivity_timer.stop()

    def _on_inactivity_timeout(self) -> None:
        if not self.lock_screen.isVisible():
            self._lock()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            if not self.lock_screen.isVisible():
                self._reset_inactivity_timer()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "lock_screen") and self.lock_screen.isVisible():
            self.lock_screen.setGeometry(self.centralWidget().rect())

    def _build_tray_icon(self) -> None:
        self.tray_icon = QSystemTrayIcon(app_icon(), self)
        self.tray_icon.setToolTip("Foxtale")

        menu = QMenu()
        show_action = menu.addAction("Show Foxtale")
        show_action.triggered.connect(self._restore_from_tray)
        scan_action = menu.addAction("Start Scan")
        scan_action.triggered.connect(self._start_scan_from_tray)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _start_scan_from_tray(self) -> None:
        self._restore_from_tray()
        self.navigate("scan")

    def _quit_app(self) -> None:
        self._save_window_geometry()
        self.scan_page.shutdown()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        new_scan_action = file_menu.addAction("New Scan")
        new_scan_action.setShortcut(QKeySequence("Ctrl+N"))
        new_scan_action.triggered.connect(lambda: self.navigate("scan"))
        settings_action = file_menu.addAction("Settings")
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(lambda: self.navigate("settings"))
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)

        view_menu = menu_bar.addMenu("&View")
        palette_action = view_menu.addAction("Command Palette")
        palette_action.setShortcut(QKeySequence("Ctrl+K"))
        palette_action.triggered.connect(self._open_command_palette)
        view_menu.addSeparator()
        home_action = view_menu.addAction("Dashboard")
        home_action.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        home_action.triggered.connect(lambda: self.navigate("home"))
        for key, label, _icon in NAV_ITEMS:
            if key in ("home", "settings"):
                continue
            action = view_menu.addAction(label)
            if key == "history":
                action.setShortcut(QKeySequence("Ctrl+H"))
            action.triggered.connect(lambda _, k=key: self.navigate(k))

        help_menu = menu_bar.addMenu("&Help")
        shortcuts_action = help_menu.addAction("Keyboard Shortcuts")
        shortcuts_action.triggered.connect(self._show_shortcuts_dialog)
        log_action = help_menu.addAction("Open Log Folder")
        log_action.triggered.connect(self._open_log_folder)
        help_menu.addSeparator()
        about_action = help_menu.addAction("About Foxtale")
        about_action.triggered.connect(self._show_about_dialog)

    def _show_welcome_dialog(self) -> None:
        dialog = WelcomeDialog(current_theme=self._settings.get("theme", "light"), parent=self)
        dialog.exec()
        self._settings["onboarding_complete"] = True
        self._settings["theme"] = dialog.selected_theme
        storage.save_settings(self._settings)
        self.apply_theme(dialog.selected_theme)

    def _open_command_palette(self) -> None:
        commands = []
        for key, label, _icon in NAV_ITEMS:
            commands.append((f"Go to {label}", lambda k=key: self.navigate(k)))
        commands.append(("New Scan", lambda: self.navigate("scan")))
        commands.append(("Toggle Theme", self._toggle_theme))
        if app_lock.has_pin():
            commands.append(("Lock Now", self._lock))
        commands.append(("Open Settings", lambda: self.navigate("settings")))
        commands.append(("Open Log Folder", self._open_log_folder))
        commands.append(("Keyboard Shortcuts", self._show_shortcuts_dialog))
        commands.append(("About Foxtale", self._show_about_dialog))
        CommandPalette(commands, parent=self).exec()

    def _toggle_theme(self) -> None:
        current = self._settings.get("theme", "light")
        next_theme = "dark" if self._resolve_theme(current) == "light" else "light"
        self._settings["theme"] = next_theme
        storage.save_settings(self._settings)
        self.apply_theme(next_theme)

    def _show_about_dialog(self) -> None:
        AboutDialog(parent=self).exec()

    def _show_shortcuts_dialog(self) -> None:
        ShortcutsDialog(parent=self).exec()

    def _open_log_folder(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR)))

    def navigate(self, key: str) -> None:
        if key == "home":
            self.home_page.refresh()
        if key == "scan":
            self.scan_page.reset()
        if key == "history":
            self.history_page.refresh()
        if key == "compare":
            self.compare_page.refresh()
        if key == "privacy":
            self.privacy_page.refresh()
        if key == "settings":
            self.settings_page.reload()

        self.stack.setCurrentWidget(self._pages[key])
        for k, btn in self._nav_buttons.items():
            active = k == key
            btn.setProperty("active", "true" if active else "false")
            btn.setIcon(make_icon(self._nav_icons[k], FOX if active else muted_text_color()))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_scan_complete(self, result: AnalyzeResult, image: np.ndarray, quality=None) -> None:
        if self._settings.get("save_history", True):
            record = storage.save_scan(
                result.analysis, result.regions, image,
                save_image=self._settings.get("save_images", False),
                quality=quality,
            )
        else:
            record = storage.make_transient_record(result.analysis, result.regions, quality=quality)
        self.results_page.show_record(record, image)
        self.navigate("results")
        self._toast("Scan complete.")
        if not self.isVisible() or not self.isActiveWindow():
            self.tray_icon.showMessage(
                "Scan complete", "Your skin analysis is ready to view.",
                QSystemTrayIcon.MessageIcon.Information, 4000,
            )

    def _open_history_record(self, scan_id: str) -> None:
        record = storage.get_scan(scan_id)
        if not record:
            return
        image = cv2.imread(record.image_path) if record.image_path else None
        self.results_page.show_record(record, image)
        self.navigate("results")

    def _on_delete_scan(self, scan_id: str) -> None:
        storage.delete_scan(scan_id)
        self._toast("Moved to Recently Deleted.")
        self.navigate("scan")

    def _on_settings_changed(self, partial: dict) -> None:
        self._settings.update(partial)
        storage.save_settings(self._settings)
        self.apply_theme(self._settings.get("theme", "light"))
        self._reset_inactivity_timer()

    def _resolve_theme(self, theme: str) -> str:
        if theme != "auto":
            return theme
        app = QApplication.instance()
        if not app:
            return "light"
        scheme = app.styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"

    def apply_theme(self, theme: str) -> None:
        resolved = self._resolve_theme(theme)
        set_current_theme(resolved)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet_for(resolved))

    def _on_system_theme_changed(self, *_args) -> None:
        if self._settings.get("theme") == "auto":
            self.apply_theme("auto")

    def _toast(self, message: str) -> None:
        self.toast.show_message(message)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._settings.get("minimize_to_tray", False):
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self.tray_icon.showMessage(
                    "Foxtale",
                    "Still running in the system tray. Right-click the tray icon to quit.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
                self._tray_hint_shown = True
            return

        self._save_window_geometry()
        self.scan_page.shutdown()
        self.tray_icon.hide()
        super().closeEvent(event)
        QApplication.instance().quit()
