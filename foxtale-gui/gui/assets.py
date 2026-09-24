"""Brand assets: the real Foxtale logo (loaded from assets/), monochrome
icon helpers, and a reusable card drop-shadow.
"""

from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from gui import theme as _theme

NAVY = "#0b1224"
FOX = _theme.FOX
FOX_HOVER = _theme.FOX_HOVER
ACCENT = _theme.ACCENT
ACCENT_TEXT = _theme.ACCENT_TEXT

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_LOGO_FULL_PATH = _ASSETS_DIR / "logo_full.png"   # fox art + "foxtale" + tagline
_LOGO_MARK_PATH = _ASSETS_DIR / "logo_mark.png"   # just the fox line-art, transparent


def icon(name: str, color: str) -> QIcon:
    """A flat, single-color vector icon (Font Awesome via qtawesome) --
    never a multicolor emoji glyph."""
    return qta.icon(name, color=color)


def icon_pixmap(name: str, color: str, size: int = 20) -> QPixmap:
    return qta.icon(name, color=color).pixmap(size, size)


def icon_circle(icon_name: str, fg: str, bg: str, size: int = 44, icon_size: int = 18) -> QWidget:
    """A round, softly tinted badge with one flat icon centered in it."""
    from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

    circle = QFrame()
    circle.setFixedSize(size, size)
    circle.setStyleSheet(f"background-color: {bg}; border-radius: {size // 2}px; border: none;")
    inner = QVBoxLayout(circle)
    inner.setContentsMargins(0, 0, 0, 0)
    label = QLabel()
    label.setPixmap(icon_pixmap(icon_name, fg, size=icon_size))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    inner.addWidget(label)
    return circle


def logo_mark_pixmap(height: int = 30) -> QPixmap:
    """Just the fox line-art (no wordmark), scaled to a target height,
    for small contexts like the sidebar."""
    pm = QPixmap(str(_LOGO_MARK_PATH))
    return pm.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)


def logo_full_pixmap(height: int = 160) -> QPixmap:
    """The full lockup -- fox art + 'foxtale' + 'YOU GLOW DIFFERENT' -- as
    it appears in the source logo file, scaled to a target height."""
    pm = QPixmap(str(_LOGO_FULL_PATH))
    return pm.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)


# Kept as `brand_pixmap` for existing call sites.
def brand_pixmap(height: int = 30) -> QPixmap:
    return logo_mark_pixmap(height)


def app_icon(size: int = 256) -> QIcon:
    """Taskbar/window icon: the real fox mark centered on a white rounded
    tile with a thin brand-orange border, so it reads clearly at small
    sizes against any taskbar background."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    border_w = max(2, size * 0.05)
    rect = QRectF(border_w / 2, border_w / 2, size - border_w, size - border_w)
    painter.setBrush(QColor("white"))
    painter.setPen(QPen(QColor(FOX), border_w))
    painter.drawRoundedRect(rect, size * 0.26, size * 0.26)

    mark = logo_mark_pixmap(int(size * 0.5))
    painter.drawPixmap(int((size - mark.width()) / 2), int((size - mark.height()) / 2), mark)

    painter.end()
    return QIcon(pixmap)


def splash_pixmap(width: int = 480, height: int = 320) -> QPixmap:
    pixmap = QPixmap(width, height)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rect = QRectF(1, 1, width - 2, height - 2)
    painter.setBrush(QColor("white"))
    painter.setPen(QPen(QColor("#e7e9f0"), 2))
    painter.drawRoundedRect(rect, 20, 20)

    logo = logo_full_pixmap(150)
    painter.drawPixmap((width - logo.width()) // 2, 56, logo)

    painter.setPen(QColor("#5a6478"))
    painter.setFont(QFont("Segoe UI", 11))
    painter.drawText(QRectF(0, 222, width, 28), Qt.AlignmentFlag.AlignCenter, "AI-Powered Visual Skin Analysis")

    painter.setPen(QColor(ACCENT_TEXT))
    painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
    painter.drawText(QRectF(0, height - 40, width, 24), Qt.AlignmentFlag.AlignCenter, "Starting up…")

    painter.end()
    return pixmap


def apply_card_shadow(
    widget: QWidget, blur: int = 30, y_offset: int = 8, alpha: int = 28,
    rgb: tuple = (11, 18, 36),
) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(*rgb, alpha))
    widget.setGraphicsEffect(effect)


def apply_cta_glow(button: QWidget) -> None:
    """A soft brand-orange glow under a primary call-to-action button."""
    apply_card_shadow(button, blur=26, y_offset=8, alpha=85, rgb=(229, 74, 0))
