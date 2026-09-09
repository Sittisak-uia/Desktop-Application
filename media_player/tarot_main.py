"""Application entry point for the Tarot App.

Creates the QApplication, shows the TarotWindow, and runs the event loop.
This is a separate entry point from the Media Player PRO main module.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from media_player.tarot_window import TarotWindow


def main() -> int:
    """Boot the Tarot App."""
    app = QApplication(sys.argv)
    app.setApplicationName("Tarot Reading")
    window = TarotWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
