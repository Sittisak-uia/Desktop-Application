"""Trash / Recycle Bin page for SQLite Task Manager PRO.

Displays soft-deleted tasks (is_deleted = 1) in a table and supports
restoring tasks back to the active list or permanently deleting them from SQLite.
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from task_manager.database import (
    get_all_categories,
    get_trash_tasks,
    permanent_delete_task,
    restore_task,
)

_TEXT = "#2c3e50"

_TABLE_STYLE = f"""
    QTableWidget {{
        background-color: white;
        alternate-background-color: #f8f9fa;
        color: {_TEXT};
    }}
    QHeaderView::section {{
        background-color: white;
        color: {_TEXT};
        border: none;
        border-bottom: 1px solid #bdc3c7;
        padding: 6px 8px;
        font-weight: bold;
    }}
    QTableWidget::item {{
        color: {_TEXT};
    }}
    QTableWidget::item:selected {{
        background-color: #3498db;
        color: white;
    }}
"""

_BTN_STYLE = """
    QPushButton {
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 13px;
    }
"""

_MESSAGE_STYLE = f"""
    QMessageBox {{
        background-color: white;
    }}
    QLabel {{
        color: {_TEXT};
    }}
    QPushButton {{
        background-color: #ecf0f1;
        color: {_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 16px;
    }}
    QPushButton:hover {{
        background-color: #d5dbdb;
    }}
"""


class TrashWidget(QWidget):
    """Widget for viewing and managing trashed tasks."""

    tasks_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tasks: list[dict] = []
        self._categories: list[dict] = []
        self._category_map: dict[int, str] = {}
        self._build_ui()
        self._connect_signals()
        self.refresh()

    def text(self) -> str:
        """Return page label for compatibility."""
        return "Trash"

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        self.title_label = QLabel("Trash")
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {_TEXT};")
        layout.addWidget(self.title_label)

        # Info subtitle
        self.subtitle = QLabel("Items in the trash can be restored or permanently removed.")
        self.subtitle.setFont(QFont("Segoe UI", 10))
        self.subtitle.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(self.subtitle)

        # Table for deleted tasks
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Title", "Priority", "Category", "Due Date",
            "Status", "Created At", "Completed At"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for col in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self.table)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.restore_btn = QPushButton("Restore Task")
        self.restore_btn.setStyleSheet(
            _BTN_STYLE + "QPushButton { background-color: #27ae60; color: white; }"
        )
        button_layout.addWidget(self.restore_btn)

        self.delete_btn = QPushButton("Permanently Delete")
        self.delete_btn.setStyleSheet(
            _BTN_STYLE + "QPushButton { background-color: #e74c3c; color: white; }"
        )
        button_layout.addWidget(self.delete_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(
            _BTN_STYLE + "QPushButton { background-color: #3498db; color: white; }"
        )
        button_layout.addWidget(self.refresh_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        self.restore_btn.clicked.connect(self._on_restore_task)
        self.delete_btn.clicked.connect(self._on_permanent_delete_task)
        self.refresh_btn.clicked.connect(self.refresh)

    def _load_categories(self) -> None:
        try:
            self._categories = get_all_categories()
        except Exception:
            self._categories = []
        self._category_map = {cat["id"]: cat["name"] for cat in self._categories}

    def refresh(self) -> None:
        """Reload categories and trashed tasks from the database."""
        self._load_categories()
        try:
            self._tasks = get_trash_tasks()
        except Exception as exc:
            self._tasks = []
            _show_critical(self, "Database Error", f"Failed to load trash tasks:\n{exc}")
        self._populate_table()
        self.tasks_changed.emit()

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self._tasks))
        for row, task in enumerate(self._tasks):
            self.table.setItem(row, 0, QTableWidgetItem(task.get("title", "")))
            priority = task.get("priority", "")
            self.table.setItem(row, 1, QTableWidgetItem(priority.title() if priority else ""))
            cat_id = task.get("category_id")
            cat_name = self._category_map.get(cat_id, "Uncategorized") if cat_id else "Uncategorized"
            self.table.setItem(row, 2, QTableWidgetItem(cat_name))
            self.table.setItem(row, 3, QTableWidgetItem(task.get("due_date") or ""))
            status = task.get("status", "")
            self.table.setItem(row, 4, QTableWidgetItem(status.title() if status else ""))
            self.table.setItem(row, 5, QTableWidgetItem(task.get("created_at") or ""))
            self.table.setItem(row, 6, QTableWidgetItem(task.get("completed_at") or ""))

        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def _on_restore_task(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._tasks):
            _show_warning(self, "No Selection", "Please select a task to restore.")
            return

        task = self._tasks[row]
        try:
            restore_task(task["id"])
            self.refresh()
        except Exception as exc:
            _show_critical(self, "Error", f"Failed to restore task:\n{exc}")

    def _on_permanent_delete_task(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._tasks):
            _show_warning(self, "No Selection", "Please select a task to permanently delete.")
            return

        task = self._tasks[row]
        confirmed = _confirm(
            self,
            "Confirm Delete",
            f"Permanently delete task '{task['title']}'?\n"
            "This action cannot be undone.",
        )
        if not confirmed:
            return

        try:
            permanent_delete_task(task["id"])
            self.refresh()
        except Exception as exc:
            _show_critical(self, "Error", f"Failed to permanently delete task:\n{exc}")

    def apply_theme(self, theme: str) -> None:
        """Update TrashWidget styling to match the specified theme."""
        from task_manager.ui.theme import (
            get_subtitle_color,
            get_table_style,
            get_title_color,
        )
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {get_title_color(theme)};")
        if hasattr(self, "subtitle"):
            self.subtitle.setStyleSheet(f"color: {get_subtitle_color(theme)};")
        if hasattr(self, "table"):
            self.table.setStyleSheet(get_table_style(theme))


# ---------------------------------------------------------------------------
# Message dialog helpers with readable dark text on light background
# ---------------------------------------------------------------------------

def _make_message_box(
    parent: QWidget,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton | None = None,
    default: QMessageBox.StandardButton | None = None,
) -> QMessageBox:
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
