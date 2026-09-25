"""The "Recommended Skincare" section of the Analysis page.

A routine strip (skin type, focus areas, estimated cost), a Full / Morning /
Evening switch, and a responsive grid of product cards. Each card shows the
product picture, step, size and price, why it was picked for this face, and
a "How it works" drawer with usage notes.
"""

from typing import Callable, List, Optional

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from engine.schemas import SkinAnalysis
from gui.assets import apply_card_shadow, icon_circle
from gui.assets import icon as make_icon
from gui.core import skincare_advisor as adv
from gui.theme import FOX, get_current_theme, icon_color, muted_text_color
from gui.widgets.product_art import ProductImage

DISCLAIMER = (
    "Cosmetic suggestions based on what is visible in your photo, not medical advice. Patch-test new products "
    "and check the label. Product details are from foxtale.in as of {date} and can change. If your skin is "
    "painful, spreading or not improving, see a dermatologist."
)

CARD_MIN_WIDTH = 250
GRID_SPACING = 14


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


def _pill(text: str, accent: bool = False) -> QLabel:
    dark = get_current_theme() == "dark"
    if accent:
        bg, fg = ("#2a1d10", "#ffb27a") if dark else ("#fff1e7", "#c2410c")
    else:
        bg, fg = ("#1c2740", "#c9d3ea") if dark else ("#eef1f7", "#3b455c")
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background-color: {bg}; color: {fg}; border: none; border-radius: 11px; padding: 3px 10px; "
        "font-size: 11px; font-weight: 700;"
    )
    lbl.setFixedHeight(22)
    return lbl


def _rupees(amount: int) -> str:
    return f"₹{amount:,}"


class ProductCard(QFrame):
    def __init__(self, suggestion: adv.Suggestion, index: int, on_owned: Callable[[str, bool], None], parent=None):
        super().__init__(parent)
        p = suggestion.product
        dark = get_current_theme() == "dark"
        bg, border = ("#141c31", "#26314f") if dark else ("#ffffff", "#e6e9f2")
        self.setObjectName("ProductCard")
        self.setStyleSheet(
            f"QFrame#ProductCard {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
            "QFrame#ProductCard QLabel { background: transparent; }"
        )
        apply_card_shadow(self, blur=16, y_offset=4, alpha=16)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 14)
        v.setSpacing(10)

        v.addWidget(ProductImage(p, height=240))

        meta = QHBoxLayout()
        meta.setSpacing(6)
        step = QLabel(f"{index}  ·  {suggestion.step_label.upper()}")
        step.setStyleSheet(f"color: {FOX}; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        meta.addWidget(step)
        meta.addStretch()
        meta.addWidget(_pill(p.when))
        v.addLayout(meta)

        name = QLabel(p.name)
        name.setWordWrap(True)
        name.setMinimumHeight(40)
        name.setAlignment(Qt.AlignmentFlag.AlignTop)
        name.setStyleSheet("font-size: 13.5px; font-weight: 800;")
        v.addWidget(name)

        price_row = QHBoxLayout()
        price_row.setSpacing(8)
        if p.price_inr:
            price = QLabel(_rupees(p.price_inr))
            price.setStyleSheet("font-size: 17px; font-weight: 800;")
            price_row.addWidget(price)
            label = "MRP" if p.price_source == "retailer_mrp" else "on foxtale.in"
            tail = QLabel(f"{label} · {p.size}" if p.size else label)
        else:
            tail = QLabel(f"{p.size} · check price on foxtale.in" if p.size else "Check price on foxtale.in")
        tail.setObjectName("Muted")
        tail.setStyleSheet("font-size: 11px;")
        tail.setWordWrap(True)
        price_row.addWidget(tail, stretch=1)
        v.addLayout(price_row)

        ing = QLabel("  ·  ".join(p.key_ingredients[:3]))
        ing.setWordWrap(True)
        ing.setObjectName("Muted")
        ing.setStyleSheet("font-size: 11px;")
        v.addWidget(ing)

        why_head = QLabel("KEEP USING" if suggestion.owned else "WHY THIS FOR YOU")
        why_head.setObjectName("Muted")
        why_head.setStyleSheet("font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        v.addWidget(why_head)
        why = QLabel(suggestion.reason)
        why.setWordWrap(True)
        why.setStyleSheet("font-size: 12px;")
        v.addWidget(why)

        # "How it works" drawer
        self.details = QWidget()
        self.details.setStyleSheet("background: transparent;")
        dv = QVBoxLayout(self.details)
        dv.setContentsMargins(0, 0, 0, 0)
        dv.setSpacing(8)
        for head, body in (("HOW IT WORKS", p.how_it_works), ("HOW TO USE", p.how_to_use),
                           ("GOOD TO KNOW", p.caution)):
            if not body:
                continue
            h = QLabel(head)
            h.setObjectName("Muted")
            h.setStyleSheet("font-size: 10px; font-weight: 800; letter-spacing: 1px;")
            dv.addWidget(h)
            t = QLabel(body)
            t.setWordWrap(True)
            t.setStyleSheet("font-size: 12px;")
            dv.addWidget(t)
        self.details.setVisible(False)

        self.how_btn = QPushButton("  How it works")
        self.how_btn.setObjectName("PillChip")
        self.how_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.how_btn.setIconSize(QSize(12, 12))
        self.how_btn.clicked.connect(self._toggle)
        self._refresh_how()
        v.addWidget(self.how_btn)
        v.addWidget(self.details)

        v.addStretch(1)
        foot = QHBoxLayout()
        foot.setSpacing(8)
        self.owned_btn = QPushButton("  In my routine" if suggestion.owned else "  I use this")
        self.owned_btn.setObjectName("PillChip")
        self.owned_btn.setCheckable(True)
        self.owned_btn.setChecked(suggestion.owned)
        self.owned_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.owned_btn.setIconSize(QSize(13, 13))
        self.owned_btn.setIcon(make_icon("fa5s.check", FOX if suggestion.owned else muted_text_color()))
        self.owned_btn.toggled.connect(lambda checked, pid=p.id: on_owned(pid, checked))
        foot.addWidget(self.owned_btn)
        foot.addStretch()
        link = QPushButton()
        link.setObjectName("IconButton")
        link.setIcon(make_icon("fa5s.external-link-alt", icon_color("primary")))
        link.setIconSize(QSize(14, 14))
        link.setFixedSize(34, 34)
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.setToolTip("View on foxtale.in (opens your browser; this app never connects to the internet)")
        link.clicked.connect(lambda _=False, url=p.url: QDesktopServices.openUrl(QUrl(url)))
        foot.addWidget(link)
        v.addLayout(foot)

    def _toggle(self) -> None:
        self.details.setVisible(not self.details.isVisible())
        self._refresh_how()

    def _refresh_how(self) -> None:
        open_ = self.details.isVisible()
        self.how_btn.setText("  Hide details" if open_ else "  How it works")
        self.how_btn.setIcon(make_icon("fa5s.chevron-up" if open_ else "fa5s.chevron-down", muted_text_color()))


class SkincareCard(QFrame):
    def __init__(self, on_owned_changed: Callable[[str, bool], None], parent=None):
        super().__init__(parent)
        self._on_owned_changed = on_owned_changed
        self._analysis: Optional[SkinAnalysis] = None
        self._owned: List[str] = []
        self._suggestions: List[adv.Suggestion] = []
        self._when = "all"
        self._cols = 0
        self._cards: List[ProductCard] = []
        self.setObjectName("Card")
        apply_card_shadow(self, blur=20, y_offset=5, alpha=20)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(icon_circle("fa5s.pump-soap", FOX, "#fde8da", size=42, icon_size=17))
        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel("Recommended Skincare")
        title.setObjectName("CardTitle")
        title.setStyleSheet("font-size: 14.5px;")
        col.addWidget(title)
        sub = QLabel("A simple Foxtale routine matched to what your scan measured, and why each step should help.")
        sub.setObjectName("SubHeading")
        sub.setWordWrap(True)
        col.addWidget(sub)
        header.addLayout(col, stretch=1)
        outer.addLayout(header)

        self.profile_row = QHBoxLayout()
        self.profile_row.setSpacing(8)
        outer.addLayout(self.profile_row)

        # Full / Morning / Evening switch + cost summary
        controls = QHBoxLayout()
        controls.setSpacing(8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for key, label, icon_name in (("all", "Full routine", "fa5s.list"), ("AM", "Morning", "fa5s.sun"),
                                      ("PM", "Evening", "fa5s.moon")):
            b = QPushButton(f"  {label}")
            b.setObjectName("PillChip")
            b.setCheckable(True)
            b.setChecked(key == "all")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIconSize(QSize(13, 13))
            b.setIcon(make_icon(icon_name, muted_text_color()))
            b.clicked.connect(lambda _=False, k=key: self._set_when(k))
            self._group.addButton(b)
            controls.addWidget(b)
        controls.addStretch()
        self.cost_label = QLabel()
        self.cost_label.setStyleSheet("font-size: 12px; font-weight: 700; background: transparent;")
        controls.addWidget(self.cost_label)
        outer.addLayout(controls)

        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(GRID_SPACING)
        outer.addWidget(self.grid_host)

        self.note = QLabel()
        self.note.setObjectName("Muted")
        self.note.setWordWrap(True)
        self.note.setStyleSheet("font-size: 11px;")
        outer.addWidget(self.note)

    # ---------------------------------------------------------------- data
    def set_data(self, analysis: SkinAnalysis, owned_ids: Optional[List[str]] = None) -> None:
        self._analysis = analysis
        self._owned = list(owned_ids or [])
        profile = adv.skin_profile(analysis)
        _clear(self.profile_row)
        lead = QLabel("Your skin looks")
        lead.setStyleSheet("font-weight: 700; background: transparent;")
        self.profile_row.addWidget(lead)
        self.profile_row.addWidget(_pill(profile.skin_type.title(), accent=True))
        if profile.concerns:
            focus = QLabel("Focus on")
            focus.setStyleSheet("font-weight: 700; background: transparent; margin-left: 8px;")
            self.profile_row.addWidget(focus)
            for attr in profile.concerns[:3]:
                self.profile_row.addWidget(_pill(adv.CATEGORY_LABELS[attr].title()))
        self.profile_row.addStretch()

        self._suggestions = adv.recommend(analysis, self._owned)
        total, missing = adv.routine_cost(self._suggestions)
        if total:
            extra = f"  +  {missing} not priced" if missing else ""
            self.cost_label.setText(f"Products to buy: about {_rupees(total)}{extra}")
        elif self._suggestions:
            self.cost_label.setText("Check prices on foxtale.in")
        else:
            self.cost_label.setText("")
        self.note.setText(
            adv.catalog_price_note() + "\n" + DISCLAIMER.format(date=adv.catalog_date() or "the catalog date")
        )
        self._rebuild()

    def _set_when(self, key: str) -> None:
        self._when = key
        self._rebuild()

    def _rebuild(self) -> None:
        _clear(self.grid)
        self._cards = []
        suggestions = [s for s in self._suggestions if adv.in_routine(s, self._when)]
        if not suggestions:
            empty = QLabel("Product suggestions are unavailable right now (the product list could not be loaded).")
            empty.setObjectName("Muted")
            self.grid.addWidget(empty, 0, 0)
            return
        for i, sug in enumerate(suggestions, start=1):
            self._cards.append(ProductCard(sug, i, self._owned_toggled))
        self._cols = 0
        self._reflow()

    def _owned_toggled(self, product_id: str, owned: bool) -> None:
        # Toggling rebuilds the cards, so defer it until this click has finished.
        QTimer.singleShot(0, lambda: self._on_owned_changed(product_id, owned))

    # -------------------------------------------------------------- layout
    def _columns_for(self, width: int) -> int:
        return max(1, min(4, (width + GRID_SPACING) // (CARD_MIN_WIDTH + GRID_SPACING)))

    def _reflow(self) -> None:
        cols = self._columns_for(self.grid_host.width() or self.width() - 44)
        if cols == self._cols and self.grid.count() == len(self._cards):
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        for i, card in enumerate(self._cards):
            self.grid.addWidget(card, i // cols, i % cols)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)
        for c in range(cols, 5):
            self.grid.setColumnStretch(c, 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()
