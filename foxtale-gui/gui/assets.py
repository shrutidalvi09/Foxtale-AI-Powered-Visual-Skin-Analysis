"""Generated brand assets: app icon, splash screen, and a reusable card
drop-shadow -- drawn programmatically so the app ships with a real icon and
launch screen without needing external image files."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

NAVY = "#0b1224"
FOX = "#ff8a3d"
FOX_DARK = "#f2721f"
ACCENT = "#3b8dff"


def _brand_mark(size: int) -> QPixmap:
    """A rounded-square gradient lettermark ('F') -- reliable across
    platforms, unlike drawing an emoji glyph via QPainter."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rect = QRectF(0, 0, size, size)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(ACCENT))
    grad.setColorAt(1, QColor(FOX))
    painter.setBrush(grad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, size * 0.26, size * 0.26)

    font = QFont("Segoe UI", int(size * 0.5), QFont.Weight.Black)
    painter.setFont(font)
    painter.setPen(QColor("white"))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "F")

    painter.end()
    return pixmap


def app_icon(size: int = 256) -> QIcon:
    return QIcon(_brand_mark(size))


def brand_pixmap(size: int = 28) -> QPixmap:
    return _brand_mark(size)


def splash_pixmap(width: int = 520, height: int = 320) -> QPixmap:
    pixmap = QPixmap(width, height)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rect = QRectF(0, 0, width, height)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0, QColor(NAVY))
    grad.setColorAt(1, QColor("#16214a"))
    painter.setBrush(grad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, 22, 22)

    mark = _brand_mark(84)
    painter.drawPixmap(width // 2 - 42, 56, mark)

    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", 26, QFont.Weight.Black))
    painter.drawText(QRectF(0, 156, width, 44), Qt.AlignmentFlag.AlignCenter, "Foxtale")

    painter.setPen(QColor("#9aa6c3"))
    painter.setFont(QFont("Segoe UI", 11))
    painter.drawText(QRectF(0, 198, width, 28), Qt.AlignmentFlag.AlignCenter, "AI-Powered Visual Skin Analysis")

    painter.setPen(QColor("#5ea8ff"))
    painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
    painter.drawText(QRectF(0, height - 44, width, 24), Qt.AlignmentFlag.AlignCenter, "Starting up…")

    painter.end()
    return pixmap


def apply_card_shadow(widget: QWidget, blur: int = 26, y_offset: int = 6, alpha: int = 35) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(11, 18, 36, alpha))
    widget.setGraphicsEffect(effect)
