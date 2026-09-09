"""Unit tests for Duplicate Task feature in SQLite Task Manager PRO.

Phase 13 requirements:
- Duplicate action/button on the Tasks page.
- Exactly one task selected before duplicating.
- If no task is selected: show readable warning, do not create task.
- Creates a new task record with auto-generated ID.
- Copied fields: title, description, priority, category_id, due_date.
- Non-copied fields: id, created_at, completed_at (NULL), is_deleted (0), status (PENDING).
- Completed source tasks duplicate as PENDING with completed_at = NULL.
- Deleted tasks (in Trash) cannot be duplicated.
- Nonexistent tasks fail safely (raise ValueError).
- Task list refreshed and user feedback displayed after duplication.
- Notification system detects overdue duplicates through existing task-change mechanism.
- Light and Dark mode readability preserved.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QPushButton, QMessageBox

from task_manager.database import (
    add_category,
    add_task,
    duplicate_task,
    get_active_tasks,
    get_overdue_tasks,
    get_task_by_id,
    initialize_database,
    seed_default_user,
    soft_delete_task,
)
from task_manager.ui.task_list import TaskListWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


def _connect_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _make_temp_db() -> tuple[str, sqlite3.Connection]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = _connect_db(path)
    initialize_database(conn)
    seed_default_user(conn)
    return path, conn


def _yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _future_days(days: int = 5) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# =========================================================================
#  1. Database Tests
# =========================================================================

class TestDuplicateDatabase(unittest.TestCase):
    """Test duplicate_task database behavior."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.cat_id = add_category("Work", conn=self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_duplicate_existing_pending_task(self) -> None:
        """Duplicate an existing pending task with full attributes."""
        orig_id = add_task(
            title="Design Mockups",
            description="Create Figma components",
            priority="HIGH",
            category_id=self.cat_id,
            due_date=_future_days(4),
            status="PENDING",
            conn=self.conn,
        )
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertIsInstance(new_id, int)
        self.assertNotEqual(new_id, orig_id)

        new_task = get_task_by_id(new_id, conn=self.conn)
        self.assertIsNotNone(new_task)
        self.assertEqual(new_task["title"], "Design Mockups")
        self.assertEqual(new_task["description"], "Create Figma components")
        self.assertEqual(new_task["priority"], "HIGH")
        self.assertEqual(new_task["category_id"], self.cat_id)
        self.assertEqual(new_task["due_date"], _future_days(4))
        self.assertEqual(new_task["status"], "PENDING")
        self.assertEqual(new_task["is_deleted"], 0)
        self.assertIsNone(new_task["completed_at"])
        self.assertIsNotNone(new_task["created_at"])

    def test_duplicate_creates_new_id(self) -> None:
        """Duplicate generates a distinct, auto-incremented database ID."""
        task_id = add_task("Original Task", conn=self.conn)
        new_id = duplicate_task(task_id, conn=self.conn)
        self.assertGreater(new_id, task_id)

    def test_original_task_remains_unchanged(self) -> None:
        """Original task data is completely untouched after duplication."""
        orig_id = add_task(
            title="Original Spec",
            description="Original Description",
            priority="LOW",
            category_id=self.cat_id,
            due_date=_future_days(2),
            status="PENDING",
            conn=self.conn,
        )
        before = dict(get_task_by_id(orig_id, conn=self.conn))
        duplicate_task(orig_id, conn=self.conn)
        after = dict(get_task_by_id(orig_id, conn=self.conn))
        self.assertEqual(before, after)

    def test_title_is_copied(self) -> None:
        orig_id = add_task("Unique Title 123", conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertEqual(get_task_by_id(new_id, conn=self.conn)["title"], "Unique Title 123")

    def test_description_is_copied(self) -> None:
        orig_id = add_task("Task", description="Detailed description text", conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertEqual(get_task_by_id(new_id, conn=self.conn)["description"], "Detailed description text")

    def test_priority_is_copied(self) -> None:
        orig_id = add_task("Task", priority="HIGH", conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertEqual(get_task_by_id(new_id, conn=self.conn)["priority"], "HIGH")

    def test_category_is_copied(self) -> None:
        orig_id = add_task("Task", category_id=self.cat_id, conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertEqual(get_task_by_id(new_id, conn=self.conn)["category_id"], self.cat_id)

    def test_due_date_is_copied(self) -> None:
        due = _future_days(10)
        orig_id = add_task("Task", due_date=due, conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertEqual(get_task_by_id(new_id, conn=self.conn)["due_date"], due)

    def test_duplicate_status_is_pending(self) -> None:
        orig_id = add_task("Task", status="PENDING", conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertEqual(get_task_by_id(new_id, conn=self.conn)["status"], "PENDING")

    def test_duplicate_completed_at_is_null(self) -> None:
        orig_id = add_task("Task", status="COMPLETED", conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertIsNone(get_task_by_id(new_id, conn=self.conn)["completed_at"])

    def test_duplicate_is_deleted_is_zero(self) -> None:
        orig_id = add_task("Task", conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertEqual(get_task_by_id(new_id, conn=self.conn)["is_deleted"], 0)

    def test_duplicate_gets_new_created_at(self) -> None:
        orig_id = add_task("Task", conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        created_at = get_task_by_id(new_id, conn=self.conn)["created_at"]
        self.assertIsNotNone(created_at)
        self.assertGreater(len(created_at), 0)

    def test_cannot_duplicate_nonexistent_task(self) -> None:
        """Duplicating an invalid task ID raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            duplicate_task(99999, conn=self.conn)
        self.assertIn("does not exist", str(ctx.exception))

    def test_cannot_duplicate_deleted_task(self) -> None:
        """Duplicating a soft-deleted task in Trash raises ValueError."""
        task_id = add_task("Trashed Task", conn=self.conn)
        soft_delete_task(task_id, conn=self.conn)
        with self.assertRaises(ValueError) as ctx:
            duplicate_task(task_id, conn=self.conn)
        self.assertIn("deleted task", str(ctx.exception))

    def test_duplicate_completed_task_becomes_pending(self) -> None:
        """When duplicating a completed task, duplicate status is PENDING and completed_at is NULL."""
        orig_id = add_task(
            title="Finished Project",
            status="COMPLETED",
            due_date=_yesterday(),
            conn=self.conn,
        )
        orig_task = get_task_by_id(orig_id, conn=self.conn)
        self.assertEqual(orig_task["status"], "COMPLETED")
        self.assertIsNotNone(orig_task["completed_at"])

        new_id = duplicate_task(orig_id, conn=self.conn)
        new_task = get_task_by_id(new_id, conn=self.conn)
        self.assertEqual(new_task["status"], "PENDING")
        self.assertIsNone(new_task["completed_at"])
        # Original remains COMPLETED
        self.assertEqual(get_task_by_id(orig_id, conn=self.conn)["status"], "COMPLETED")

    def test_duplicate_uncategorized_task(self) -> None:
        """Task without category duplicates with category_id = NULL."""
        orig_id = add_task("Uncategorized Task", category_id=None, conn=self.conn)
        new_id = duplicate_task(orig_id, conn=self.conn)
        self.assertIsNone(get_task_by_id(new_id, conn=self.conn)["category_id"])


# =========================================================================
#  2. UI Tests
# =========================================================================

class TestDuplicateUI(unittest.TestCase):
    """Test Duplicate Task action in TaskListWidget."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.patch_warning = patch("PyQt6.QtWidgets.QMessageBox.warning")
        self.mock_warning = self.patch_warning.start()
        self.patch_info = patch("PyQt6.QtWidgets.QMessageBox.information")
        self.mock_info = self.patch_info.start()
        self.patch_critical = patch("PyQt6.QtWidgets.QMessageBox.critical")
        self.mock_critical = self.patch_critical.start()
        self.patch_db = patch("task_manager.database.get_connection", side_effect=lambda: _connect_db(self.db_path))
        self.patch_db.start()
        self.widget = TaskListWidget()
        self.widget.show()

    def tearDown(self) -> None:
        self.patch_warning.stop()
        self.patch_info.stop()
        self.patch_critical.stop()
        self.patch_db.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_duplicate_button_exists(self) -> None:
        """Duplicate button exists in the button bar."""
        self.assertIsNotNone(self.widget.duplicate_btn)
        self.assertIsInstance(self.widget.duplicate_btn, QPushButton)
        self.assertEqual(self.widget.duplicate_btn.text(), "Duplicate")

    def test_no_selection_shows_warning(self) -> None:
        """Clicking Duplicate without selection displays warning and creates no task."""
        self.widget.table.clearSelection()
        self.widget.table.setCurrentCell(-1, -1)
        self.widget.duplicate_btn.click()

        self.mock_warning.assert_called_once()
        args = self.mock_warning.call_args[0]
        self.assertIn("No Selection", args[1])
        # DB remains empty
        active = get_active_tasks(conn=self.conn)
        self.assertEqual(len(active), 0)

    def test_selected_task_can_be_duplicated(self) -> None:
        """Selecting a task and clicking Duplicate creates the duplicate and gives user feedback."""
        add_task("Weekly Sync", description="Agenda review", priority="MEDIUM", conn=self.conn)
        self.widget.refresh()
        self.assertEqual(self.widget.table.rowCount(), 1)

        self.widget.table.selectRow(0)
        self.widget.duplicate_btn.click()

        self.mock_info.assert_called_once()
        args = self.mock_info.call_args[0]
        self.assertIn("Task Duplicated", args[1])
        self.assertIn("Weekly Sync", args[2])

        # Verify new task appears after refresh
        active = get_active_tasks(conn=self.conn)
        self.assertEqual(len(active), 2)
        self.assertEqual(self.widget.table.rowCount(), 2)
        self.assertEqual(self.widget.table.item(0, 0).text(), "Weekly Sync")
        self.assertEqual(self.widget.table.item(1, 0).text(), "Weekly Sync")

    def test_duplicate_overdue_task_detected_by_notification_system(self) -> None:
        """Duplicating an overdue task creates a new overdue task detected by get_overdue_tasks."""
        add_task("Overdue Item", due_date=_yesterday(), status="PENDING", conn=self.conn)
        self.widget.refresh()
        self.assertEqual(len(get_overdue_tasks(conn=self.conn)), 1)

        self.widget.table.selectRow(0)
        self.widget.duplicate_btn.click()

        # Both original and duplicate are now overdue pending tasks
        overdue = get_overdue_tasks(conn=self.conn)
        self.assertEqual(len(overdue), 2)

    def test_duplicate_button_readability_styling(self) -> None:
        """Verify Duplicate button uses high-contrast text and styling."""
        style = self.widget.duplicate_btn.styleSheet()
        self.assertIn("background-color: #2980b9", style)
        self.assertIn("color: white", style)


if __name__ == "__main__":
    unittest.main()
