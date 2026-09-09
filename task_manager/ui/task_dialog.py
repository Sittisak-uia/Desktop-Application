"""Add / Edit Task dialog for SQLite Task Manager PRO.

Collects and validates task fields.  Does **not** write to the database
directly — the caller is responsible for persisting the returned data.
"""

from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QWidget,
)

from task_manager.database import get_all_categories

_MAX_TITLE = 200
_MAX_DESCRIPTION = 2000
_VALID_PRIORITIES = ["Low", "Medium", "High"]
_VALID_STATUSES = ["Pending", "Completed"]
_NONE_CATEGORY_LABEL = "None (Uncategorized)"

_TEXT = "#2c3e50"
_PLACEHOLDER = "#95a5a6"

_DIALOG_STYLE = f"""
    QDialog {{ background-color: white; }}
    QLabel {{ color: {_TEXT}; background: transparent; }}
    QLineEdit {{
        background-color: white;
        color: {_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 8px;
    }}
    QLineEdit::placeholder {{ color: {_PLACEHOLDER}; }}
    QPlainTextEdit {{
        background-color: white;
        color: {_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 4px;
    }}
    QPlainTextEdit::placeholder {{ color: {_PLACEHOLDER}; }}
    QComboBox {{
        background-color: white;
        color: {_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 8px;
    }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background-color: white;
        color: {_TEXT};
        selection-background-color: #3498db;
        selection-color: white;
    }}
    QCheckBox {{ color: {_TEXT}; background: transparent; }}
    QDateEdit {{
        background-color: white;
        color: {_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 8px;
    }}
    QCalendarWidget QToolButton {{ color: {_TEXT}; background: transparent; }}
    QCalendarWidget QSpinBox {{ color: {_TEXT}; }}
    QCalendarWidget QAbstractItemView {{
        background-color: white;
        color: {_TEXT};
        selection-background-color: #3498db;
        selection-color: white;
    }}
    QDialogButtonBox QPushButton {{
        background-color: #ecf0f1;
        color: {_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 16px;
    }}
    QDialogButtonBox QPushButton:hover {{ background-color: #d5dbdb; }}
"""


class TaskDialog(QDialog):
    """Modal dialog for adding or editing a task."""

    def __init__(
        self,
        parent: QWidget | None = None,
        task: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self._task = task
        self._is_edit = task is not None

        self.setWindowTitle("Edit Task" if self._is_edit else "Add New Task")
        self.setMinimumWidth(480)
        self.setModal(True)
        from task_manager.ui.theme import get_current_theme, get_dialog_style
        self.setStyleSheet(get_dialog_style(get_current_theme()))

        self._build_ui()
        self._load_categories()
        self._populate_existing()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        form = QFormLayout(self)
        form.setSpacing(10)
        form.setContentsMargins(20, 20, 20, 20)

        # ---- Title ----
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter task title")
        self.title_input.setMaxLength(_MAX_TITLE)
        form.addRow("Title *:", self.title_input)

        # ---- Description ----
        self.description_input = QPlainTextEdit()
        self.description_input.setPlaceholderText("Optional description")
        self.description_input.setMaximumHeight(100)
        self._descMaxLength = _MAX_DESCRIPTION
        form.addRow("Description:", self.description_input)

        # ---- Priority ----
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(_VALID_PRIORITIES)
        self.priority_combo.setCurrentText("Medium")
        form.addRow("Priority:", self.priority_combo)

        # ---- Category ----
        self.category_combo = QComboBox()
        form.addRow("Category:", self.category_combo)

        # ---- Due date ----
        date_row = QWidget()
        from PyQt6.QtWidgets import QHBoxLayout
        date_layout = QHBoxLayout(date_row)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(8)

        self.due_date_enabled = QCheckBox("Set due date")
        self.due_date_enabled.toggled.connect(self._on_due_date_toggled)
        date_layout.addWidget(self.due_date_enabled)

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate())
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_date_edit.setEnabled(False)
        date_layout.addWidget(self.due_date_edit, stretch=1)

        form.addRow("Due Date:", date_row)

        # ---- Status ----
        self.status_combo = QComboBox()
        self.status_combo.addItems(_VALID_STATUSES)
        self.status_combo.setCurrentText("Pending")
        form.addRow("Status:", self.status_combo)

        # ---- Error label ----
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e74c3c; font-size: 11px; padding: 2px;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        form.addRow("", self.error_label)

        # ---- Buttons ----
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        form.addRow(self.button_box)

    # ------------------------------------------------------------------
    # Category loading
    # ------------------------------------------------------------------

    def _load_categories(self) -> None:
        self.category_combo.clear()
        self.category_combo.addItem(_NONE_CATEGORY_LABEL, None)
        for cat in get_all_categories():
            self.category_combo.addItem(cat["name"], cat["id"])

    # ------------------------------------------------------------------
    # Populate existing task data (edit mode)
    # ------------------------------------------------------------------

    def _populate_existing(self) -> None:
        if not self._task:
            return

        self.title_input.setText(self._task.get("title", ""))
        self.description_input.setPlainText(self._task.get("description", ""))

        priority = self._task.get("priority", "Medium")
        idx = self.priority_combo.findText(priority, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)

        status = self._task.get("status", "Pending")
        idx = self.status_combo.findText(status, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        # Category
        cat_id = self._task.get("category_id")
        if cat_id is not None:
            for i in range(self.category_combo.count()):
                if self.category_combo.itemData(i) == cat_id:
                    self.category_combo.setCurrentIndex(i)
                    break

        # Due date
        due = self._task.get("due_date")
        if due:
            self.due_date_enabled.setChecked(True)
            qd = QDate.fromString(due, "yyyy-MM-dd")
            if qd.isValid():
                self.due_date_edit.setDate(qd)

    # ------------------------------------------------------------------
    # Due date toggle
    # ------------------------------------------------------------------

    def _on_due_date_toggled(self, checked: bool) -> None:
        self.due_date_edit.setEnabled(checked)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> bool:
        title = self.title_input.text().strip()
        if not title:
            self._show_error("Title is required.")
            return False
        if len(title) > _MAX_TITLE:
            self._show_error(f"Title must be {_MAX_TITLE} characters or fewer.")
            return False

        desc = self.description_input.toPlainText()
        if len(desc) > _MAX_DESCRIPTION:
            self._show_error(f"Description must be {_MAX_DESCRIPTION} characters or fewer.")
            return False

        return True

    # ------------------------------------------------------------------
    # Save handler
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        if not self._validate():
            return

        # Warn on past due date for new tasks (non-blocking)
        if not self._is_edit and self.due_date_enabled.isChecked():
            chosen = self.due_date_edit.date().toPyDate()
            if chosen < date.today():
                reply = QMessageBox.warning(
                    self,
                    "Past Due Date",
                    "The selected due date is in the past.\nDo you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return

        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_task_data(self) -> dict:
        """Return the collected field values as a plain dictionary."""
        title = self.title_input.text().strip()
        description = self.description_input.toPlainText()
        priority = self.priority_combo.currentText()
        category_id = self.category_combo.currentData()
        status = self.status_combo.currentText()

        if self.due_date_enabled.isChecked():
            due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        else:
            due_date = None

        return {
            "title": title,
            "description": description,
            "priority": priority,
            "category_id": category_id,
            "due_date": due_date,
            "status": status,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)
