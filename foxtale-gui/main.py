"""Foxtale Desktop -- native GUI entry point.

Run locally with:
    python main.py
"""

import sys

from PySide6.QtWidgets import QApplication, QSplashScreen

from gui.assets import app_icon, splash_pixmap
from gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Foxtale")
    app.setWindowIcon(app_icon())

    splash = QSplashScreen(splash_pixmap())
    splash.show()
    app.processEvents()

    window = MainWindow()
    window.setWindowIcon(app_icon())
    window.show()
    splash.finish(window)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
