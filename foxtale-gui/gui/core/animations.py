"""Small reusable animation/blur helpers used for the frosted-glass overlays
(Toast, LockScreen). Everything here is plain Qt (QGraphicsBlurEffect over a
grabbed QPixmap, QPropertyAnimation on opacity) -- a Qt-only approximation of
glassmorphism/acrylic, deliberately avoiding any OS-level window-compositing
API so it behaves the same on every platform.

Note: don't add a QGraphicsOpacityEffect (via fade_widget) to a widget that
already carries a QGraphicsDropShadowEffect (e.g. from assets.apply_card_
shadow) -- Qt only supports one QGraphicsEffect per widget, and stacking two
corrupts painting (observed as "QPainter: paint device can only be painted
by one painter at a time"). fade_widget() is safe on plain, effect-free
widgets only.
"""

from typing import Callable, Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsBlurEffect, QGraphicsOpacityEffect, QGraphicsPixmapItem, QGraphicsScene, QWidget,
)


def blur_pixmap(pixmap: QPixmap, radius: int = 24) -> QPixmap:
    """Return a Gaussian-blurred copy of `pixmap`, used as a frosted-glass
    backdrop behind an overlay."""
    if pixmap.isNull():
        return pixmap
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(pixmap)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    result = QPixmap(pixmap.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    scene.render(painter, QRectF(result.rect()), QRectF(pixmap.rect()))
    painter.end()
    return result


def fade_widget(
    widget: QWidget, start: float, end: float, duration: int = 220,
    on_finished: Optional[Callable[[], None]] = None,
) -> QPropertyAnimation:
    """Animate a widget's opacity from `start` to `end`. Keeps the effect and
    animation referenced on the widget itself (`_fade_effect`/`_fade_anim`)
    so they aren't garbage-collected mid-flight."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(start)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    if on_finished is not None:
        anim.finished.connect(on_finished)
    widget._fade_effect = effect  # keep alive
    widget._fade_anim = anim  # keep alive
    anim.start()
    return anim
