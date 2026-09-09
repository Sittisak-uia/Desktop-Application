"""Application entry point for SQLite Task Manager PRO.

Creates the QApplication, initialises the database, shows the login
window, and on success opens the main window.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import QApplication

from task_manager.database import initialize_database, seed_default_user
from task_manager.ui.login_window import LoginWindow
from task_manager.ui.main_window import MainWindow


def _apply_light_theme(app: QApplication) -> None:
    """Force a light palette so text is never light-on-light.

    Qt auto-detects the OS colour mode (e.g. Windows dark mode) and hands
    unstyled widgets a light-text default palette.  Every explicitly
    styled control keeps its own colours (the dark sidebar, coloured
    buttons, etc.) while all other text -- labels, inputs, tables,
    dialogs, message boxes, placeholders -- becomes dark and readable.
    """
    text = "#2c3e50"
    placeholder = "#95a5a6"
    disabled_text = "#7f8c8d"

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#ecf0f1"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(text))
    pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8f9fa"))
    pal.setColor(QPalette.ColorRole.Text, QColor(text))
    pal.setColor(QPalette.ColorRole.Button, QColor("#ecf0f1"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(text))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#3498db"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(placeholder))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(text))
    pal.setColor(QPalette.ColorRole.Link, QColor("#3498db"))
    pal.setColor(QPalette.ColorRole.LinkVisited, QColor("#8e44ad"))
    # Disabled state: visible but clearly lighter than normal text.
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(disabled_text))
    pal.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.HighlightedText,
        QColor("#bdc3c7"),
    )
    pal.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.PlaceholderText,
        QColor("#bdc3c7"),
    )
    app.setPalette(pal)


def main() -> int:
    """Boot the Task Manager PRO application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Task Manager PRO")
    icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    from task_manager.ui.theme import apply_theme, get_current_theme
    current_theme = get_current_theme()
    apply_theme(current_theme, app)

    # Ensure the database schema and default user exist
    initialize_database()
    seed_default_user()

    # Show login
    login = LoginWindow()
    result = login.exec()

    if login.is_authenticated:
        window = MainWindow()
        window.apply_theme(current_theme)
        window.show()
        return app.exec()

    return result


if __name__ == "__main__":
    sys.exit(main())
