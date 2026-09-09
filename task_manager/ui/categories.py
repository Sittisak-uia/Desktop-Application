"""Categories management page for SQLite Task Manager PRO.

Read/summary widget that lists categories and supports Add / Edit /
Delete operations through the existing database layer.
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from task_manager.database import (
    add_category,
    delete_category,
    get_all_categories,
    update_category,
)

_MAX_NAME = 50

_CATEGORY_TEXT = "#2c3e50"

_TABLE_STYLE = f"""
    QTableWidget {{
        background-color: white;
        alternate-background-color: #f8f9fa;
        color: {_CATEGORY_TEXT};
    }}
    QHeaderView::section {{
        background-color: white;
        color: {_CATEGORY_TEXT};
        border: none;
        border-bottom: 1px solid #bdc3c7;
        padding: 6px 8px;
        font-weight: bold;
    }}
    QTableWidget::item {{
        color: {_CATEGORY_TEXT};
    }}
    QTableWidget::item:selected {{
        background-color: #3498db;
        color: white;
    }}
"""

_INPUT_DIALOG_STYLE = f"""
    QDialog {{
        background-color: white;
    }}
    QLabel {{
        color: {_CATEGORY_TEXT};
    }}
    QLineEdit {{
        background-color: white;
        color: {_CATEGORY_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 10px;
    }}
    QPushButton {{
        background-color: #ecf0f1;
        color: {_CATEGORY_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 16px;
    }}
    QPushButton:hover {{
        background-color: #d5dbdb;
    }}
"""

_MESSAGE_STYLE = f"""
    QMessageBox {{
        background-color: white;
    }}
    QLabel {{
        color: {_CATEGORY_TEXT};
    }}
    QPushButton {{
        background-color: #ecf0f1;
        color: {_CATEGORY_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 16px;
    }}
    QPushButton:hover {{
        background-color: #d5dbdb;
    }}
"""


class CategoriesWidget(QWidget):
    """Widget for viewing and managing categories."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._categories: list[dict] = []
        self._build_ui()
        self._connect_signals()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.title_label = QLabel("Categories")
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #2c3e50;")
        layout.addWidget(self.title_label)

        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Category Name"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self.table)

        btn_style = (
            "QPushButton { padding: 8px 16px; border-radius: 4px;"
            " font-weight: bold; }"
        )

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.add_btn = QPushButton("Add Category")
        self.add_btn.setStyleSheet(btn_style + "QPushButton { background-color: #27ae60; color: white; }")
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setStyleSheet(btn_style + "QPushButton { background-color: #3498db; color: white; }")
        button_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(btn_style + "QPushButton { background-color: #e74c3c; color: white; }")
        button_layout.addWidget(self.delete_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(btn_style + "QPushButton { background-color: #7f8c8d; color: white; }")
        button_layout.addWidget(self.refresh_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn.clicked.connect(self._on_delete)
        self.refresh_btn.clicked.connect(self.refresh)

    def refresh(self) -> None:
        try:
            self._categories = get_all_categories()
        except Exception:
            self._categories = []

        self.table.setRowCount(len(self._categories))
        for row, cat in enumerate(self._categories):
            item = QTableWidgetItem(cat["name"])
            item.setData(Qt.ItemDataRole.UserRole, cat["id"])
            self.table.setItem(row, 0, item)

        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def _selected_category(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._categories):
            return None
        return self._categories[row]

    def _validate_name(self, name: str) -> str | None:
        """Return a cleaned name, or None if invalid."""
        name = name.strip()
        if not name:
            _show_warning(self, "Invalid Name", "Category name cannot be empty.")
            return None
        if len(name) > _MAX_NAME:
            _show_warning(
                self, "Invalid Name",
                f"Category name must be {_MAX_NAME} characters or fewer.",
            )
            return None
        return name

    def _on_add(self) -> None:
        text, ok = self._prompt_for_name("Add Category", "Category name:")
        if not ok:
            return
        name = self._validate_name(text)
        if name is None:
            return
        try:
            add_category(name)
            self.refresh()
        except sqlite3.IntegrityError:
            _show_warning(self, "Duplicate", f"Category '{name}' already exists.")
        except Exception as exc:
            _show_critical(self, "Error", f"Failed to add category:\n{exc}")

    def _on_edit(self) -> None:
        cat = self._selected_category()
        if cat is None:
            _show_warning(self, "No Selection", "Please select a category to edit.")
            return
        text, ok = self._prompt_for_name(
            "Edit Category", "Category name:", initial=cat["name"]
        )
        if not ok:
            return
        name = self._validate_name(text)
        if name is None:
            return
        try:
            update_category(cat["id"], name)
            self.refresh()
        except sqlite3.IntegrityError:
            _show_warning(self, "Duplicate", f"Category '{name}' already exists.")
        except Exception as exc:
            _show_critical(self, "Error", f"Failed to edit category:\n{exc}")

    def _on_delete(self) -> None:
        cat = self._selected_category()
        if cat is None:
            _show_warning(self, "No Selection", "Please select a category to delete.")
            return
        if not _confirm(
            self,
            "Confirm Delete",
            f"Delete category '{cat['name']}'?\n"
            "Tasks in this category will become Uncategorized.",
        ):
            return
        try:
            delete_category(cat["id"])
            self.refresh()
        except Exception as exc:
            _show_critical(self, "Error", f"Failed to delete category:\n{exc}")

    def _prompt_for_name(self, title: str, label: str, initial: str = "") -> tuple[str, bool]:
        """Show a styled name-input dialog; return ``(text, accepted)``."""
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(initial)
        dialog.setOkButtonText("OK")
        dialog.setCancelButtonText("Cancel")
        dialog.setStyleSheet(_INPUT_DIALOG_STYLE)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.textValue(), accepted

    def apply_theme(self, theme: str) -> None:
        """Update CategoriesWidget styling to match the specified theme."""
        from task_manager.ui.theme import get_table_style, get_title_color
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {get_title_color(theme)};")
        if hasattr(self, "table"):
            self.table.setStyleSheet(get_table_style(theme))


def _make_message_box(
    parent: QWidget,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton | None = None,
    default: QMessageBox.StandardButton | None = None,
) -> QMessageBox:
    """Build a message box with readable dark text on a light background."""
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    if buttons is not None:
        box.setStandardButtons(buttons)
    if default is not None:
        box.setDefaultButton(default)
    box.setStyleSheet(_MESSAGE_STYLE)
    return box


def _show_warning(parent: QWidget, title: str, text: str) -> None:
    _make_message_box(parent, QMessageBox.Icon.Warning, title, text).exec()


def _show_critical(parent: QWidget, title: str, text: str) -> None:
    _make_message_box(parent, QMessageBox.Icon.Critical, title, text).exec()


def _confirm(parent: QWidget, title: str, text: str) -> bool:
    box = _make_message_box(
        parent,
        QMessageBox.Icon.Question,
        title,
        text,
        buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default=QMessageBox.StandardButton.No,
    )
    return box.exec() == QMessageBox.StandardButton.Yes