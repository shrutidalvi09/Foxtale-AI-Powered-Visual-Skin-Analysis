from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

STEPS = [
    "Detecting face...",
    "Analyzing skin regions...",
    "Checking visible texture...",
    "Checking visible redness...",
    "Generating report...",
]


class ScanProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.label = QLabel(STEPS[0])
        self.label.setStyleSheet("font-weight: 600;")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("Muted")

        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        layout.addWidget(self.percent_label)

        self._step = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self._step = 0
        self.label.setText(STEPS[0])
        self.bar.setValue(10)
        self.percent_label.setText("10%")
        self._timer.start(650)

    def _advance(self) -> None:
        self._step = min(self._step + 1, len(STEPS) - 1)
        self.label.setText(STEPS[self._step])
        pct = int(((self._step + 1) / len(STEPS)) * 90)
        self.bar.setValue(pct)
        self.percent_label.setText(f"{pct}%")

    def finish(self) -> None:
        self._timer.stop()
        self.label.setText("Analysis complete")
        self.bar.setValue(100)
        self.percent_label.setText("100%")
