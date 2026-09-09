"""Focused unit tests for Phase 11 — CSV Export / Import for Task Manager PRO.

Uses standard library unittest and csv. All tests use a temporary SQLite database
for complete isolation from production tasks.db.
"""

import csv
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from task_manager.csv_io import (
    CSV_COLUMNS,
    export_tasks_to_csv,
    import_tasks_from_csv,
)
from task_manager.database import (
    add_category,
    add_task,
    get_active_tasks,
    get_all_categories,
    initialize_database,
    seed_default_user,
    soft_delete_task,
)

# Ensure a QApplication exists for widget testing
_app = QApplication.instance() or QApplication(sys.argv)


def _make_temp_db() -> tuple[str, sqlite3.Connection]:
    """Create a temporary SQLite database with full schema initialized."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    seed_default_user(conn)
    return path, conn


class TestCSVExport(unittest.TestCase):
    """Verify CSV export functionality."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.cat_work = add_category("Work", conn=self.conn)
        self.t_active1 = add_task(
            "Active Task 1",
            description="Active description",
            priority="HIGH",
            category_id=self.cat_work,
            due_date="2026-10-15",
            conn=self.conn,
        )
        self.t_active2 = add_task(
            "Uncategorized Active",
            priority="LOW",
            conn=self.conn,
        )
        self.t_deleted = add_task(
            "Trashed Task",
            priority="MEDIUM",
            conn=self.conn,
        )
        soft_delete_task(self.t_deleted, conn=self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_export_creates_valid_csv(self) -> None:
        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            count = export_tasks_to_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 2)
            self.assertTrue(os.path.exists(csv_path))
            self.assertGreater(os.path.getsize(csv_path), 0)
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_export_contains_required_columns(self) -> None:
        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            export_tasks_to_csv(csv_path, conn=self.conn)
            with open(csv_path, "r", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = next(reader)
            self.assertEqual(header, CSV_COLUMNS)
            self.assertEqual(
                header,
                ["id", "title", "description", "priority", "category", "due_date", "status", "created_at", "completed_at"]
            )
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_deleted_tasks_are_excluded(self) -> None:
        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            export_tasks_to_csv(csv_path, conn=self.conn)
            with open(csv_path, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            titles = {r["title"] for r in rows}
            self.assertIn("Active Task 1", titles)
            self.assertIn("Uncategorized Active", titles)
            self.assertNotIn("Trashed Task", titles)
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_uncategorized_tasks_export_correctly(self) -> None:
        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            export_tasks_to_csv(csv_path, conn=self.conn)
            with open(csv_path, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = {r["title"]: r for r in reader}
            self.assertEqual(rows["Active Task 1"]["category"], "Work")
            self.assertEqual(rows["Uncategorized Active"]["category"], "Uncategorized")
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_export_empty_database(self) -> None:
        # Create fresh DB with no tasks
        db_p, conn_empty = _make_temp_db()
        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            count = export_tasks_to_csv(csv_path, conn=conn_empty)
            self.assertEqual(count, 0)
            with open(csv_path, "r", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = next(reader)
                rows = list(reader)
            self.assertEqual(header, CSV_COLUMNS)
            self.assertEqual(len(rows), 0)
        finally:
            conn_empty.close()
            if os.path.exists(db_p):
                os.unlink(db_p)
            if os.path.exists(csv_path):
                os.unlink(csv_path)


class TestCSVImport(unittest.TestCase):
    """Verify CSV import validation, transactional integrity, and duplicate handling."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.cat_work = add_category("Work", conn=self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _write_csv(self, header: list[str], rows: list[list[str]]) -> str:
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            for r in rows:
                writer.writerow(r)
        return path

    def test_valid_csv_imports_successfully(self) -> None:
        csv_path = self._write_csv(
            CSV_COLUMNS,
            [
                ["1", "Imported 1", "Desc 1", "LOW", "Work", "2026-11-01", "PENDING", "2026-01-01T00:00:00", ""],
                ["2", "Imported 2", "Desc 2", "HIGH", "Uncategorized", "", "COMPLETED", "2026-01-02T00:00:00", "2026-01-03T00:00:00"],
            ],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 2)
            self.assertEqual(errors, [])

            tasks = get_active_tasks(conn=self.conn)
            self.assertEqual(len(tasks), 2)
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_imported_task_data_is_preserved(self) -> None:
        csv_path = self._write_csv(
            CSV_COLUMNS,
            [
                ["10", "Detailed Task", "Important notes here", "HIGH", "Work", "2026-12-25", "COMPLETED", "2026-01-01T10:00:00", "2026-01-05T12:00:00"],
            ],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 1)

            tasks = get_active_tasks(conn=self.conn)
            self.assertEqual(len(tasks), 1)
            t = tasks[0]
            self.assertEqual(t["title"], "Detailed Task")
            self.assertEqual(t["description"], "Important notes here")
            self.assertEqual(t["priority"], "HIGH")
            self.assertEqual(t["category_id"], self.cat_work)
            self.assertEqual(t["due_date"], "2026-12-25")
            self.assertEqual(t["status"], "COMPLETED")
            self.assertEqual(t["created_at"], "2026-01-01T10:00:00")
            self.assertEqual(t["completed_at"], "2026-01-05T12:00:00")
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_invalid_missing_columns_are_rejected(self) -> None:
        # Missing priority and status
        csv_path = self._write_csv(
            ["title", "description"],
            [["Task Without Priority", "desc"]],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 0)
            self.assertTrue(len(errors) > 0)
            self.assertIn("Missing required CSV column", errors[0])

            # Database has no tasks inserted
            self.assertEqual(len(get_active_tasks(conn=self.conn)), 0)
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_invalid_priority_is_rejected(self) -> None:
        csv_path = self._write_csv(
            CSV_COLUMNS,
            [["1", "Task", "desc", "URGENT", "Work", "2026-10-01", "PENDING", "", ""]],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 0)
            self.assertTrue(any("invalid priority" in e for e in errors))
            self.assertEqual(len(get_active_tasks(conn=self.conn)), 0)
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_invalid_status_is_rejected(self) -> None:
        csv_path = self._write_csv(
            CSV_COLUMNS,
            [["1", "Task", "desc", "LOW", "Work", "2026-10-01", "IN_PROGRESS", "", ""]],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 0)
            self.assertTrue(any("invalid status" in e for e in errors))
            self.assertEqual(len(get_active_tasks(conn=self.conn)), 0)
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_invalid_date_is_rejected(self) -> None:
        csv_path = self._write_csv(
            CSV_COLUMNS,
            [["1", "Task", "desc", "LOW", "Work", "31-12-2026", "PENDING", "", ""]],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 0)
            self.assertTrue(any("invalid due_date format" in e for e in errors))
            self.assertEqual(len(get_active_tasks(conn=self.conn)), 0)
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_failed_import_does_not_partially_insert_tasks(self) -> None:
        """Verify atomic transaction: 1 valid row + 1 invalid row leaves 0 inserted tasks."""
        csv_path = self._write_csv(
            CSV_COLUMNS,
            [
                ["1", "Valid Task First", "desc", "LOW", "Work", "2026-10-01", "PENDING", "", ""],
                ["2", "Invalid Task Second", "desc", "INVALID_PRIORITY", "Work", "2026-10-01", "PENDING", "", ""],
            ],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 0)
            self.assertTrue(len(errors) > 0)

            # Neither task should be in database
            tasks = get_active_tasks(conn=self.conn)
            self.assertEqual(len(tasks), 0)
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_category_resolution_works(self) -> None:
        """Resolves existing categories, auto-registers new categories, and handles Uncategorized."""
        csv_path = self._write_csv(
            CSV_COLUMNS,
            [
                ["1", "Task Existing Cat", "", "LOW", "Work", "", "PENDING", "", ""],
                ["2", "Task New Cat", "", "MEDIUM", "Fitness", "", "PENDING", "", ""],
                ["3", "Task No Cat", "", "HIGH", "Uncategorized", "", "PENDING", "", ""],
            ],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 3)
            self.assertEqual(errors, [])

            # Check that "Fitness" category was registered
            categories = {c["name"]: c["id"] for c in get_all_categories(conn=self.conn)}
            self.assertIn("Work", categories)
            self.assertIn("Fitness", categories)

            tasks = {t["title"]: t for t in get_active_tasks(conn=self.conn)}
            self.assertEqual(tasks["Task Existing Cat"]["category_id"], categories["Work"])
            self.assertEqual(tasks["Task New Cat"]["category_id"], categories["Fitness"])
            self.assertIsNone(tasks["Task No Cat"]["category_id"])
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_duplicate_handling_works_as_documented(self) -> None:
        """Duplicate tasks receive fresh IDs without overwriting existing tasks."""
        existing_id = add_task("Existing Task", priority="LOW", conn=self.conn)

        # Import a CSV row with identical title and custom CSV ID 999
        csv_path = self._write_csv(
            CSV_COLUMNS,
            [["999", "Existing Task", "New copy description", "LOW", "Uncategorized", "", "PENDING", "", ""]],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 1)
            self.assertEqual(errors, [])

            tasks = get_active_tasks(conn=self.conn)
            self.assertEqual(len(tasks), 2)

            task_ids = {t["id"] for t in tasks}
            self.assertIn(existing_id, task_ids)
            # The newly inserted task must have an ID distinct from existing_id
            new_tasks = [t for t in tasks if t["id"] != existing_id]
            self.assertEqual(len(new_tasks), 1)
            self.assertEqual(new_tasks[0]["title"], "Existing Task")
            self.assertEqual(new_tasks[0]["description"], "New copy description")
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)

    def test_existing_tasks_remain_intact(self) -> None:
        t1 = add_task("Original Task 1", priority="HIGH", conn=self.conn)
        t2 = add_task("Original Task 2", priority="MEDIUM", conn=self.conn)

        csv_path = self._write_csv(
            CSV_COLUMNS,
            [["1", "Newly Imported", "", "LOW", "", "", "PENDING", "", ""]],
        )
        try:
            count, errors = import_tasks_from_csv(csv_path, conn=self.conn)
            self.assertEqual(count, 1)

            tasks = {t["id"]: t for t in get_active_tasks(conn=self.conn)}
            self.assertEqual(len(tasks), 3)
            self.assertEqual(tasks[t1]["title"], "Original Task 1")
            self.assertEqual(tasks[t2]["title"], "Original Task 2")
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)


class TestTaskListCSVIntegration(unittest.TestCase):
    """Verify that TaskListWidget contains Export and Import buttons and handlers."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget

        self.db_path, self.conn = _make_temp_db()
        self.patchers = [
            patch("task_manager.ui.task_list.get_active_tasks", return_value=[]),
            patch("task_manager.ui.task_list.get_all_categories", return_value=[]),
            patch("task_manager.ui.task_list.search_tasks", return_value=[]),
        ]
        for p in self.patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()
        for p in self.patchers:
            p.stop()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_export_and_import_buttons_exist(self) -> None:
        self.assertTrue(hasattr(self.widget, "export_btn"))
        self.assertTrue(hasattr(self.widget, "import_btn"))
        self.assertEqual(self.widget.export_btn.text(), "Export CSV")
        self.assertEqual(self.widget.import_btn.text(), "Import CSV")

    @patch("task_manager.ui.task_list.QFileDialog.getSaveFileName")
    @patch("task_manager.csv_io.export_tasks_to_csv", return_value=5)
    @patch("task_manager.ui.task_list.QMessageBox.information")
    def test_export_action_flow(self, mock_msg, mock_export, mock_dialog) -> None:
        mock_dialog.return_value = ("my_tasks.csv", "CSV Files (*.csv)")
        self.widget._on_export_csv()

        mock_export.assert_called_once_with("my_tasks.csv")
        mock_msg.assert_called_once()
        self.assertIn("Successfully exported 5 task(s)", mock_msg.call_args[0][2])

    @patch("task_manager.ui.task_list.QFileDialog.getOpenFileName")
    @patch("task_manager.csv_io.import_tasks_from_csv", return_value=(3, []))
    @patch("task_manager.ui.task_list.QMessageBox.information")
    def test_import_action_flow_success(self, mock_msg, mock_import, mock_dialog) -> None:
        mock_dialog.return_value = ("valid_tasks.csv", "CSV Files (*.csv)")
        self.widget._on_import_csv()

        mock_import.assert_called_once_with("valid_tasks.csv")
        mock_msg.assert_called_once()
        self.assertIn("Successfully imported 3 task(s)", mock_msg.call_args[0][2])


if __name__ == "__main__":
    unittest.main()
