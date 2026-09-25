"""The "Skin Health Report" card on the Analysis page: overall 0-100 score
ring, a plain-language summary, per-region score bars, every measured
category with its real numbers, and changes since the previous scan.
"""

from typing import List, Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from engine.schemas import SkinAnalysis
from engine.skin_analysis import score_label
from gui.assets import apply_card_shadow, icon_circle
from gui.core import report_content as rc
from gui.theme import FOX, get_current_theme, level_pill_colors

SCORE_COLORS = [(85, "#10b981"), (70, "#84cc16"), (55, "#f59e0b"), (0, "#f43f5e")]


def score_color(score: int) -> str:
    for floor, color in SCORE_COLORS:
        if score >= floor:
            return color
    return SCORE_COLORS[-1][1]


def _track_color() -> QColor:
    return QColor("#2b3346") if get_current_theme() == "dark" else QColor("#eceff5")


class ScoreRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(132, 132)
        self._score: Optional[int] = None

    def set_score(self, score: Optional[int]) -> None:
        self._score = score
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        pen = QPen(_track_color(), 11)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawEllipse(rect)
        text_color = QColor("#f3f4f8") if get_current_theme() == "dark" else QColor("#1b2233")
        if self._score is None:
            p.setPen(text_color)
            f = QFont(self.font())
            f.setPointSize(20)
            f.setBold(True)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "--")
            return
        pen.setColor(QColor(score_color(self._score)))
        p.setPen(pen)
        p.drawArc(rect, 90 * 16, int(-360 * 16 * self._score / 100.0))
        p.setPen(text_color)
        f = QFont(self.font())
        f.setPixelSize(34)
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect().adjusted(0, -8, 0, 0), Qt.AlignmentFlag.AlignCenter, str(self._score))
        f.setPixelSize(11)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#8a93a8"))
        p.drawText(self.rect().adjusted(0, 40, 0, 0), Qt.AlignmentFlag.AlignCenter, "out of 100")


class ScoreBar(QWidget):
    def __init__(self, score: int, parent=None):
        super().__init__(parent)
        self._score = score
        self.setFixedHeight(10)
        self.setMinimumWidth(80)

    def sizeHint(self) -> QSize:
        return QSize(160, 10)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_track_color())
        p.drawRoundedRect(r, 5, 5)
        p.setBrush(QColor(score_color(self._score)))
        p.drawRoundedRect(QRectF(0, 0, max(10.0, r.width() * self._score / 100.0), r.height()), 5, 5)


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


class ReportCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        apply_card_shadow(self, blur=20, y_offset=5, alpha=20)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(icon_circle("fa5s.clipboard-check", FOX, "#fde8da", size=42, icon_size=17))
        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel("Skin Health Report")
        title.setObjectName("CardTitle")
        title.setStyleSheet("font-size: 14.5px;")
        col.addWidget(title)
        sub = QLabel("Measured from the visible skin in your photo. Not a medical diagnosis.")
        sub.setObjectName("SubHeading")
        sub.setWordWrap(True)
        col.addWidget(sub)
        header.addLayout(col, stretch=1)
        outer.addLayout(header)

        top = QHBoxLayout()
        top.setSpacing(22)
        self.ring = ScoreRing()
        top.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignTop)

        summary_col = QVBoxLayout()
        summary_col.setSpacing(6)
        self.verdict = QLabel()
        self.verdict.setStyleSheet("font-size: 20px; font-weight: 800; background: transparent;")
        summary_col.addWidget(self.verdict)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("background: transparent;")
        summary_col.addWidget(self.summary)
        self.changes = QLabel()
        self.changes.setWordWrap(True)
        self.changes.setObjectName("Muted")
        summary_col.addWidget(self.changes)
        summary_col.addStretch()
        top.addLayout(summary_col, stretch=1)

        self.regions_box = QVBoxLayout()
        self.regions_box.setSpacing(6)
        regions_wrap = QWidget()
        regions_wrap.setMinimumWidth(320)
        regions_wrap.setStyleSheet("background: transparent;")
        regions_wrap.setLayout(self.regions_box)
        top.addWidget(regions_wrap, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(top)

        rule = QFrame()
        rule.setObjectName("Divider")
        outer.addWidget(rule)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(10)
        self.grid.setColumnStretch(2, 1)
        outer.addLayout(self.grid)

    def set_data(self, analysis: SkinAnalysis, previous: Optional[SkinAnalysis] = None) -> None:
        score = analysis.overall_score
        self.ring.set_score(score)
        if score is None:
            self.verdict.setText("Detailed report unavailable")
            self.verdict.setStyleSheet("font-size: 18px; font-weight: 800; background: transparent;")
            self.summary.setText(
                "This scan was saved by an earlier version of Foxtale. Run a new scan to get the "
                "overall score, region scores and detailed measurements."
            )
            self.changes.setText("")
        else:
            self.verdict.setText(score_label(score))
            self.verdict.setStyleSheet(
                f"font-size: 20px; font-weight: 800; color: {score_color(score)}; background: transparent;"
            )
            self.summary.setText(rc.overall_summary(analysis))
            changes = rc.compare_with_previous(analysis, previous)
            self.changes.setText("\n".join(changes[:3]))
            self.changes.setVisible(bool(changes))

        _clear(self.regions_box)
        head = QLabel("REGION SCORES")
        head.setObjectName("Muted")
        head.setStyleSheet("font-size: 10.5px; font-weight: 800; letter-spacing: 1px; background: transparent;")
        self.regions_box.addWidget(head)
        for row in rc.region_rows(analysis):
            line = QGridLayout()
            line.setHorizontalSpacing(8)
            line.setVerticalSpacing(2)
            name = QLabel(f"{row.name}  <span style='font-weight:400; color:#8a93a8; font-size:10.5px;'>"
                          f"{row.concern}</span>")
            name.setTextFormat(Qt.TextFormat.RichText)
            name.setStyleSheet("font-weight: 700; font-size: 12px; background: transparent;")
            val = QLabel(str(row.score))
            val.setStyleSheet("font-weight: 800; font-size: 12px; background: transparent;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            line.addWidget(name, 0, 0)
            line.addWidget(val, 0, 1)
            line.addWidget(ScoreBar(row.score), 1, 0, 1, 2)
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            wrap.setLayout(line)
            self.regions_box.addWidget(wrap)
        if not analysis.region_scores:
            note = QLabel("Region scores appear on new scans.")
            note.setObjectName("Muted")
            self.regions_box.addWidget(note)

        _clear(self.grid)
        rows = rc.category_rows(analysis)
        for i, row in enumerate(rows):
            label = QLabel(row.label)
            label.setStyleSheet("font-weight: 700; background: transparent;")
            label.setMinimumWidth(130)
            self.grid.addWidget(label, i, 0)

            bg, fg = level_pill_colors(row.level)
            pill = QLabel(row.level.title())
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setFixedSize(92, 26)
            pill.setStyleSheet(
                f"background-color: {bg}; color: {fg}; border: none; border-radius: 13px; "
                "font-weight: 800; font-size: 11.5px;"
            )
            self.grid.addWidget(pill, i, 1)

            text = QLabel(row.measurement if analysis.metrics else row.meaning)
            text.setWordWrap(True)
            text.setObjectName("SubHeading")
            text.setToolTip(row.meaning)
            self.grid.addWidget(text, i, 2)

            conf = QLabel(f"{int(row.confidence * 100)}% confidence")
            conf.setObjectName("Muted")
            self.grid.addWidget(conf, i, 3)
