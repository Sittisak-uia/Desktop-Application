"""Unit tests for task_manager.ui.task_dialog.

Uses the standard library unittest only -- no pytest dependency.
Categories are loaded from a temporary SQLite database so the production
tasks.db is never touched.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QPlainTextEdit

from task_manager.database import add_category, initialize_database, seed_default_user
from task_manager.ui.task_dialog import TaskDialog

_app = QApplication.instance() or QApplication(sys.argv)


def _make_temp_db() -> tuple[str, sqlite3.Connection]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    seed_default_user(conn)
    add_category("Work", conn=conn)
    add_category("Personal", conn=conn)
    return path, conn


class TestTaskDialogAddMode(unittest.TestCase):
    """Test dialog in Add mode."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self._patcher = patch(
            "task_manager.ui.task_dialog.get_all_categories",
            side_effect=lambda: _cats(self.conn),
        )
        self._patcher.start()
        self.dlg = TaskDialog()
        self.dlg.show()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.dlg.close()
        self.dlg.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_can_be_instantiated(self) -> None:
        self.assertIsInstance(self.dlg, TaskDialog)
        self.assertIn("Add", self.dlg.windowTitle())

    def test_title_field_exists(self) -> None:
        self.assertIsNotNone(self.dlg.title_input)
        self.assertIsInstance(self.dlg.title_input, QLineEdit)

    def test_description_field_exists(self) -> None:
        self.assertIsNotNone(self.dlg.description_input)
        self.assertIsInstance(self.dlg.description_input, QPlainTextEdit)

    def test_priority_field_exists(self) -> None:
        self.assertIsNotNone(self.dlg.priority_combo)
        self.assertIsInstance(self.dlg.priority_combo, QComboBox)

    def test_category_field_exists(self) -> None:
        self.assertIsNotNone(self.dlg.category_combo)
        self.assertIsInstance(self.dlg.category_combo, QComboBox)

    def test_due_date_field_exists(self) -> None:
        self.assertIsNotNone(self.dlg.due_date_edit)

    def test_status_field_exists(self) -> None:
        self.assertIsNotNone(self.dlg.status_combo)
        self.assertIsInstance(self.dlg.status_combo, QComboBox)

    def test_save_button_exists(self) -> None:
        from PyQt6.QtWidgets import QDialogButtonBox
        self.assertIsNotNone(self.dlg.button_box)

    def test_cancel_button_exists(self) -> None:
        from PyQt6.QtWidgets import QDialogButtonBox
        self.assertIsNotNone(self.dlg.button_box)

    def test_default_priority_medium(self) -> None:
        self.assertEqual(self.dlg.priority_combo.currentText(), "Medium")

    def test_default_status_pending(self) -> None:
        self.assertEqual(self.dlg.status_combo.currentText(), "Pending")

    def test_categories_loaded(self) -> None:
        count = self.dlg.category_combo.count()
        # None + Work + Personal = 3
        self.assertEqual(count, 3)

    def test_none_category_first(self) -> None:
        self.assertEqual(self.dlg.category_combo.currentText(), "None (Uncategorized)")
        self.assertIsNone(self.dlg.category_combo.currentData())

    def test_dialog_styles_are_readable(self) -> None:
        style = self.dlg.styleSheet()
        self.assertIn("color: #2c3e50", style)
        self.assertIn("#95a5a6", style)  # placeholder text
        for token in (
            "QLineEdit",
            "QPlainTextEdit",
            "QComboBox",
            "QCheckBox",
            "QDateEdit",
            "QDialogButtonBox QPushButton",
        ):
            self.assertIn(token, style)


class TestTaskDialogEditMode(unittest.TestCase):
    """Test dialog in Edit mode."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self._patcher = patch(
            "task_manager.ui.task_dialog.get_all_categories",
            side_effect=lambda: _cats(self.conn),
        )
        self._patcher.start()

        work_id = _cat_id(self.conn, "Work")
        self.existing_task = {
            "title": "Buy milk",
            "description": "2% preferred",
            "priority": "Low",
            "category_id": work_id,
            "due_date": "2026-12-25",
            "status": "Completed",
        }
        self.dlg = TaskDialog(task=self.existing_task)
        self.dlg.show()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.dlg.close()
        self.dlg.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_edit_mode_title(self) -> None:
        self.assertIn("Edit", self.dlg.windowTitle())

    def test_populates_title(self) -> None:
        self.assertEqual(self.dlg.title_input.text(), "Buy milk")

    def test_populates_description(self) -> None:
        self.assertEqual(self.dlg.description_input.toPlainText(), "2% preferred")

    def test_populates_priority(self) -> None:
        self.assertEqual(self.dlg.priority_combo.currentText(), "Low")

    def test_populates_status(self) -> None:
        self.assertEqual(self.dlg.status_combo.currentText(), "Completed")

    def test_populates_category(self) -> None:
        cat_id = self.dlg.category_combo.currentData()
        self.assertEqual(cat_id, self.existing_task["category_id"])

    def test_populates_due_date(self) -> None:
        self.assertTrue(self.dlg.due_date_enabled.isChecked())
        qd = self.dlg.due_date_edit.date()
        self.assertEqual(qd.toString("yyyy-MM-dd"), "2026-12-25")


class TestTaskDialogNullFields(unittest.TestCase):
    """Test dialog with NULL category and due date."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self._patcher = patch(
            "task_manager.ui.task_dialog.get_all_categories",
            side_effect=lambda: _cats(self.conn),
        )
        self._patcher.start()

        self.task_nulls = {
            "title": "No cat or date",
            "description": "",
            "priority": "High",
            "category_id": None,
            "due_date": None,
            "status": "Pending",
        }
        self.dlg = TaskDialog(task=self.task_nulls)
        self.dlg.show()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.dlg.close()
        self.dlg.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_null_category_selects_none(self) -> None:
        self.assertEqual(self.dlg.category_combo.currentText(), "None (Uncategorized)")
        self.assertIsNone(self.dlg.category_combo.currentData())

    def test_null_due_date_unchecked(self) -> None:
        self.assertFalse(self.dlg.due_date_enabled.isChecked())


class TestTaskDialogValidation(unittest.TestCase):
    """Test validation rules."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self._patcher = patch(
            "task_manager.ui.task_dialog.get_all_categories",
            side_effect=lambda: _cats(self.conn),
        )
        self._patcher.start()
        self.dlg = TaskDialog()
        self.dlg.show()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.dlg.close()
        self.dlg.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_empty_title_fails(self) -> None:
        self.dlg.title_input.setText("")
        self.assertFalse(self.dlg._validate())
        self.assertTrue(self.dlg.error_label.isVisible())

    def test_whitespace_title_fails(self) -> None:
        self.dlg.title_input.setText("   ")
        self.assertFalse(self.dlg._validate())
        self.assertTrue(self.dlg.error_label.isVisible())

    def test_title_too_long_fails(self) -> None:
        # QLineEdit.setMaxLength enforces 200 at input level;
        # setText also truncates, so verify the max-length constraint
        self.dlg.title_input.setMaxLength(0)  # temporarily remove limit
        self.dlg.title_input.setText("x" * 201)
        self.assertFalse(self.dlg._validate())
        self.assertTrue(self.dlg.error_label.isVisible())

    def test_description_too_long_fails(self) -> None:
        self.dlg.title_input.setText("OK")
        self.dlg.description_input.setPlainText("x" * 2001)
        self.assertFalse(self.dlg._validate())
        self.assertTrue(self.dlg.error_label.isVisible())

    def test_valid_data_passes(self) -> None:
        self.dlg.title_input.setText("Valid task")
        self.assertTrue(self.dlg._validate())


class TestTaskDialogGetData(unittest.TestCase):
    """Test get_task_data() returns correct dictionary."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self._patcher = patch(
            "task_manager.ui.task_dialog.get_all_categories",
            side_effect=lambda: _cats(self.conn),
        )
        self._patcher.start()
        self.dlg = TaskDialog()
        self.dlg.show()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.dlg.close()
        self.dlg.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_returns_dict(self) -> None:
        data = self.dlg.get_task_data()
        self.assertIsInstance(data, dict)

    def test_has_all_keys(self) -> None:
        data = self.dlg.get_task_data()
        expected_keys = {"title", "description", "priority", "category_id",
                         "due_date", "status"}
        self.assertEqual(set(data.keys()), expected_keys)

    def test_default_values(self) -> None:
        data = self.dlg.get_task_data()
        self.assertEqual(data["title"], "")
        self.assertEqual(data["description"], "")
        self.assertEqual(data["priority"], "Medium")
        self.assertIsNone(data["category_id"])
        self.assertIsNone(data["due_date"])
        self.assertEqual(data["status"], "Pending")

    def test_title_trimmed(self) -> None:
        self.dlg.title_input.setText("  Hello  ")
        data = self.dlg.get_task_data()
        self.assertEqual(data["title"], "Hello")

    def test_category_none_when_not_checked(self) -> None:
        self.dlg.due_date_enabled.setChecked(False)
        data = self.dlg.get_task_data()
        self.assertIsNone(data["due_date"])

    def test_category_selected(self) -> None:
        work_id = _cat_id(self.conn, "Work")
        for i in range(self.dlg.category_combo.count()):
            if self.dlg.category_combo.itemData(i) == work_id:
                self.dlg.category_combo.setCurrentIndex(i)
                break
        data = self.dlg.get_task_data()
        self.assertEqual(data["category_id"], work_id)

    def test_due_date_when_checked(self) -> None:
        self.dlg.due_date_enabled.setChecked(True)
        self.dlg.due_date_edit.setDate(QDate(2026, 6, 15))
        data = self.dlg.get_task_data()
        self.assertEqual(data["due_date"], "2026-06-15")

    def test_due_date_none_when_unchecked(self) -> None:
        self.dlg.due_date_enabled.setChecked(False)
        data = self.dlg.get_task_data()
        self.assertIsNone(data["due_date"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _cats(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def _cat_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
    return row["id"]


if __name__ == "__main__":
    unittest.main()
