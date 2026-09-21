"""Application-wide logging and a global crash handler.

A desktop app that just vanishes on an unhandled exception looks unfinished;
this logs the full traceback to a rotating local file and shows the user a
plain explanation instead of silently dying -- while making it just as
clear as everywhere else in the app that nothing was ever sent anywhere.
"""

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path.home() / ".foxtale_gui" / "logs"
LOG_PATH = LOG_DIR / "app.log"

_logger = logging.getLogger("foxtale")


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.info("Foxtale starting up")


def log_info(message: str) -> None:
    _logger.info(message)


def install_excepthook() -> None:
    def _handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _logger.error("Unhandled exception:\n%s", text)
        _show_crash_dialog(text)

    sys.excepthook = _handle


def _show_crash_dialog(text: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Foxtale hit an unexpected error")
        box.setText(
            "Something went wrong, but your data is safe — nothing was sent anywhere. "
            f"Details were written to:\n{LOG_PATH}"
        )
        box.setDetailedText(text)
        box.exec()
    except Exception:
        pass  # the crash handler itself must never crash
