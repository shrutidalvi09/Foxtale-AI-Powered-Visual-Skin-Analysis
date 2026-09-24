"""Live camera preview with a friendly scanning-frame overlay: corner
brackets, an animated sweep line, a live brightness meter, and a face-lock
indicator that goes from brand-orange to green once a face is framed --
all computed locally, before the user even presses Capture.
"""

import time
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from engine.quality import FrameStatus
from gui.assets import apply_card_shadow, icon_pixmap
from gui.core.camera_worker import CameraWorker, list_camera_indices
from gui.theme import FOX, NAVY, icon_color


def _bgr_to_pixmap(frame: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class CameraCanvas(QWidget):
    countdown_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self._pixmap: Optional[QPixmap] = None
        self._mode = "off"  # off | live | captured
        self._face_detected = False
        self._brightness = 0.0
        self._guidance = "Position your face inside the frame"
        self._phase = 0.0
        self._countdown = 0

        self._timer = QTimer(self)
        self._timer.setInterval(35)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._countdown_tick)

    def _tick(self) -> None:
        if self._mode == "live":
            self._phase = (self._phase + 0.03) % 1.0
            self.update()

    @property
    def is_counting_down(self) -> bool:
        return self._countdown > 0

    def start_countdown(self, seconds: int) -> None:
        self._countdown = seconds
        self.update()
        self._countdown_timer.start()

    def _countdown_tick(self) -> None:
        self._countdown -= 1
        self.update()
        if self._countdown <= 0:
            self._countdown_timer.stop()
            self.countdown_finished.emit()

    def set_live_frame(self, frame_bgr: np.ndarray) -> None:
        self._mode = "live"
        self._pixmap = _bgr_to_pixmap(frame_bgr)
        self.update()

    def set_captured_frame(self, frame_bgr: np.ndarray) -> None:
        self._mode = "captured"
        self._pixmap = _bgr_to_pixmap(frame_bgr)
        self.update()

    def set_status(self, face_detected: bool, brightness: float, guidance: str = "") -> None:
        self._face_detected = face_detected
        self._brightness = brightness
        if guidance:
            self._guidance = guidance
        self.update()

    def clear(self) -> None:
        self._mode = "off"
        self._pixmap = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        side = min(rect.width(), rect.height())
        square = rect.adjusted(
            (rect.width() - side) // 2, (rect.height() - side) // 2,
            -(rect.width() - side) // 2, -(rect.height() - side) // 2,
        )

        painter.setBrush(QColor(NAVY))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(square, 26, 26)

        if self._pixmap:
            painter.save()
            path_rect = square.adjusted(2, 2, -2, -2)
            painter.setClipRect(path_rect)
            scaled = self._pixmap.scaled(
                path_rect.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = path_rect.x() - (scaled.width() - path_rect.width()) // 2
            y = path_rect.y() - (scaled.height() - path_rect.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.restore()

        if self._mode == "live":
            self._draw_scan_overlay(painter, square)
        elif self._mode == "off":
            painter.setPen(QColor("#8993a8"))
            painter.drawText(square, Qt.AlignmentFlag.AlignCenter, "Camera is off")

        painter.end()

    def _draw_scan_overlay(self, painter: QPainter, square) -> None:
        inset_w = square.width() * 0.24
        inset_h = square.height() * 0.16
        frame_rect = square.adjusted(int(inset_w), int(inset_h), -int(inset_w), -int(inset_h))

        color = QColor("#22c55e") if self._face_detected else QColor(FOX)
        pen = QPen(color, 4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        bracket = 24
        x0, y0, x1, y1 = frame_rect.left(), frame_rect.top(), frame_rect.right(), frame_rect.bottom()
        painter.drawLine(x0, y0, x0 + bracket, y0)
        painter.drawLine(x0, y0, x0, y0 + bracket)
        painter.drawLine(x1, y0, x1 - bracket, y0)
        painter.drawLine(x1, y0, x1, y0 + bracket)
        painter.drawLine(x0, y1, x0 + bracket, y1)
        painter.drawLine(x0, y1, x0, y1 - bracket)
        painter.drawLine(x1, y1, x1 - bracket, y1)
        painter.drawLine(x1, y1, x1, y1 - bracket)

        sweep_y = frame_rect.top() + int(self._phase * frame_rect.height())
        sweep_color = QColor(color)
        sweep_color.setAlpha(140)
        painter.setPen(QPen(sweep_color, 2))
        painter.drawLine(frame_rect.left() + 4, sweep_y, frame_rect.right() - 4, sweep_y)

        status_text = self._guidance
        pill_rect = square.adjusted(16, square.height() - 46, -16, -12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(11, 18, 36, 210))
        painter.drawRoundedRect(pill_rect, 14, 14)
        painter.setPen(QColor("white"))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, status_text)

        meter_rect = square.adjusted(16, 14, -16, -square.height() + 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 40))
        painter.drawRoundedRect(meter_rect, 5, 5)
        fill_ratio = max(0.0, min(1.0, self._brightness / 255.0))
        fill_rect = meter_rect.adjusted(0, 0, -int(meter_rect.width() * (1 - fill_ratio)), 0)
        meter_color = QColor("#22c55e") if self._brightness >= 60 else QColor("#f97316")
        painter.setBrush(meter_color)
        painter.drawRoundedRect(fill_rect, 5, 5)

        if self._countdown > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(11, 18, 36, 150))
            painter.drawRoundedRect(square, 26, 26)
            painter.setPen(QColor("white"))
            font = QFont()
            font.setPointSize(80)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(square, Qt.AlignmentFlag.AlignCenter, str(self._countdown))


class CameraView(QWidget):
    captured = Signal(np.ndarray)
    error = Signal(str)

    def __init__(self, get_settings, parent=None):
        super().__init__(parent)
        self._get_settings = get_settings
        self.worker: Optional[CameraWorker] = None
        self._captured_frame: Optional[np.ndarray] = None
        self._burst_timer: Optional[QTimer] = None
        self._face_steady_since: Optional[float] = None

        layout = QVBoxLayout(self)
        self.canvas = CameraCanvas()
        apply_card_shadow(self.canvas, blur=34, y_offset=12, alpha=45)
        self.canvas.countdown_finished.connect(self._do_capture)
        layout.addWidget(self.canvas)

        self.checklist_panel = QFrame()
        self.checklist_panel.setObjectName("Card")
        checklist_layout = QVBoxLayout(self.checklist_panel)
        checklist_title = QLabel("Standardised Scan Mode")
        checklist_title.setObjectName("CardTitle")
        checklist_layout.addWidget(checklist_title)
        self._checklist_icons: dict[str, QLabel] = {}
        checklist_row = QHBoxLayout()
        for name in ("Face centered", "Distance consistent", "Brightness in range", "Low shadow", "Exposure stable"):
            item = QHBoxLayout()
            icon_lbl = QLabel()
            item.addWidget(icon_lbl)
            text_lbl = QLabel(name)
            text_lbl.setStyleSheet("font-size: 11px;")
            item.addWidget(text_lbl)
            checklist_row.addLayout(item)
            self._checklist_icons[name] = icon_lbl
        checklist_layout.addLayout(checklist_row)
        self.checklist_panel.setVisible(False)
        layout.addWidget(self.checklist_panel)

        controls = QHBoxLayout()
        self.device_combo = QComboBox()
        for idx in list_camera_indices():
            self.device_combo.addItem(f"Camera {idx}", idx)
        controls.addWidget(QLabel("Device:"))
        controls.addWidget(self.device_combo)

        self.resolution_combo = QComboBox()
        for label, (w, h) in [("HD 1280x720", (1280, 720)), ("VGA 640x480", (640, 480)), ("Full HD 1920x1080", (1920, 1080))]:
            self.resolution_combo.addItem(label, (w, h))
        controls.addWidget(QLabel("Resolution:"))
        controls.addWidget(self.resolution_combo)
        controls.addStretch()
        layout.addLayout(controls)

        settings = self._get_settings()
        dev_idx = self.device_combo.findData(settings.get("camera_index", 0))
        if dev_idx >= 0:
            self.device_combo.setCurrentIndex(dev_idx)
        res_idx = self.resolution_combo.findData((settings.get("camera_width", 1280), settings.get("camera_height", 720)))
        if res_idx >= 0:
            self.resolution_combo.setCurrentIndex(res_idx)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.start_btn = QPushButton("Start Camera")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self.start_camera)
        self.stop_btn = QPushButton("Stop Camera")
        self.stop_btn.setObjectName("Secondary")
        self.stop_btn.clicked.connect(self.stop_camera)
        self.stop_btn.setVisible(False)
        self.capture_btn = QPushButton("Capture")
        self.capture_btn.setObjectName("Primary")
        self.capture_btn.clicked.connect(self.capture)
        self.capture_btn.setVisible(False)
        self.retake_btn = QPushButton("Retake")
        self.retake_btn.setObjectName("Secondary")
        self.retake_btn.clicked.connect(self.retake)
        self.retake_btn.setVisible(False)

        for b in (self.start_btn, self.stop_btn, self.capture_btn, self.retake_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def start_camera(self) -> None:
        index = self.device_combo.currentData() or 0
        width, height = self.resolution_combo.currentData() or (1280, 720)

        self._face_steady_since = None
        self.worker = CameraWorker(camera_index=index, width=width, height=height)
        self.worker.frame_ready.connect(self.canvas.set_live_frame)
        self.worker.status_ready.connect(self._on_status)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        self.start_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.capture_btn.setVisible(True)
        self.retake_btn.setVisible(False)
        self.device_combo.setEnabled(False)
        self.resolution_combo.setEnabled(False)

    def _on_status(self, status: FrameStatus) -> None:
        self.canvas.set_status(status.face_detected, status.brightness, status.guidance)

        settings = self._get_settings()
        standardised = settings.get("standardised_mode", False)
        self.checklist_panel.setVisible(standardised)
        if standardised:
            self._update_checklist(status)

        if not settings.get("auto_capture", False) or not status.face_detected:
            self._face_steady_since = None
            return
        if standardised and not status.all_standardised_checks_pass:
            self._face_steady_since = None
            return

        now = time.monotonic()
        if self._face_steady_since is None:
            self._face_steady_since = now
            return
        if (
            now - self._face_steady_since >= 1.5
            and self.capture_btn.isVisible()
            and self.capture_btn.isEnabled()
            and not self.canvas.is_counting_down
        ):
            self._face_steady_since = None
            self.capture()

    def _update_checklist(self, status: FrameStatus) -> None:
        for name, ok in status.checklist():
            icon_lbl = self._checklist_icons.get(name)
            if icon_lbl is None:
                continue
            icon_name = "fa5s.check-circle" if ok else "fa5s.times-circle"
            color = icon_color("success") if ok else icon_color("warning")
            icon_lbl.setPixmap(icon_pixmap(icon_name, color, size=13))

    def stop_camera(self) -> None:
        if self.worker:
            self.worker.stop()
            self.worker = None
        self._face_steady_since = None
        self.canvas.clear()
        self.start_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.capture_btn.setVisible(False)
        self.device_combo.setEnabled(True)
        self.resolution_combo.setEnabled(True)

    def capture(self) -> None:
        if not self.worker:
            return
        self.capture_btn.setEnabled(False)
        if self._get_settings().get("capture_countdown", True):
            self.canvas.start_countdown(3)
        else:
            self._do_capture()

    def _do_capture(self) -> None:
        if not self.worker:
            return
        self.worker.request_capture(burst_count=5)

        self._burst_timer = QTimer(self)
        self._burst_timer.setInterval(60)
        self._burst_timer.timeout.connect(self._poll_burst)
        self._burst_timer.start()

    def _poll_burst(self) -> None:
        if not self.worker:
            self._burst_timer.stop()
            return
        frame = self.worker.take_burst_result()
        if frame is not None:
            self._burst_timer.stop()
            self.capture_btn.setEnabled(True)
            self._captured_frame = frame
            self.worker.stop()
            self.worker = None
            self.canvas.set_captured_frame(frame)
            self.stop_btn.setVisible(False)
            self.capture_btn.setVisible(False)
            self.retake_btn.setVisible(True)
            self.captured.emit(frame)

    def retake(self) -> None:
        self._captured_frame = None
        self.canvas.clear()
        self.retake_btn.setVisible(False)
        self.start_camera()

    def current_frame(self) -> Optional[np.ndarray]:
        return self._captured_frame

    def _on_error(self, message: str) -> None:
        self.stop_camera()
        self.error.emit(message)

    def shutdown(self) -> None:
        if self.worker:
            self.worker.stop()
            self.worker = None
