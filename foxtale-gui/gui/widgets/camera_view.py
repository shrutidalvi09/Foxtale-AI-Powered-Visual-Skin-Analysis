"""Live camera preview with a futuristic scanning-frame overlay: corner
brackets, an animated sweep line, a live brightness meter, and a face-lock
indicator that goes green once a face is framed -- all computed locally,
before the user even presses Capture.
"""

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.assets import apply_card_shadow
from gui.core.camera_worker import CameraWorker, list_camera_indices


def _bgr_to_pixmap(frame: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class CameraCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self._pixmap: Optional[QPixmap] = None
        self._mode = "off"  # off | live | captured
        self._face_detected = False
        self._brightness = 0.0
        self._phase = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(35)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        if self._mode == "live":
            self._phase = (self._phase + 0.03) % 1.0
            self.update()

    def set_live_frame(self, frame_bgr: np.ndarray) -> None:
        self._mode = "live"
        self._pixmap = _bgr_to_pixmap(frame_bgr)
        self.update()

    def set_captured_frame(self, frame_bgr: np.ndarray) -> None:
        self._mode = "captured"
        self._pixmap = _bgr_to_pixmap(frame_bgr)
        self.update()

    def set_status(self, face_detected: bool, brightness: float) -> None:
        self._face_detected = face_detected
        self._brightness = brightness
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

        painter.setBrush(QColor("#0b1224"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(square, 24, 24)

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

        color = QColor("#22c55e") if self._face_detected else QColor("#5ea8ff")
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

        status_text = "Face detected — hold still" if self._face_detected else "Position your face inside the frame"
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


class CameraView(QWidget):
    captured = Signal(np.ndarray)
    error = Signal(str)

    def __init__(self, get_settings, parent=None):
        super().__init__(parent)
        self._get_settings = get_settings
        self.worker: Optional[CameraWorker] = None
        self._captured_frame: Optional[np.ndarray] = None
        self._burst_timer: Optional[QTimer] = None

        layout = QVBoxLayout(self)
        self.canvas = CameraCanvas()
        apply_card_shadow(self.canvas, blur=34, y_offset=12, alpha=45)
        layout.addWidget(self.canvas)

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

        self.worker = CameraWorker(camera_index=index, width=width, height=height)
        self.worker.frame_ready.connect(self.canvas.set_live_frame)
        self.worker.status_ready.connect(self.canvas.set_status)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        self.start_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.capture_btn.setVisible(True)
        self.retake_btn.setVisible(False)
        self.device_combo.setEnabled(False)
        self.resolution_combo.setEnabled(False)

    def stop_camera(self) -> None:
        if self.worker:
            self.worker.stop()
            self.worker = None
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
