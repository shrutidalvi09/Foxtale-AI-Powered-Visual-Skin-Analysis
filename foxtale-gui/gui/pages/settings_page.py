from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

from gui.assets import apply_card_shadow
from gui.core import storage


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

        heading = QLabel("Settings")
        heading.setObjectName("Heading")
        layout.addWidget(heading)

        layout.addWidget(self._privacy_card())
        layout.addWidget(self._appearance_card())
        layout.addWidget(self._analysis_card())
        layout.addWidget(self._calibration_card())
        layout.addStretch()

        self.reload()

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("Card")
        apply_card_shadow(frame)
        v = QVBoxLayout(frame)
        t = QLabel(title)
        t.setStyleSheet("font-weight: 800; font-size: 14px;")
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

        note = QLabel(
            "🔒 Images are never sent anywhere — everything runs on this device. "
            "Saved images live in a local folder and are deleted when you delete a scan."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        v.addWidget(note)

        return frame

    def _appearance_card(self) -> QFrame:
        frame, v = self._card("Appearance")
        row = QHBoxLayout()
        row.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.currentIndexChanged.connect(self._on_change)
        row.addWidget(self.theme_combo)
        row.addStretch()
        v.addLayout(row)
        return frame

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
        self.calibration_status = QLabel()
        self.calibration_status.setObjectName("SubHeading")
        v.addWidget(self.calibration_status)

        reset_btn = QPushButton("Clear Calibration")
        reset_btn.setObjectName("Secondary")
        reset_btn.clicked.connect(self._clear_calibration)
        v.addWidget(reset_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return frame

    def reload(self) -> None:
        settings = self._get_settings()
        self.save_history_check.blockSignals(True)
        self.save_images_check.blockSignals(True)
        self.theme_combo.blockSignals(True)
        self.confidence_slider.blockSignals(True)

        self.save_history_check.setChecked(settings.get("save_history", True))
        self.save_images_check.setChecked(settings.get("save_images", False))
        idx = self.theme_combo.findData(settings.get("theme", "light"))
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        pct = int(settings.get("min_confidence", 0.0) * 100)
        self.confidence_slider.setValue(pct)
        self.confidence_label.setText(f"{pct}%")

        self.save_history_check.blockSignals(False)
        self.save_images_check.blockSignals(False)
        self.theme_combo.blockSignals(False)
        self.confidence_slider.blockSignals(False)

        self._refresh_calibration_status()

    def _refresh_calibration_status(self) -> None:
        profile = storage.load_calibration()
        if profile:
            self.calibration_status.setText("✅ Calibration saved — scans use your personal baseline.")
        else:
            self.calibration_status.setText("No calibration saved. You can calibrate from the Scan page after capturing a photo.")

    def _on_confidence_change(self, value: int) -> None:
        self.confidence_label.setText(f"{value}%")
        self._on_change()

    def _on_change(self, *_args) -> None:
        settings = {
            "save_history": self.save_history_check.isChecked(),
            "save_images": self.save_images_check.isChecked(),
            "theme": self.theme_combo.currentData(),
            "min_confidence": self.confidence_slider.value() / 100.0,
        }
        self._on_settings_changed(settings)

    def _clear_calibration(self) -> None:
        storage.clear_calibration()
        self._refresh_calibration_status()
        self._show_toast("Calibration cleared.")
