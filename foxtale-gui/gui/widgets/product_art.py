"""Product image slot for the skincare cards.

If a photo exists it is shown (a user-added file in ~/.foxtale_gui/product_photos
or a bundled one in assets/products, named <product id>.png/.jpg/.webp). Until
then a clean packaging illustration (tube / dropper bottle / jar) is painted
in the product's routine-step colour, labelled with its lead ingredient.
Clicking the slot lets the user pick their own photo of the product.
"""

import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFileDialog, QWidget

from gui.core import storage
from gui.core.skincare_advisor import Product
from gui.theme import get_current_theme

BUNDLED_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "products"
USER_DIR = storage.APP_DIR / "product_photos"
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")

# (light tile top, light tile bottom, packaging colour)
STEP_STYLE = {
    "cleanse": ("#e4f1ff", "#cfe4fb", "#3b8dff"),
    "treat": ("#ffece0", "#ffd9c2", "#e54a00"),
    "moisturize": ("#e0f6ef", "#c8ecdf", "#12a06a"),
    "protect": ("#fff5d9", "#ffe9ae", "#e0a100"),
}


def find_photo(product_id: str) -> Optional[Path]:
    for folder in (USER_DIR, BUNDLED_DIR):
        for ext in EXTENSIONS:
            candidate = folder / f"{product_id}{ext}"
            if candidate.exists():
                return candidate
    return None


class ProductImage(QWidget):
    photo_changed = Signal()

    def __init__(self, product: Product, height: int = 190, parent=None):
        super().__init__(parent)
        self._product = product
        self.setFixedHeight(height)
        self.setMinimumWidth(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to use your own photo of this product")
        self._pixmap: Optional[QPixmap] = None
        self._load()

    def _load(self) -> None:
        path = find_photo(self._product.id)
        pm = QPixmap(str(path)) if path else QPixmap()
        self._pixmap = pm if not pm.isNull() else None
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a photo of this product", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        USER_DIR.mkdir(parents=True, exist_ok=True)
        for ext in EXTENSIONS:  # replace any previous photo
            (USER_DIR / f"{self._product.id}{ext}").unlink(missing_ok=True)
        shutil.copyfile(path, USER_DIR / f"{self._product.id}{Path(path).suffix.lower()}")
        self._load()
        self.photo_changed.emit()

    # ------------------------------------------------------------ painting
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = get_current_theme() == "dark"
        top, bottom, accent = STEP_STYLE.get(self._product.step, STEP_STYLE["treat"])
        rect = QRectF(self.rect())

        tile = QPainterPath()
        tile.addRoundedRect(rect, 14, 14)
        p.setClipPath(tile)
        if self._pixmap is not None:
            # Fit the whole picture inside the tile; fill any spare width with the picture's own
            # background colour so the tile looks seamless.
            edge = self._pixmap.toImage().pixelColor(2, 2)
            p.fillRect(rect, edge)
            scaled = self._pixmap.scaled(
                int(rect.width()), int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(int((rect.width() - scaled.width()) / 2), int((rect.height() - scaled.height()) / 2), scaled)
            return

        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if dark:
            grad.setColorAt(0, QColor(accent).darker(420))
            grad.setColorAt(1, QColor(accent).darker(560))
        else:
            grad.setColorAt(0, QColor(top))
            grad.setColorAt(1, QColor(bottom))
        p.fillRect(rect, grad)

        cx = rect.width() / 2
        base = rect.height() - 16
        body = QColor("#ffffff")
        body.setAlpha(235 if not dark else 220)
        col = QColor(accent)
        shape = self._product.shape

        # soft floor shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawEllipse(QPointF(cx, base + 2), 38, 5)

        p.setBrush(body)
        if shape == "jar":
            w, h = 100, 56
            p.drawRoundedRect(QRectF(cx - w / 2, base - h, w, h), 10, 10)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(cx - w / 2 - 2, base - h - 16, w + 4, 18), 6, 6)
            label = QRectF(cx - 40, base - h + 10, 80, 34)
        elif shape == "dropper":
            w, h = 66, 78
            p.drawRoundedRect(QRectF(cx - w / 2, base - h, w, h), 9, 9)
            p.setBrush(col)
            p.drawRect(QRectF(cx - 11, base - h - 12, 22, 13))
            p.setBrush(col.darker(115))
            bulb = QPainterPath()
            bulb.addRoundedRect(QRectF(cx - 9, base - h - 36, 18, 26), 8, 8)
            p.drawPath(bulb)
            label = QRectF(cx - 29, base - h + 14, 58, 46)
        else:  # tube, standing on its cap
            w, h = 62, 92
            path = QPainterPath()
            path.moveTo(cx - w / 2, base - h)
            path.lineTo(cx + w / 2, base - h)
            path.lineTo(cx + w / 2 - 5, base)
            path.lineTo(cx - w / 2 + 5, base)
            path.closeSubpath()
            p.drawPath(path)
            p.setBrush(col)
            p.drawRect(QRectF(cx - w / 2, base - h - 4, w, 9))  # crimped end
            label = QRectF(cx - 26, base - h + 16, 52, 46)

        # accent stripe + lead ingredient on the label
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(accent))
        p.drawRoundedRect(QRectF(label.left(), label.top(), label.width(), 3), 1.5, 1.5)
        lead = (self._product.key_ingredients[0] if self._product.key_ingredients else "").upper().replace("SODIUM ", "")
        font = QFont(self.font())
        font.setPixelSize(7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QPen(QColor("#1b2233")))
        p.drawText(label.adjusted(0, 6, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, lead)

        # "add photo" hint
        hint_font = QFont(self.font())
        hint_font.setPixelSize(9)
        p.setFont(hint_font)
        p.setPen(QColor(255, 255, 255, 190) if dark else QColor(27, 34, 51, 130))
        p.drawText(rect.adjusted(0, 0, 0, -3), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, "Click to add photo")
