from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow, icon_pixmap
from gui.assets import icon as make_icon
from gui.core import app_lock, perf, storage
from gui.core.camera_worker import list_camera_indices
from gui.theme import icon_color

CAMERA_RESOLUTIONS = [
    ("HD 1280x720", (1280, 720)),
    ("VGA 640x480", (640, 480)),
    ("Full HD 1920x1080", (1920, 1080)),
]


class SettingsPage(QWidget):
    def __init__(self, get_settings: Callable[[], dict], on_settings_changed: Callable[[dict], None],
                 show_toast: Callable[[str], None], parent=None):
        super().__init__(parent)
        self._get_settings = get_settings
        self._on_settings_changed = on_settings_changed
        self._show_toast = show_toast

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_icon = QLabel()
        header_icon.setPixmap(icon_pixmap("fa5s.cog", icon_color("accent"), size=22))
        header_row.addWidget(header_icon)
        heading = QLabel("Settings")
        heading.setObjectName("Heading")
        header_row.addWidget(heading)
        header_row.addStretch()
        layout.addLayout(header_row)

        layout.addWidget(self._privacy_card())
        layout.addWidget(self._app_lock_card())
        layout.addWidget(self._appearance_card())
        layout.addWidget(self._scanning_card())
        layout.addWidget(self._camera_card())
        layout.addWidget(self._analysis_card())
        layout.addWidget(self._calibration_card())
        layout.addWidget(self._performance_card())
        layout.addWidget(self._backup_card())
        layout.addStretch()

        self.reload()

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("Card")
        apply_card_shadow(frame)
        v = QVBoxLayout(frame)
        t = QLabel(title)
        t.setObjectName("CardTitle")
        v.addWidget(t)
        return frame, v

    def _privacy_card(self) -> QFrame:
        frame, v = self._card("Privacy")

        self.save_history_check = QCheckBox("Save scan history (analysis summaries only)")
        self.save_history_check.stateChanged.connect(self._on_change)
        v.addWidget(self.save_history_check)

        self.save_images_check = QCheckBox("Also save captured images with each scan (off by default)")
        self.save_images_check.stateChanged.connect(self._on_change)
        v.addWidget(self.save_images_check)

        note_row = QHBoxLayout()
        note_icon = QLabel()
        note_icon.setPixmap(icon_pixmap("fa5s.lock", icon_color("accent"), size=12))
        note_icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        note_row.addWidget(note_icon)
        note = QLabel(
            "Images are never sent anywhere — everything runs on this device. "
            "Saved images live in a local folder and are deleted when you delete a scan."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        note_row.addWidget(note, stretch=1)
        v.addLayout(note_row)

        return frame

    def _app_lock_card(self) -> QFrame:
        frame, v = self._card("App Lock")

        note = QLabel(
            "Locks the app window behind a PIN. Your data always stays on this device either way — "
            "this only blocks casual access to the window, not full-disk encryption."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        v.addWidget(note)

        self.app_lock_check = QCheckBox("Enable App Lock")
        self.app_lock_check.toggled.connect(self._on_app_lock_toggled)
        v.addWidget(self.app_lock_check)

        pin_row = QHBoxLayout()
        self.change_pin_btn = QPushButton(" Set / Change PIN")
        self.change_pin_btn.setIcon(make_icon("fa5s.key", icon_color("primary")))
        self.change_pin_btn.setObjectName("Secondary")
        self.change_pin_btn.clicked.connect(self._set_pin)
        pin_row.addWidget(self.change_pin_btn)
        pin_row.addStretch()
        v.addLayout(pin_row)

        self.lock_on_start_check = QCheckBox("Lock when the app starts")
        self.lock_on_start_check.stateChanged.connect(self._on_change)
        v.addWidget(self.lock_on_start_check)

        inactivity_row = QHBoxLayout()
        inactivity_row.addWidget(QLabel("Lock after inactivity:"))
        self.lock_inactivity_combo = QComboBox()
        for label, minutes in [("Never", 0), ("5 minutes", 5), ("15 minutes", 15), ("30 minutes", 30), ("1 hour", 60)]:
            self.lock_inactivity_combo.addItem(label, minutes)
        self.lock_inactivity_combo.currentIndexChanged.connect(self._on_change)
        inactivity_row.addWidget(self.lock_inactivity_combo)
        inactivity_row.addStretch()
        v.addLayout(inactivity_row)

        return frame

    def _set_pin(self) -> bool:
        pin, ok = QInputDialog.getText(self, "Set PIN", "Enter a new PIN (4+ digits):", QLineEdit.EchoMode.Password)
        if not ok or len(pin.strip()) < 4:
            if ok:
                QMessageBox.warning(self, "PIN too short", "Please use a PIN of at least 4 digits.")
            return False
        confirm, ok = QInputDialog.getText(self, "Confirm PIN", "Re-enter your PIN:", QLineEdit.EchoMode.Password)
        if not ok or confirm != pin:
            QMessageBox.warning(self, "PINs didn't match", "Please try again.")
            return False
        app_lock.set_pin(pin.strip())
        self._show_toast("PIN saved.")
        return True

    def _on_app_lock_toggled(self, checked: bool) -> None:
        if checked and not app_lock.has_pin():
            if not self._set_pin():
                self.app_lock_check.blockSignals(True)
                self.app_lock_check.setChecked(False)
                self.app_lock_check.blockSignals(False)
                return
        if not checked:
            app_lock.clear_pin()
        self._on_change()

    def _appearance_card(self) -> QFrame:
        frame, v = self._card("Appearance")
        row = QHBoxLayout()
        row.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Auto (matches system)", "auto")
        self.theme_combo.currentIndexChanged.connect(self._on_change)
        row.addWidget(self.theme_combo)
        row.addStretch()
        v.addLayout(row)
        return frame

    def _scanning_card(self) -> QFrame:
        frame, v = self._card("Scanning & Reminders")

        self.countdown_check = QCheckBox("Show a 3-second countdown before capturing")
        self.countdown_check.stateChanged.connect(self._on_change)
        v.addWidget(self.countdown_check)

        reminder_row = QHBoxLayout()
        reminder_row.addWidget(QLabel("Remind me to scan:"))
        self.reminder_combo = QComboBox()
        for label, days in [("Never", 0), ("Every 3 days", 3), ("Weekly", 7), ("Every 2 weeks", 14), ("Monthly", 30)]:
            self.reminder_combo.addItem(label, days)
        self.reminder_combo.currentIndexChanged.connect(self._on_change)
        reminder_row.addWidget(self.reminder_combo)
        reminder_row.addStretch()
        v.addLayout(reminder_row)

        self.tray_check = QCheckBox("Keep running in the system tray when the window is closed")
        self.tray_check.stateChanged.connect(self._on_change)
        v.addWidget(self.tray_check)

        self.auto_capture_check = QCheckBox("Hands-free: capture automatically once your face holds steady")
        self.auto_capture_check.stateChanged.connect(self._on_change)
        v.addWidget(self.auto_capture_check)

        self.standardised_check = QCheckBox(
            "Standardised Scan Mode — show a live checklist (position, distance, "
            "lighting, shadow, exposure) for more comparable scans over time"
        )
        self.standardised_check.stateChanged.connect(self._on_change)
        v.addWidget(self.standardised_check)

        return frame

    def _camera_card(self) -> QFrame:
        frame, v = self._card("Camera")

        note = QLabel(
            "Choose the default capture device and resolution, or save named profiles "
            "to switch quickly between setups (e.g. different desks or lighting)."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        v.addWidget(note)

        row = QHBoxLayout()
        row.addWidget(QLabel("Device:"))
        self.camera_device_combo = QComboBox()
        for idx in list_camera_indices():
            self.camera_device_combo.addItem(f"Camera {idx}", idx)
        self.camera_device_combo.currentIndexChanged.connect(self._on_change)
        row.addWidget(self.camera_device_combo)

        row.addWidget(QLabel("Resolution:"))
        self.camera_resolution_combo = QComboBox()
        for label, res in CAMERA_RESOLUTIONS:
            self.camera_resolution_combo.addItem(label, res)
        self.camera_resolution_combo.currentIndexChanged.connect(self._on_change)
        row.addWidget(self.camera_resolution_combo)
        row.addStretch()
        v.addLayout(row)

        save_row = QHBoxLayout()
        save_profile_btn = QPushButton(" Save Current as Profile")
        save_profile_btn.setIcon(make_icon("fa5s.save", icon_color("primary")))
        save_profile_btn.setObjectName("Secondary")
        save_profile_btn.clicked.connect(self._save_camera_profile)
        save_row.addWidget(save_profile_btn)
        save_row.addStretch()
        v.addLayout(save_row)

        self.profiles_layout = QVBoxLayout()
        v.addLayout(self.profiles_layout)

        return frame

    def _save_camera_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Camera Profile", "Profile name:")
        name = name.strip()
        if not ok or not name:
            return
        width, height = self.camera_resolution_combo.currentData() or (1280, 720)
        profiles = [p for p in self._get_settings().get("camera_profiles", []) if p["name"] != name]
        profiles.append({
            "name": name,
            "index": self.camera_device_combo.currentData() or 0,
            "width": width,
            "height": height,
        })
        self._on_settings_changed({"camera_profiles": profiles})
        self._refresh_camera_profiles(profiles)
        self._show_toast(f'Saved camera profile "{name}".')

    def _apply_camera_profile(self, profile: dict) -> None:
        dev_idx = self.camera_device_combo.findData(profile["index"])
        if dev_idx >= 0:
            self.camera_device_combo.setCurrentIndex(dev_idx)
        res_idx = self.camera_resolution_combo.findData((profile["width"], profile["height"]))
        if res_idx >= 0:
            self.camera_resolution_combo.setCurrentIndex(res_idx)
        self._show_toast(f'Using camera profile "{profile["name"]}".')

    def _delete_camera_profile(self, name: str) -> None:
        profiles = [p for p in self._get_settings().get("camera_profiles", []) if p["name"] != name]
        self._on_settings_changed({"camera_profiles": profiles})
        self._refresh_camera_profiles(profiles)

    def _refresh_camera_profiles(self, profiles: list) -> None:
        while self.profiles_layout.count():
            item = self.profiles_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        for profile in profiles:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 4, 0, 4)
            label = QLabel(f'{profile["name"]} — Camera {profile["index"]}, {profile["width"]}x{profile["height"]}')
            h.addWidget(label, stretch=1)
            use_btn = QPushButton("Use")
            use_btn.setObjectName("Secondary")
            use_btn.clicked.connect(lambda _, p=profile: self._apply_camera_profile(p))
            h.addWidget(use_btn)
            del_btn = QPushButton("Delete")
            del_btn.setObjectName("Secondary")
            del_btn.clicked.connect(lambda _, n=profile["name"]: self._delete_camera_profile(n))
            h.addWidget(del_btn)
            self.profiles_layout.addWidget(row)

    def _analysis_card(self) -> QFrame:
        frame, v = self._card("Analysis")
        row = QHBoxLayout()
        row.addWidget(QLabel("Minimum confidence to show a region marker:"))
        self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.confidence_slider.setRange(0, 90)
        self.confidence_slider.valueChanged.connect(self._on_confidence_change)
        row.addWidget(self.confidence_slider, stretch=1)
        self.confidence_label = QLabel("0%")
        row.addWidget(self.confidence_label)
        v.addLayout(row)
        return frame

    def _calibration_card(self) -> QFrame:
        frame, v = self._card("Skin-tone Calibration")
        status_row = QHBoxLayout()
        self.calibration_icon = QLabel()
        status_row.addWidget(self.calibration_icon)
        self.calibration_status = QLabel()
        self.calibration_status.setObjectName("SubHeading")
        self.calibration_status.setWordWrap(True)
        status_row.addWidget(self.calibration_status, stretch=1)
        v.addLayout(status_row)

        reset_btn = QPushButton(" Clear Calibration")
        reset_btn.setIcon(make_icon("fa5s.undo", icon_color("primary")))
        reset_btn.setObjectName("Secondary")
        reset_btn.clicked.connect(self._clear_calibration)
        v.addWidget(reset_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return frame

    def _performance_card(self) -> QFrame:
        frame, v = self._card("Performance")
        note = QLabel(
            "Timing for the on-device analysis pipeline (face detection + skin analysis) — "
            "proof it stays fast without ever leaving this machine."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        v.addWidget(note)
        self.perf_rows_layout = QVBoxLayout()
        v.addLayout(self.perf_rows_layout)
        return frame

    def _refresh_performance(self) -> None:
        while self.perf_rows_layout.count():
            item = self.perf_rows_layout.takeAt(0)
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

        stats = perf.get_stats()
        if not stats:
            empty = QLabel("Run a scan to see timing stats here.")
            empty.setObjectName("Muted")
            self.perf_rows_layout.addWidget(empty)
            return

        rows = [
            ("Last scan", f"{stats['last']:.0f} ms"),
            ("Average", f"{stats['avg']:.0f} ms"),
            ("Fastest", f"{stats['min']:.0f} ms"),
            ("Slowest", f"{stats['max']:.0f} ms"),
            ("Scans measured", str(stats["count"])),
        ]
        for label, value in rows:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("Muted")
            row.addWidget(name)
            row.addStretch()
            val = QLabel(value)
            val.setStyleSheet("font-weight: 700;")
            row.addWidget(val)
            self.perf_rows_layout.addLayout(row)

    def _backup_card(self) -> QFrame:
        frame, v = self._card("Data Backup")

        note = QLabel(
            "A full backup includes your settings, calibration, and scan history (plus any saved "
            "images) in one file — useful for moving to a new computer or as a safety net."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        v.addWidget(note)

        row = QHBoxLayout()
        export_btn = QPushButton(" Export All Data")
        export_btn.setIcon(make_icon("fa5s.file-archive", icon_color("primary")))
        export_btn.setObjectName("Secondary")
        export_btn.clicked.connect(self._export_backup)
        row.addWidget(export_btn)

        import_btn = QPushButton(" Import All Data")
        import_btn.setIcon(make_icon("fa5s.file-upload", icon_color("primary")))
        import_btn.setObjectName("Secondary")
        import_btn.clicked.connect(self._import_backup)
        row.addWidget(import_btn)
        row.addStretch()
        v.addLayout(row)

        return frame

    def _export_backup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export All Data", "foxtale-backup.zip", "Zip files (*.zip)")
        if not path:
            return
        storage.export_full_backup(path)
        self._show_toast("Backup exported.")

    def _import_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import All Data", "", "Zip files (*.zip)")
        if not path:
            return
        if QMessageBox.question(
            self, "Restore backup",
            "This replaces your current settings, calibration, and scan history with the backup's. Continue?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            storage.import_full_backup(path)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            QMessageBox.warning(self, "Restore failed", str(exc))
            return
        QMessageBox.information(self, "Backup restored", "Restart Foxtale for the restored data to fully take effect.")
        self._show_toast("Backup restored — restart to apply.")

    def reload(self) -> None:
        settings = self._get_settings()
        widgets = (
            self.save_history_check, self.save_images_check, self.theme_combo,
            self.confidence_slider, self.countdown_check, self.reminder_combo, self.tray_check,
            self.auto_capture_check, self.standardised_check,
            self.app_lock_check, self.lock_on_start_check, self.lock_inactivity_combo,
            self.camera_device_combo, self.camera_resolution_combo,
        )
        for w in widgets:
            w.blockSignals(True)

        self.save_history_check.setChecked(settings.get("save_history", True))
        self.save_images_check.setChecked(settings.get("save_images", False))
        idx = self.theme_combo.findData(settings.get("theme", "light"))
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        pct = int(settings.get("min_confidence", 0.0) * 100)
        self.confidence_slider.setValue(pct)
        self.confidence_label.setText(f"{pct}%")
        self.countdown_check.setChecked(settings.get("capture_countdown", True))
        reminder_idx = self.reminder_combo.findData(settings.get("reminder_days", 7))
        if reminder_idx >= 0:
            self.reminder_combo.setCurrentIndex(reminder_idx)
        self.tray_check.setChecked(settings.get("minimize_to_tray", False))
        self.auto_capture_check.setChecked(settings.get("auto_capture", False))
        self.standardised_check.setChecked(settings.get("standardised_mode", False))
        self.app_lock_check.setChecked(settings.get("app_lock_enabled", False))
        self.lock_on_start_check.setChecked(settings.get("lock_on_start", True))
        inactivity_idx = self.lock_inactivity_combo.findData(settings.get("lock_after_minutes", 0))
        if inactivity_idx >= 0:
            self.lock_inactivity_combo.setCurrentIndex(inactivity_idx)
        dev_idx = self.camera_device_combo.findData(settings.get("camera_index", 0))
        if dev_idx >= 0:
            self.camera_device_combo.setCurrentIndex(dev_idx)
        res_idx = self.camera_resolution_combo.findData(
            (settings.get("camera_width", 1280), settings.get("camera_height", 720))
        )
        if res_idx >= 0:
            self.camera_resolution_combo.setCurrentIndex(res_idx)

        for w in widgets:
            w.blockSignals(False)

        self._refresh_calibration_status()
        self._refresh_camera_profiles(settings.get("camera_profiles", []))
        self._refresh_performance()

    def _refresh_calibration_status(self) -> None:
        profile = storage.load_calibration()
        if profile:
            self.calibration_icon.setPixmap(icon_pixmap("fa5s.check-circle", icon_color("success"), size=14))
            self.calibration_status.setText("Calibration saved — scans use your personal baseline.")
        else:
            self.calibration_icon.setPixmap(icon_pixmap("fa5s.info-circle", icon_color("accent"), size=14))
            self.calibration_status.setText(
                "No calibration saved. You can calibrate from the Scan page after capturing a photo."
            )

    def _on_confidence_change(self, value: int) -> None:
        self.confidence_label.setText(f"{value}%")
        self._on_change()

    def _on_change(self, *_args) -> None:
        width, height = self.camera_resolution_combo.currentData() or (1280, 720)
        settings = {
            "save_history": self.save_history_check.isChecked(),
            "save_images": self.save_images_check.isChecked(),
            "theme": self.theme_combo.currentData(),
            "min_confidence": self.confidence_slider.value() / 100.0,
            "capture_countdown": self.countdown_check.isChecked(),
            "reminder_days": self.reminder_combo.currentData(),
            "minimize_to_tray": self.tray_check.isChecked(),
            "auto_capture": self.auto_capture_check.isChecked(),
            "standardised_mode": self.standardised_check.isChecked(),
            "app_lock_enabled": self.app_lock_check.isChecked(),
            "lock_on_start": self.lock_on_start_check.isChecked(),
            "lock_after_minutes": self.lock_inactivity_combo.currentData(),
            "camera_index": self.camera_device_combo.currentData() or 0,
            "camera_width": width,
            "camera_height": height,
        }
        self._on_settings_changed(settings)

    def _clear_calibration(self) -> None:
        storage.clear_calibration()
        self._refresh_calibration_status()
        self._show_toast("Calibration cleared.")
