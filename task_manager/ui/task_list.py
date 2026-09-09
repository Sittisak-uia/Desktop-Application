"""Task List page for SQLite Task Manager PRO.

Displays active (non-deleted) tasks in a table with search/filter
capabilities and buttons for Add, Edit, Delete, and Complete/Pending
operations.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QFileDialog,
)

from task_manager.database import (
    add_task,
    duplicate_task,
    get_active_tasks,
    get_all_categories,
    get_task_by_id,
    search_tasks,
    soft_delete_task,
    update_task,
)
from task_manager.ui.task_dialog import TaskDialog

_TEXT = "#2c3e50"
_PLACEHOLDER = "#95a5a6"

_INPUT_STYLE = f"""
    QLineEdit {{
        background-color: white;
        color: {_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 8px;
    }}
    QLineEdit::placeholder {{ color: {_PLACEHOLDER}; }}
"""

_COMBO_STYLE = f"""
    QComboBox {{
        background-color: white;
        color: {_TEXT};
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 6px 8px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: white;
        color: {_TEXT};
        selection-background-color: #3498db;
        selection-color: white;
    }}
"""


class TaskListWidget(QWidget):
    """Widget for displaying and managing the task list."""

    tasks_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tasks: list[dict] = []
        self._categories: list[dict] = []
        self._category_map: dict[int, str] = {}
        self._build_ui()
        self._connect_signals()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.title_label = QLabel("Tasks")
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #2c3e50;")
        layout.addWidget(self.title_label)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tasks...")
        self.search_input.setStyleSheet(_INPUT_STYLE)
        search_layout.addWidget(self.search_input, stretch=1)

        self.priority_filter = QComboBox()
        self.priority_filter.addItems(["All", "Low", "Medium", "High"])
        self.priority_filter.setMinimumWidth(100)
        self.priority_filter.setStyleSheet(_COMBO_STYLE)
        search_layout.addWidget(self.priority_filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Pending", "Completed"])
        self.status_filter.setMinimumWidth(100)
        self.status_filter.setStyleSheet(_COMBO_STYLE)
        search_layout.addWidget(self.status_filter)

        self.category_filter = QComboBox()
        self.category_filter.setMinimumWidth(120)
        self.category_filter.setStyleSheet(_COMBO_STYLE)
        search_layout.addWidget(self.category_filter)

        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Title", "Priority", "Category", "Due Date",
            "Status", "Created At", "Completed At"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { background-color: white;"
            " alternate-background-color: #f8f9fa;"
            f" color: {_TEXT}; }}"
            "QHeaderView::section { background-color: white;"
            f" color: {_TEXT}; border: none;"
            " border-bottom: 1px solid #bdc3c7; padding: 6px 8px;"
            " font-weight: bold; }"
            f"QTableWidget::item {{ color: {_TEXT}; }}"
            "QTableWidget::item:selected { background-color: #3498db;"
            " color: white; }"
        )
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        btn_style = """
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """

        self.add_btn = QPushButton("Add Task")
        self.add_btn.setStyleSheet(btn_style + "QPushButton { background-color: #27ae60; color: white; }")
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setStyleSheet(btn_style + "QPushButton { background-color: #3498db; color: white; }")
        button_layout.addWidget(self.edit_btn)

        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.setStyleSheet(
            btn_style + "QPushButton { background-color: #2980b9; color: white; }"
            "QPushButton:hover { background-color: #1f618d; }"
        )
        button_layout.addWidget(self.duplicate_btn)

        self.complete_btn = QPushButton("Complete")
        self.complete_btn.setStyleSheet(btn_style + "QPushButton { background-color: #f39c12; color: white; }")
        button_layout.addWidget(self.complete_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(btn_style + "QPushButton { background-color: #e74c3c; color: white; }")
        button_layout.addWidget(self.delete_btn)

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setStyleSheet(btn_style + "QPushButton { background-color: #8e44ad; color: white; }")
        button_layout.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import CSV")
        self.import_btn.setStyleSheet(btn_style + "QPushButton { background-color: #16a085; color: white; }")
        button_layout.addWidget(self.import_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(self._on_search_changed)
        self.priority_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.status_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.category_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.add_btn.clicked.connect(self._on_add_task)
        self.edit_btn.clicked.connect(self._on_edit_task)
        self.duplicate_btn.clicked.connect(self._on_duplicate_task)
        self.complete_btn.clicked.connect(self._on_complete_task)
        self.delete_btn.clicked.connect(self._on_delete_task)
        self.export_btn.clicked.connect(self._on_export_csv)
        self.import_btn.clicked.connect(self._on_import_csv)

    def _load_categories(self) -> None:
        try:
            self._categories = get_all_categories()
        except Exception:
            self._categories = []
        self._category_map = {cat["id"]: cat["name"] for cat in self._categories}
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories", None)
        self.category_filter.addItem("Uncategorized", -1)
        for cat in self._categories:
            self.category_filter.addItem(cat["name"], cat["id"])
        self.category_filter.blockSignals(False)

    def refresh(self) -> None:
        saved_keyword = self.search_input.text().strip()
        saved_priority = self.priority_filter.currentText()
        saved_status = self.status_filter.currentText()
        saved_cat_data = self.category_filter.currentData()

        self._load_categories()

        self.priority_filter.blockSignals(True)
        self.status_filter.blockSignals(True)
        self.category_filter.blockSignals(True)

        if saved_priority:
            idx = self.priority_filter.findText(saved_priority)
            if idx >= 0:
                self.priority_filter.setCurrentIndex(idx)
        if saved_status:
            idx = self.status_filter.findText(saved_status)
            if idx >= 0:
                self.status_filter.setCurrentIndex(idx)
        if saved_cat_data is not None:
            for i in range(self.category_filter.count()):
                if self.category_filter.itemData(i) == saved_cat_data:
                    self.category_filter.setCurrentIndex(i)
                    break

        self.priority_filter.blockSignals(False)
        self.status_filter.blockSignals(False)
        self.category_filter.blockSignals(False)

        keyword = self.search_input.text().strip()
        priority = self.priority_filter.currentText()
        status = self.status_filter.currentText()
        cat_data = self.category_filter.currentData()

        if priority == "All":
            priority = None
        if status == "All":
            status = None
        if cat_data is None:
            category_id = None
        elif cat_data == -1:
            category_id = -1
        else:
            category_id = cat_data

        try:
            if category_id == -1:
                all_tasks = search_tasks(
                    keyword=keyword, priority=priority, status=status, conn=None
                )
                self._tasks = [t for t in all_tasks if t["category_id"] is None]
            else:
                self._tasks = search_tasks(
                    keyword=keyword, category_id=category_id,
                    priority=priority, status=status, conn=None
                )
        except Exception:
            self._tasks = []

        self._populate_table()

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self._tasks))
        for row, task in enumerate(self._tasks):
            self.table.setItem(row, 0, QTableWidgetItem(task["title"]))
            self.table.setItem(row, 1, QTableWidgetItem(task["priority"].title()))
            cat_name = self._category_map.get(task["category_id"], "Uncategorized") if task["category_id"] else "Uncategorized"
            self.table.setItem(row, 2, QTableWidgetItem(cat_name))
            self.table.setItem(row, 3, QTableWidgetItem(task["due_date"] or ""))
            self.table.setItem(row, 4, QTableWidgetItem(task["status"].title()))
            self.table.setItem(row, 5, QTableWidgetItem(task["created_at"]))
            self.table.setItem(row, 6, QTableWidgetItem(task["completed_at"] or ""))

        if self.table.rowCount() > 0:
            self.table.selectRow(0)

        self.tasks_changed.emit()

    def _on_search_changed(self) -> None:
        self.refresh()

    def _on_filter_changed(self) -> None:
        self.refresh()

    def _on_add_task(self) -> None:
        dialog = TaskDialog(parent=self)
        if dialog.exec():
            data = dialog.get_task_data()
            try:
                add_task(
                    title=data["title"],
                    description=data["description"],
                    priority=data["priority"],
                    category_id=data["category_id"],
                    due_date=data["due_date"],
                    status=data["status"],
                )
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add task: {str(e)}")

    def _on_edit_task(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a task to edit.")
            return

        task = self._tasks[row]
        dialog = TaskDialog(parent=self, task=task)
        if dialog.exec():
            data = dialog.get_task_data()
            try:
                update_task(
                    task_id=task["id"],
                    title=data["title"],
                    description=data["description"],
                    priority=data["priority"],
                    category_id=data["category_id"],
                    due_date=data["due_date"],
                    status=data["status"],
                )
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update task: {str(e)}")

    def _on_duplicate_task(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._tasks):
            QMessageBox.warning(self, "No Selection", "Please select a task to duplicate.")
            return

        task = self._tasks[row]
        try:
            duplicate_task(task["id"])
            self.refresh()
            QMessageBox.information(
                self,
                "Task Duplicated",
                f"Task \"{task['title']}\" has been duplicated successfully.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to duplicate task: {str(e)}")

    def _on_complete_task(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a task.")
            return

        task = self._tasks[row]
        try:
            if task["status"] == "Pending":
                new_status = "Completed"
            else:
                new_status = "Pending"
            update_task(
                task_id=task["id"],
                title=task["title"],
                description=task["description"],
                priority=task["priority"],
                category_id=task["category_id"],
                due_date=task["due_date"],
                status=new_status,
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update task status: {str(e)}")

    def _on_delete_task(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a task to delete.")
            return

        task = self._tasks[row]
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{task['title']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                soft_delete_task(task["id"])
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete task: {str(e)}")

    def _on_export_csv(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Tasks to CSV",
            "tasks_export.csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        try:
            from task_manager.csv_io import export_tasks_to_csv
            count = export_tasks_to_csv(file_path)
            QMessageBox.information(
                self,
                "Export Successful",
                f"Successfully exported {count} task(s) to:\n{file_path}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export tasks to CSV:\n{exc}",
            )

    def _on_import_csv(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Tasks from CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        try:
            from task_manager.csv_io import import_tasks_from_csv
            count, errors = import_tasks_from_csv(file_path)
            if errors:
                error_summary = "\n".join(errors[:10])
                if len(errors) > 10:
                    error_summary += f"\n...and {len(errors) - 10} more error(s)."
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    f"The CSV file contained validation errors and was not imported:\n\n{error_summary}",
                )
            else:
                QMessageBox.information(
                    self,
                    "Import Successful",
                    f"Successfully imported {count} task(s).",
                )
                self.refresh()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Import Error",
                f"An unexpected error occurred during import:\n{exc}",
            )

    def apply_theme(self, theme: str) -> None:
        """Update TaskListWidget styling to match the specified theme."""
        from task_manager.ui.theme import (
            get_combo_style,
            get_input_style,
            get_table_style,
            get_title_color,
        )
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {get_title_color(theme)};")
        if hasattr(self, "search_input"):
            self.search_input.setStyleSheet(get_input_style(theme))
        if hasattr(self, "priority_filter"):
            self.priority_filter.setStyleSheet(get_combo_style(theme))
        if hasattr(self, "status_filter"):
            self.status_filter.setStyleSheet(get_combo_style(theme))
        if hasattr(self, "category_filter"):
            self.category_filter.setStyleSheet(get_combo_style(theme))
        if hasattr(self, "table"):
            self.table.setStyleSheet(get_table_style(theme))
