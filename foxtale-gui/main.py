"""Foxtale Desktop -- native GUI entry point.

Run locally with:
    python main.py
"""

import sys

from PySide6.QtWidgets import QApplication, QSplashScreen

from gui.assets import app_icon, splash_pixmap
from gui.core.error_handling import install_excepthook, setup_logging
from gui.main_window import MainWindow
from gui.version import __version__


def main() -> int:
    setup_logging()
    install_excepthook()

    app = QApplication(sys.argv)
    app.setApplicationName("Foxtale")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    # Closing the window shouldn't silently end the process when "minimize to
    # tray" is on -- MainWindow.closeEvent() decides whether to hide or quit,
    # and explicitly calls quit() itself when it does want to exit.
    app.setQuitOnLastWindowClosed(False)

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
