"""Embedded matplotlib chart plotting each category's severity level over
time, so a user can see whether things are trending better or worse across
scans -- something the single-scan web report can't show."""

from datetime import datetime
from typing import List

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from engine.schemas import LEVEL_SCORE
from gui.core.storage import ScanRecord
from gui.theme import CATEGORY_QCOLOR

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
        self.ax.set_ylim(-0.4, 3.4)
        self.ax.set_yticks([0, 1, 2, 3])
        self.ax.set_yticklabels(["Minimal", "Mild", "Moderate", "Noticeable"])
        self.ax.spines[["top", "right"]].set_visible(False)
        self.fig.patch.set_alpha(0)
        self.ax.patch.set_alpha(0)

    def plot(self, records: List[ScanRecord]) -> None:
        self.ax.clear()
        self._style_axes()

        if len(records) < 2:
            self.ax.text(0.5, 0.5, "Need at least 2 scans to show a trend", ha="center", va="center",
                         transform=self.ax.transAxes, color="#8993a8")
            self.draw()
            return

        ordered = sorted(records, key=lambda r: r.timestamp)
        x_labels = [datetime.fromisoformat(r.timestamp).strftime("%m/%d %H:%M") for r in ordered]
        x = list(range(len(ordered)))

        for label, getter in SERIES:
            y = [LEVEL_SCORE[getter(r.analysis).level] for r in ordered]
            self.ax.plot(x, y, marker="o", label=label, color=CATEGORY_QCOLOR.get(label, "#3b8dff"), linewidth=2)

        self.ax.set_xticks(x)
        self.ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8)
        self.ax.legend(loc="upper left", fontsize=8, frameon=False)
        self.draw()
