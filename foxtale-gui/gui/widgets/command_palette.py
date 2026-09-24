"""A Ctrl+K quick-launcher: type-to-filter, Enter to run -- jump to any
page or run a common action without touching the mouse. Standard in
modern desktop apps (VS Code, Slack, Notion) and a fast way to get around
once the sidebar has this many destinations.
"""

from typing import Callable, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


class CommandPalette(QDialog):
    def __init__(self, commands: List[Tuple[str, Callable[[], None]]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Actions")
        self.setModal(True)
        self.setFixedWidth(420)
        self._commands = commands

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a page or action…")
        self.search.textChanged.connect(self._populate)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemActivated.connect(self._run_item)
        layout.addWidget(self.list)

        self._populate("")
        self.search.setFocus()

    def _populate(self, query: str) -> None:
        self.list.clear()
        q = query.strip().lower()
        for label, _action in self._commands:
            if q in label.lower():
                self.list.addItem(QListWidgetItem(label))
        if self.list.count():
            self.list.setCurrentRow(0)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.list.currentItem()
            if item:
                self._run_item(item)
            return
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            row = self.list.currentRow()
            step = 1 if event.key() == Qt.Key.Key_Down else -1
            self.list.setCurrentRow(max(0, min(row + step, self.list.count() - 1)))
            return
        super().keyPressEvent(event)

    def _run_item(self, item: QListWidgetItem) -> None:
        label = item.text()
        for cmd_label, action in self._commands:
            if cmd_label == label:
                self.accept()
                action()
                return
