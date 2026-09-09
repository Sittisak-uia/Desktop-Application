"""Theme management and styling definitions for SQLite Task Manager PRO.

Supports Light Mode and Dark Mode with persistent theme storage using QSettings.
Centralizes palette construction, theme tokens, and dynamic stylesheet generators.
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

THEME_LIGHT = "light"
THEME_DARK = "dark"

_ORG_NAME = "TaskManagerPRO"
_APP_NAME = "TaskManagerPRO"
_KEY_THEME = "theme"

# Color tokens for Light theme
LIGHT_TEXT = "#2c3e50"
LIGHT_PLACEHOLDER = "#95a5a6"
LIGHT_MUTED = "#7f8c8d"
LIGHT_BORDER = "#bdc3c7"
LIGHT_BG_WINDOW = "#ecf0f1"
LIGHT_BG_CARD = "#ffffff"
LIGHT_BG_ALT = "#f8f9fa"
LIGHT_PRIMARY = "#3498db"
LIGHT_SIDEBAR = "#2c3e50"

# Color tokens for Dark theme
DARK_TEXT = "#f5f6fa"
DARK_PLACEHOLDER = "#8395a7"
DARK_MUTED = "#a4b0be"
DARK_BORDER = "#4b6584"
DARK_BG_WINDOW = "#1e272e"
DARK_BG_CARD = "#2d3436"
DARK_BG_ALT = "#252a2c"
DARK_PRIMARY = "#3498db"
DARK_SIDEBAR = "#181e24"


def get_settings() -> QSettings:
    """Return the application QSettings instance."""
    return QSettings(_ORG_NAME, _APP_NAME)


def get_current_theme() -> str:
    """Read the persisted theme name from QSettings, defaulting to 'light'."""
    settings = get_settings()
    val = settings.value(_KEY_THEME, THEME_LIGHT)
    val_str = str(val).lower() if val is not None else THEME_LIGHT
    return THEME_DARK if val_str == THEME_DARK else THEME_LIGHT


def set_current_theme(theme: str) -> None:
    """Save the selected theme name into QSettings."""
    theme_clean = THEME_DARK if theme.lower() == THEME_DARK else THEME_LIGHT
    settings = get_settings()
    settings.setValue(_KEY_THEME, theme_clean)
    settings.sync()


def create_light_palette() -> QPalette:
    """Construct the explicit light QPalette preventing light-on-light text."""
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(LIGHT_BG_WINDOW))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(LIGHT_TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(LIGHT_BG_CARD))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(LIGHT_BG_ALT))
    pal.setColor(QPalette.ColorRole.Text, QColor(LIGHT_TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(LIGHT_BG_WINDOW))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(LIGHT_TEXT))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(LIGHT_PRIMARY))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(LIGHT_PLACEHOLDER))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(LIGHT_TEXT))
    pal.setColor(QPalette.ColorRole.Link, QColor(LIGHT_PRIMARY))
    pal.setColor(QPalette.ColorRole.LinkVisited, QColor("#8e44ad"))

    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(LIGHT_MUTED))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(LIGHT_BORDER))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.PlaceholderText, QColor(LIGHT_BORDER))
    return pal


def create_dark_palette() -> QPalette:
    """Construct the dark QPalette ensuring clear contrast and light text."""
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(DARK_BG_WINDOW))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(DARK_TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(DARK_BG_CARD))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(DARK_BG_ALT))
    pal.setColor(QPalette.ColorRole.Text, QColor(DARK_TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(DARK_BG_CARD))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(DARK_TEXT))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(DARK_PRIMARY))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(DARK_PLACEHOLDER))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(DARK_BG_CARD))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(DARK_TEXT))
    pal.setColor(QPalette.ColorRole.Link, QColor(DARK_PRIMARY))
    pal.setColor(QPalette.ColorRole.LinkVisited, QColor("#9b59b6"))

    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(DARK_MUTED))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(DARK_BORDER))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.PlaceholderText, QColor(DARK_BORDER))
    return pal


def apply_theme(theme_name: str, app: QApplication | None = None) -> None:
    """Apply the application-level palette corresponding to theme_name."""
    if app is None:
        app = QApplication.instance()
    if app is None:
        return

    theme = theme_name.lower()
    if theme == THEME_DARK:
        app.setPalette(create_dark_palette())
    else:
        app.setPalette(create_light_palette())


# ---------------------------------------------------------------------------
# Reusable stylesheet generators
# ---------------------------------------------------------------------------

def get_title_color(theme: str) -> str:
    return DARK_TEXT if theme == THEME_DARK else LIGHT_TEXT


def get_subtitle_color(theme: str) -> str:
    return DARK_MUTED if theme == THEME_DARK else LIGHT_MUTED


def get_table_style(theme: str) -> str:
    if theme == THEME_DARK:
        return f"""
            QTableWidget {{
                background-color: {DARK_BG_CARD};
                alternate-background-color: {DARK_BG_ALT};
                color: {DARK_TEXT};
                gridline-color: {DARK_BORDER};
            }}
            QHeaderView::section {{
                background-color: {DARK_BG_ALT};
                color: {DARK_TEXT};
                border: none;
                border-bottom: 1px solid {DARK_BORDER};
                padding: 6px 8px;
                font-weight: bold;
            }}
            QTableWidget::item {{
                color: {DARK_TEXT};
            }}
            QTableWidget::item:selected {{
                background-color: {DARK_PRIMARY};
                color: white;
            }}
        """
    return f"""
        QTableWidget {{
            background-color: white;
            alternate-background-color: {LIGHT_BG_ALT};
            color: {LIGHT_TEXT};
        }}
        QHeaderView::section {{
            background-color: white;
            color: {LIGHT_TEXT};
            border: none;
            border-bottom: 1px solid {LIGHT_BORDER};
            padding: 6px 8px;
            font-weight: bold;
        }}
        QTableWidget::item {{
            color: {LIGHT_TEXT};
        }}
        QTableWidget::item:selected {{
            background-color: {LIGHT_PRIMARY};
            color: white;
        }}
    """


def get_input_style(theme: str) -> str:
    if theme == THEME_DARK:
        return f"""
            QLineEdit {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                padding: 8px;
            }}
            QLineEdit::placeholder {{ color: {DARK_PLACEHOLDER}; }}
        """
    return f"""
        QLineEdit {{
            background-color: white;
            color: {LIGHT_TEXT};
            border: 1px solid {LIGHT_BORDER};
            border-radius: 4px;
            padding: 8px;
        }}
        QLineEdit::placeholder {{ color: {LIGHT_PLACEHOLDER}; }}
    """


def get_combo_style(theme: str) -> str:
    if theme == THEME_DARK:
        return f"""
            QComboBox {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                padding: 6px 8px;
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox QAbstractItemView {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                selection-background-color: {DARK_PRIMARY};
                selection-color: white;
            }}
        """
    return f"""
        QComboBox {{
            background-color: white;
            color: {LIGHT_TEXT};
            border: 1px solid {LIGHT_BORDER};
            border-radius: 4px;
            padding: 6px 8px;
        }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{
            background-color: white;
            color: {LIGHT_TEXT};
            selection-background-color: {LIGHT_PRIMARY};
            selection-color: white;
        }}
    """


def get_content_stack_style(theme: str) -> str:
    bg = DARK_BG_WINDOW if theme == THEME_DARK else LIGHT_BG_WINDOW
    return f"QStackedWidget#content_stack {{ background-color: {bg}; }}"


def get_sidebar_style(theme: str) -> str:
    bg = DARK_SIDEBAR if theme == THEME_DARK else LIGHT_SIDEBAR
    return f"QWidget#sidebar {{ background-color: {bg}; }}"


def get_card_row_style(theme: str) -> str:
    if theme == THEME_DARK:
        return f"""
            background-color: {DARK_BG_CARD};
            border: 1px solid {DARK_BORDER};
            border-radius: 4px;
            padding: 8px 12px;
            color: {DARK_TEXT};
        """
    return f"""
        background-color: white;
        border: 1px solid {LIGHT_BORDER};
        border-radius: 4px;
        padding: 8px 12px;
        color: {LIGHT_TEXT};
    """


def get_dialog_style(theme: str) -> str:
    if theme == THEME_DARK:
        return f"""
            QDialog {{ background-color: {DARK_BG_WINDOW}; }}
            QLabel {{ color: {DARK_TEXT}; background: transparent; }}
            QLineEdit {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                padding: 6px 8px;
            }}
            QLineEdit::placeholder {{ color: {DARK_PLACEHOLDER}; }}
            QPlainTextEdit {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                padding: 4px;
            }}
            QPlainTextEdit::placeholder {{ color: {DARK_PLACEHOLDER}; }}
            QComboBox {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                padding: 6px 8px;
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox QAbstractItemView {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                selection-background-color: {DARK_PRIMARY};
                selection-color: white;
            }}
            QDateEdit {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                padding: 6px 8px;
            }}
            QCheckBox {{ color: {DARK_TEXT}; }}
            QDialogButtonBox QPushButton {{
                background-color: {DARK_BG_CARD};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                padding: 6px 16px;
            }}
            QDialogButtonBox QPushButton:hover {{ background-color: #3d474b; }}
        """
    return f"""
        QDialog {{ background-color: white; }}
        QLabel {{ color: {LIGHT_TEXT}; background: transparent; }}
        QLineEdit {{
            background-color: white;
            color: {LIGHT_TEXT};
            border: 1px solid {LIGHT_BORDER};
            border-radius: 4px;
            padding: 6px 8px;
        }}
        QLineEdit::placeholder {{ color: {LIGHT_PLACEHOLDER}; }}
        QPlainTextEdit {{
            background-color: white;
            color: {LIGHT_TEXT};
            border: 1px solid {LIGHT_BORDER};
            border-radius: 4px;
            padding: 4px;
        }}
        QPlainTextEdit::placeholder {{ color: {LIGHT_PLACEHOLDER}; }}
        QComboBox {{
            background-color: white;
            color: {LIGHT_TEXT};
            border: 1px solid {LIGHT_BORDER};
            border-radius: 4px;
            padding: 6px 8px;
        }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{
            background-color: white;
            color: {LIGHT_TEXT};
            selection-background-color: {LIGHT_PRIMARY};
            selection-color: white;
        }}
        QDateEdit {{
            background-color: white;
            color: {LIGHT_TEXT};
            border: 1px solid {LIGHT_BORDER};
            border-radius: 4px;
            padding: 6px 8px;
        }}
        QCheckBox {{ color: {LIGHT_TEXT}; }}
        QDialogButtonBox QPushButton {{
            background-color: #ecf0f1;
            color: {LIGHT_TEXT};
            border: 1px solid {LIGHT_BORDER};
            border-radius: 4px;
            padding: 6px 16px;
        }}
        QDialogButtonBox QPushButton:hover {{ background-color: #d5dbdb; }}
    """
