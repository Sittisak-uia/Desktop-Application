"""Application entry point for Media Player PRO.

Creates the QApplication, shows the main window, and runs the event loop.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from media_player.main_window import MainWindow


def main() -> int:
    """Boot the Media Player PRO application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Media Player PRO")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
