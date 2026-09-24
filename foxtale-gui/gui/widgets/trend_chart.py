"""Embedded matplotlib chart plotting each category's severity level over
time, so a user can see whether things are trending better or worse across
scans -- something the single-scan web report can't show."""

from datetime import datetime
from typing import List

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from engine.schemas import LEVEL_SCORE
from gui.core.storage import ScanRecord
from gui.theme import CATEGORY_QCOLOR, get_current_theme, muted_text_color

# Matplotlib chrome (spines/ticks/labels) doesn't inherit Qt's QSS theme, so
# it's synced to the active theme by hand here.
_AXIS_COLORS = {
    "light": {"text": "#33415c", "spine": "#d9deeb"},
    "dark": {"text": "#e7ecf7", "spine": "#263457"},
}

SERIES = [
    ("Acne-like spots", lambda a: a.acne_like_spots),
    ("Redness", lambda a: a.redness),
    ("Texture", lambda a: a.texture),
    ("Dryness indicators", lambda a: a.dryness_indicators),
]


class TrendChart(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 3), tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)
        self._style_axes()

    def _style_axes(self) -> None:
        palette = _AXIS_COLORS["dark" if get_current_theme() == "dark" else "light"]
        self.ax.set_ylim(-0.4, 3.4)
        self.ax.set_yticks([0, 1, 2, 3])
        self.ax.set_yticklabels(["Minimal", "Mild", "Moderate", "Noticeable"])
        self.ax.spines[["top", "right"]].set_visible(False)
        for spine in ("left", "bottom"):
            self.ax.spines[spine].set_color(palette["spine"])
        self.ax.tick_params(colors=palette["text"], labelcolor=palette["text"])
        self.fig.patch.set_alpha(0)
        self.ax.patch.set_alpha(0)

    def plot(self, records: List[ScanRecord]) -> None:
        self.ax.clear()
        self._style_axes()
        palette = _AXIS_COLORS["dark" if get_current_theme() == "dark" else "light"]

        if len(records) < 2:
            self.ax.text(0.5, 0.5, "Need at least 2 scans to show a trend", ha="center", va="center",
                         transform=self.ax.transAxes, color=muted_text_color())
            self.draw()
            return

        ordered = sorted(records, key=lambda r: r.timestamp)
        x_labels = [datetime.fromisoformat(r.timestamp).strftime("%m/%d %H:%M") for r in ordered]
        x = list(range(len(ordered)))

        for label, getter in SERIES:
            y = [LEVEL_SCORE[getter(r.analysis).level] for r in ordered]
            self.ax.plot(x, y, marker="o", label=label, color=CATEGORY_QCOLOR.get(label, "#3b8dff"), linewidth=2)

        self.ax.set_xticks(x)
        self.ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8, color=palette["text"])
        legend = self.ax.legend(loc="upper left", fontsize=8, frameon=False)
        for text in legend.get_texts():
            text.set_color(palette["text"])
        self.draw()
