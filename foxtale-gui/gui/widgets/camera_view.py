"""Live camera preview with a friendly scanning-frame overlay: corner
brackets, an animated sweep line, a live brightness meter, and a face-lock
indicator that goes from brand-orange to green once a face is framed --
all computed locally, before the user even presses Capture. A small status
rail beside the preview shows lighting / face / centering at a glance.
"""

import time
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from engine.quality import FrameStatus
from gui.assets import apply_card_shadow, apply_cta_glow, icon as make_icon, icon_pixmap
from gui.core.camera_worker import CameraWorker, list_camera_indices
from gui.theme import FOX, ORANGE_TEXT, get_current_theme, icon_color, muted_text_color

CANVAS_RADIUS = 22
SINGLE_ROW_CONTROLS_FROM = 800  # camera-column width from which the buttons sit beside the combos


def _bgr_to_pixmap(frame: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class CameraCanvas(QWidget):
    countdown_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(380, 282)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
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

    # Landscape preview: the height always follows the width.
    ASPECT = 0.74

    def hasHeightForWidth(self) -> bool:  # noqa: N802 (Qt override)
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 (Qt override)
        return int(width * self.ASPECT)

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        return QSize(640, int(640 * self.ASPECT))

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

    # ------------------------------------------------------------- painting

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())

        clip = QPainterPath()
        clip.addRoundedRect(rect, CANVAS_RADIUS, CANVAS_RADIUS)
        painter.setClipPath(clip)

        if self._pixmap:
            scaled = self._pixmap.scaled(
                rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() - (scaled.width() - rect.width()) / 2
            y = rect.y() - (scaled.height() - rect.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            self._draw_idle_background(painter, rect)

        if self._mode == "live":
            self._draw_scan_overlay(painter, rect)
        elif self._mode == "off":
            self._draw_idle_content(painter, rect)

        painter.end()

    @staticmethod
    def _draw_idle_background(painter: QPainter, rect: QRectF) -> None:
        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, QColor("#22262f"))
        base.setColorAt(1.0, QColor("#0d101b"))
        painter.fillRect(rect, base)
        glow = QRadialGradient(rect.right() - rect.width() * 0.12, rect.top() + rect.height() * 0.1, rect.width() * 0.6)
        glow.setColorAt(0.0, QColor(122, 58, 78, 120))
        glow.setColorAt(1.0, QColor(122, 58, 78, 0))
        painter.fillRect(rect, glow)

    @staticmethod
    def _draw_brackets(painter: QPainter, rect: QRectF, color: QColor, inset: float, arm: float, width: float) -> None:
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        x0, y0 = rect.left() + inset, rect.top() + inset
        x1, y1 = rect.right() - inset, rect.bottom() - inset
        for sx, sy, dx, dy in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
            painter.drawLine(QPointF(sx, sy), QPointF(sx + dx * arm, sy))
            painter.drawLine(QPointF(sx, sy), QPointF(sx, sy + dy * arm))

    def _draw_idle_content(self, painter: QPainter, rect: QRectF) -> None:
        self._draw_brackets(painter, rect, QColor("white"), inset=24, arm=48, width=4)

        w, h = rect.width(), rect.height()
        ox, oy = rect.left(), rect.top()

        def half(sign: int) -> QPainterPath:
            def pt(dx: float, y: float) -> QPointF:
                return QPointF(ox + (0.5 + sign * dx) * w, oy + y * h)
            path = QPainterPath()
            path.moveTo(pt(0, 0.12))
            path.cubicTo(pt(0.13, 0.12), pt(0.18, 0.30), pt(0.165, 0.44))
            path.cubicTo(pt(0.155, 0.54), pt(0.11, 0.61), pt(0.06, 0.66))
            path.cubicTo(pt(0.06, 0.74), pt(0.10, 0.79), pt(0.22, 0.85))
            path.cubicTo(pt(0.30, 0.89), pt(0.38, 0.93), pt(0.42, 1.0))
            return path

        dash = QPen(QColor(255, 255, 255, 105), 2)
        dash.setDashPattern([4, 5])
        dash.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(dash)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(half(1))
        painter.drawPath(half(-1))

        cx, cy = rect.center().x(), rect.center().y()
        cam = icon_pixmap("fa5s.camera", "#f1b391", size=34)
        dpr = cam.devicePixelRatio()
        painter.drawPixmap(int(cx - cam.width() / dpr / 2), int(cy - 52), cam)

        title_font = QFont(painter.font())
        title_font.setPointSizeF(11.5)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(ox, cy - 6, w, 24), Qt.AlignmentFlag.AlignCenter, "Camera is off")
        sub_font = QFont(painter.font())
        sub_font.setPointSizeF(9.5)
        sub_font.setWeight(QFont.Weight.Normal)
        painter.setFont(sub_font)
        painter.setPen(QColor("#b9bfd0"))
        painter.drawText(QRectF(ox, cy + 18, w, 22), Qt.AlignmentFlag.AlignCenter, "Preview will appear here")

    def _draw_scan_overlay(self, painter: QPainter, rect: QRectF) -> None:
        frame_h = rect.height() * 0.80
        frame_w = min(rect.width() * 0.6, frame_h * 0.80)
        frame_rect = QRectF(0, 0, frame_w, frame_h)
        frame_rect.moveCenter(rect.center())

        color = QColor("#22c55e") if self._face_detected else QColor(FOX)
        self._draw_brackets(painter, frame_rect, color, inset=0, arm=26, width=4)

        sweep_y = frame_rect.top() + self._phase * frame_rect.height()
        sweep_color = QColor(color)
        sweep_color.setAlpha(140)
        painter.setPen(QPen(sweep_color, 2))
        painter.drawLine(QPointF(frame_rect.left() + 4, sweep_y), QPointF(frame_rect.right() - 4, sweep_y))

        pill_rect = QRectF(rect.left() + 16, rect.bottom() - 46, rect.width() - 32, 34)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(11, 18, 36, 210))
        painter.drawRoundedRect(pill_rect, 14, 14)
        painter.setPen(QColor("white"))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, self._guidance)

        meter_rect = QRectF(rect.left() + 16, rect.top() + 14, rect.width() - 32, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 40))
        painter.drawRoundedRect(meter_rect, 5, 5)
        fill_ratio = max(0.0, min(1.0, self._brightness / 255.0))
        fill_rect = QRectF(meter_rect.left(), meter_rect.top(), meter_rect.width() * fill_ratio, meter_rect.height())
        painter.setBrush(QColor("#22c55e") if self._brightness >= 60 else QColor("#f97316"))
        painter.drawRoundedRect(fill_rect, 5, 5)

        if self._countdown > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(11, 18, 36, 150))
            painter.drawRect(rect)
            painter.setPen(QColor("white"))
            font = QFont()
            font.setPointSize(80)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._countdown))


class StatusRail(QFrame):
    """A small vertical card beside the preview: lighting, face, centering.
    Each item is lit orange when satisfied, grey when not (or when the
    camera is off)."""

    ITEMS = [
        ("fa5s.sun", "Good lighting", "Low light", "Lighting"),
        ("fa5s.user", "Face detected", "Face not detected", "Face not detected"),
        ("fa5s.expand", "Face centered", "Center face", "Center face"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedWidth(118)
        apply_card_shadow(self, blur=20, y_offset=5, alpha=22)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        self._circles: list[QFrame] = []
        self._icons: list[QLabel] = []
        self._labels: list[QLabel] = []
        for i, (_icon, _ok, _bad, idle) in enumerate(self.ITEMS):
            if i > 0:
                dots = QLabel("⋮")
                dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
                dots.setStyleSheet("color: #b8c0d6; font-size: 14px;")
                layout.addWidget(dots)
            circle = QFrame()
            circle.setFixedSize(42, 42)
            inner = QVBoxLayout(circle)
            inner.setContentsMargins(0, 0, 0, 0)
            icon_lbl = QLabel()
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(icon_lbl)
            layout.addWidget(circle, alignment=Qt.AlignmentFlag.AlignHCenter)
            label = QLabel(idle)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            layout.addWidget(label)
            self._circles.append(circle)
            self._icons.append(icon_lbl)
            self._labels.append(label)
        self.reset()

    def reset(self) -> None:
        self.set_state(None, None, None)

    def set_state(self, lighting: Optional[bool], face: Optional[bool], centered: Optional[bool]) -> None:
        off_bg = "#f1f2f6" if get_current_theme() == "light" else "#1a2340"
        for i, state in enumerate((lighting, face, centered)):
            icon_name, ok_text, bad_text, idle_text = self.ITEMS[i]
            on = bool(state)
            text = idle_text if state is None else (ok_text if on else bad_text)
            self._circles[i].setStyleSheet(
                f"background-color: {'#fde8da' if on else off_bg}; border-radius: 21px; border: none;"
            )
            self._icons[i].setPixmap(icon_pixmap(icon_name, FOX if on else "#9aa3b8", size=18))
            self._labels[i].setText(text)
            color = ORANGE_TEXT if on else muted_text_color()
            self._labels[i].setStyleSheet(f"font-size: 10.5px; font-weight: 700; color: {color};")


def _labelled(text: str, widget: QWidget) -> QVBoxLayout:
    col = QVBoxLayout()
    col.setSpacing(6)
    label = QLabel(text)
    label.setObjectName("SubHeading")
    label.setStyleSheet("font-weight: 600;")
    col.addWidget(label)
    col.addWidget(widget)
    return col


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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        stage = QHBoxLayout()
        stage.setSpacing(18)
        self.rail = StatusRail()
        stage.addWidget(self.rail, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.canvas = CameraCanvas()
        apply_card_shadow(self.canvas, blur=34, y_offset=12, alpha=45)
        self.canvas.countdown_finished.connect(self._do_capture)
        stage.addWidget(self.canvas, stretch=1)
        layout.addLayout(stage)

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

        controls = QGridLayout()
        controls.setHorizontalSpacing(14)
        controls.setVerticalSpacing(12)
        controls.setColumnStretch(2, 1)
        self._controls = controls
        self._controls_compact = True  # starts stacked; goes single-row only when there is room

        self.device_combo = QComboBox()
        self.device_combo.setFixedHeight(48)
        self.device_combo.setMinimumWidth(150)
        for idx in list_camera_indices():
            self.device_combo.addItem(make_icon("fa5s.video", muted_text_color()), f"Camera {idx}", idx)
        controls.addLayout(_labelled("Device", self.device_combo), 0, 0)

        self.resolution_combo = QComboBox()
        self.resolution_combo.setFixedHeight(48)
        self.resolution_combo.setMinimumWidth(150)
        for label, (w, h) in [("HD 1280x720", (1280, 720)), ("VGA 640x480", (640, 480)), ("Full HD 1920x1080", (1920, 1080))]:
            self.resolution_combo.addItem(label, (w, h))
        controls.addLayout(_labelled("Resolution", self.resolution_combo), 0, 1)

        settings = self._get_settings()
        dev_idx = self.device_combo.findData(settings.get("camera_index", 0))
        if dev_idx >= 0:
            self.device_combo.setCurrentIndex(dev_idx)
        res_idx = self.resolution_combo.findData((settings.get("camera_width", 1280), settings.get("camera_height", 720)))
        if res_idx >= 0:
            self.resolution_combo.setCurrentIndex(res_idx)

        self.start_btn = self._button("  Start Camera", "fa5s.camera", "Cta", "white")
        self.start_btn.clicked.connect(self.start_camera)
        apply_cta_glow(self.start_btn)
        self.stop_btn = self._button("  Stop Camera", "fa5s.stop-circle", "Secondary", icon_color("primary"))
        self.stop_btn.clicked.connect(self.stop_camera)
        self.stop_btn.setVisible(False)
        self.capture_btn = self._button("  Capture", "fa5s.camera", "Cta", "white")
        self.capture_btn.clicked.connect(self.capture)
        apply_cta_glow(self.capture_btn)
        self.capture_btn.setVisible(False)
        self.retake_btn = self._button("  Retake", "fa5s.undo", "Secondary", icon_color("primary"))
        self.retake_btn.clicked.connect(self.retake)
        self.retake_btn.setVisible(False)
        self.import_btn = self._button("  Import Photo", "fa5s.upload", "Secondary", icon_color("primary"))
        self.import_btn.setToolTip("Analyze an existing photo from your computer instead of using the camera.")
        self.import_btn.clicked.connect(self.import_photo)

        self._button_row = QWidget()
        button_layout = QHBoxLayout(self._button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(14)
        for b in (self.start_btn, self.stop_btn, self.capture_btn, self.retake_btn, self.import_btn):
            button_layout.addWidget(b)
        controls.addWidget(self._button_row, 1, 0, 1, 4, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(controls)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        compact = self.width() < SINGLE_ROW_CONTROLS_FROM
        if compact == self._controls_compact:
            return
        self._controls_compact = compact
        self._controls.removeWidget(self._button_row)
        if compact:
            self._controls.addWidget(self._button_row, 1, 0, 1, 4, alignment=Qt.AlignmentFlag.AlignRight)
        else:
            self._controls.addWidget(self._button_row, 0, 3, alignment=Qt.AlignmentFlag.AlignBottom)

    @staticmethod
    def _button(text: str, icon_name: str, kind: str, icon_col: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setIcon(make_icon(icon_name, icon_col))
        btn.setIconSize(QSize(17, 17))
        btn.setObjectName(kind)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(48)
        return btn

    # ------------------------------------------------------------ lifecycle

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
        checks = dict(status.checklist())
        self.rail.set_state(status.brightness >= 60, status.face_detected, checks.get("Face centered", False))

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
        self.rail.reset()
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
            self.rail.reset()
            self.stop_btn.setVisible(False)
            self.capture_btn.setVisible(False)
            self.retake_btn.setVisible(True)
            self.captured.emit(frame)

    def import_photo(self) -> None:
        if self.canvas.is_counting_down:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import Photo", "", "Images (*.jpg *.jpeg *.png *.bmp)")
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            self.error.emit("Couldn't read that image file — please choose a JPG, PNG, or BMP.")
            return

        if self.worker:
            self.worker.stop()
            self.worker = None
        self._face_steady_since = None
        self._captured_frame = frame
        self.canvas.set_captured_frame(frame)
        self.rail.reset()
        self.start_btn.setVisible(False)
        self.stop_btn.setVisible(False)
        self.capture_btn.setVisible(False)
        self.retake_btn.setVisible(True)
        self.device_combo.setEnabled(True)
        self.resolution_combo.setEnabled(True)
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
