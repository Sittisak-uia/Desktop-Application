"""Focused unit tests for task_manager.ui.trash (Phase 9 - Trash / Recycle Bin).

Uses the standard library unittest only -- no pytest dependency.
All database operations use a temporary SQLite database to ensure complete
isolation from production tasks.db.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from task_manager.database import (
    add_category,
    add_task,
    get_all_categories,
    get_trash_tasks,
    initialize_database,
    permanent_delete_task,
    restore_task,
    seed_default_user,
    soft_delete_task,
)
from task_manager.ui.trash import TrashWidget

# Ensure a QApplication exists for headless GUI testing
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


def _make_patches(conn: sqlite3.Connection, confirm_result: bool = True) -> list:
    """Create mock patches for TrashWidget database and dialog calls."""
    return [
        patch(
            "task_manager.ui.trash.get_trash_tasks",
            side_effect=lambda: get_trash_tasks(conn=conn),
        ),
        patch(
            "task_manager.ui.trash.restore_task",
            side_effect=lambda tid: restore_task(tid, conn=conn),
        ),
        patch(
            "task_manager.ui.trash.permanent_delete_task",
            side_effect=lambda tid: permanent_delete_task(tid, conn=conn),
        ),
        patch(
            "task_manager.ui.trash.get_all_categories",
            side_effect=lambda: get_all_categories(conn=conn),
        ),
        patch("task_manager.ui.trash._confirm", return_value=confirm_result),
        patch("task_manager.ui.trash._show_warning"),
        patch("task_manager.ui.trash._show_critical"),
    ]


class TestTrashWidgetInstantiation(unittest.TestCase):
    """Test that TrashWidget can be instantiated and has correct controls."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.patchers = _make_patches(self.conn)
        for p in self.patchers:
            p.start()
        self.widget = TrashWidget()

    def tearDown(self) -> None:
        for p in self.patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_can_be_instantiated(self) -> None:
        self.assertIsInstance(self.widget, TrashWidget)

    def test_page_text_property(self) -> None:
        self.assertEqual(self.widget.text(), "Trash")

    def test_table_exists_and_configured(self) -> None:
        self.assertIsNotNone(self.widget.table)
        self.assertEqual(self.widget.table.columnCount(), 7)
        headers = [
            self.widget.table.horizontalHeaderItem(i).text()
            for i in range(7)
        ]
        self.assertEqual(
            headers,
            ["Title", "Priority", "Category", "Due Date", "Status", "Created At", "Completed At"]
        )

    def test_buttons_exist(self) -> None:
        self.assertIsNotNone(self.widget.restore_btn)
        self.assertIsNotNone(self.widget.delete_btn)
        self.assertIsNotNone(self.widget.refresh_btn)
        self.assertEqual(self.widget.restore_btn.text(), "Restore Task")
        self.assertEqual(self.widget.delete_btn.text(), "Permanently Delete")
        self.assertEqual(self.widget.refresh_btn.text(), "Refresh")

    def test_styles_are_readable(self) -> None:
        """Verify dark text and light styling for text readability."""
        table_style = self.widget.table.styleSheet()
        self.assertIn("#2c3e50", table_style)
        self.assertIn("background-color: white", table_style)


class TestTrashDisplay(unittest.TestCase):
    """Test displaying deleted vs non-deleted tasks."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.cat_id = add_category("Work", conn=self.conn)

        # Add 3 tasks: 2 active, 1 trashed
        self.t1 = add_task("Active Task 1", category_id=self.cat_id, conn=self.conn)
        self.t2 = add_task("Trashed Task 1", category_id=self.cat_id, priority="HIGH", due_date="2026-10-01", conn=self.conn)
        self.t3 = add_task("Active Task 2", conn=self.conn)
        self.t4 = add_task("Trashed Task 2", priority="LOW", conn=self.conn)

        # Soft delete t2 and t4
        soft_delete_task(self.t2, conn=self.conn)
        soft_delete_task(self.t4, conn=self.conn)

        self.patchers = _make_patches(self.conn)
        for p in self.patchers:
            p.start()
        self.widget = TrashWidget()

    def tearDown(self) -> None:
        for p in self.patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_deleted_tasks_are_displayed(self) -> None:
        self.assertEqual(self.widget.table.rowCount(), 2)
        titles = {
            self.widget.table.item(r, 0).text()
            for r in range(self.widget.table.rowCount())
        }
        self.assertIn("Trashed Task 1", titles)
        self.assertIn("Trashed Task 2", titles)

    def test_non_deleted_tasks_not_displayed(self) -> None:
        titles = {
            self.widget.table.item(r, 0).text()
            for r in range(self.widget.table.rowCount())
        }
        self.assertNotIn("Active Task 1", titles)
        self.assertNotIn("Active Task 2", titles)

    def test_category_name_mapping(self) -> None:
        # Find row for Trashed Task 1
        for r in range(self.widget.table.rowCount()):
            if self.widget.table.item(r, 0).text() == "Trashed Task 1":
                self.assertEqual(self.widget.table.item(r, 2).text(), "Work")
            elif self.widget.table.item(r, 0).text() == "Trashed Task 2":
                self.assertEqual(self.widget.table.item(r, 2).text(), "Uncategorized")


class TestTrashRestore(unittest.TestCase):
    """Test restoring a task from the trash."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.cat_id = add_category("Personal", conn=self.conn)
        self.task_id = add_task(
            "Important Task",
            description="Detailed description",
            priority="HIGH",
            category_id=self.cat_id,
            due_date="2026-12-31",
            status="PENDING",
            conn=self.conn,
        )
        soft_delete_task(self.task_id, conn=self.conn)

        self.patchers = _make_patches(self.conn)
        for p in self.patchers:
            p.start()
        self.widget = TrashWidget()

    def tearDown(self) -> None:
        for p in self.patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_restore_task_sets_is_deleted_zero(self) -> None:
        self.assertEqual(self.widget.table.rowCount(), 1)
        self.widget.table.selectRow(0)
        self.widget._on_restore_task()

        # Database check
        row = self.conn.execute(
            "SELECT is_deleted FROM tasks WHERE id = ?", (self.task_id,)
        ).fetchone()
        self.assertEqual(row["is_deleted"], 0)

        # Trash table should now be empty
        self.assertEqual(self.widget.table.rowCount(), 0)

    def test_restored_task_retains_info(self) -> None:
        self.widget.table.selectRow(0)
        self.widget._on_restore_task()

        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (self.task_id,)
        ).fetchone()
        self.assertEqual(row["title"], "Important Task")
        self.assertEqual(row["description"], "Detailed description")
        self.assertEqual(row["priority"], "HIGH")
        self.assertEqual(row["category_id"], self.cat_id)
        self.assertEqual(row["due_date"], "2026-12-31")
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(row["is_deleted"], 0)


class TestTrashPermanentDelete(unittest.TestCase):
    """Test permanently deleting tasks."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.t1 = add_task("Delete Me", conn=self.conn)
        self.t2 = add_task("Keep Me In Trash", conn=self.conn)
        self.t3 = add_task("Active Unrelated", conn=self.conn)

        soft_delete_task(self.t1, conn=self.conn)
        soft_delete_task(self.t2, conn=self.conn)

        self.patchers = _make_patches(self.conn, confirm_result=True)
        for p in self.patchers:
            p.start()
        self.widget = TrashWidget()

    def tearDown(self) -> None:
        for p in self.patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_permanent_delete_removes_task(self) -> None:
        # Select row for t1 ("Delete Me")
        target_row = -1
        for r in range(self.widget.table.rowCount()):
            if self.widget.table.item(r, 0).text() == "Delete Me":
                target_row = r
                break
        self.assertGreaterEqual(target_row, 0)
        self.widget.table.selectRow(target_row)
        self.widget._on_permanent_delete_task()

        # Verify t1 is permanently gone from SQLite
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM tasks WHERE id = ?", (self.t1,)
        ).fetchone()
        self.assertEqual(row["cnt"], 0)

    def test_permanent_delete_does_not_affect_unrelated_tasks(self) -> None:
        target_row = -1
        for r in range(self.widget.table.rowCount()):
            if self.widget.table.item(r, 0).text() == "Delete Me":
                target_row = r
                break
        self.widget.table.selectRow(target_row)
        self.widget._on_permanent_delete_task()

        # t2 should still exist in trash
        row_t2 = self.conn.execute(
            "SELECT is_deleted FROM tasks WHERE id = ?", (self.t2,)
        ).fetchone()
        self.assertIsNotNone(row_t2)
        self.assertEqual(row_t2["is_deleted"], 1)

        # t3 should still exist as active
        row_t3 = self.conn.execute(
            "SELECT is_deleted FROM tasks WHERE id = ?", (self.t3,)
        ).fetchone()
        self.assertIsNotNone(row_t3)
        self.assertEqual(row_t3["is_deleted"], 0)


class TestTrashEdgeCases(unittest.TestCase):
    """Test edge cases: no selection, cancel confirmation, and refresh."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.t1 = add_task("Pending Trash", conn=self.conn)
        soft_delete_task(self.t1, conn=self.conn)

        self.patchers = _make_patches(self.conn, confirm_result=False)
        for p in self.patchers:
            p.start()
        self.widget = TrashWidget()

    def tearDown(self) -> None:
        for p in self.patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_restore_no_selection_safe(self) -> None:
        self.widget.table.clearSelection()
        self.widget.table.setCurrentCell(-1, -1)
        # Should not crash or throw
        self.widget._on_restore_task()

    def test_permanent_delete_no_selection_safe(self) -> None:
        self.widget.table.clearSelection()
        self.widget.table.setCurrentCell(-1, -1)
        # Should not crash or throw
        self.widget._on_permanent_delete_task()

    def test_permanent_delete_cancelled_does_not_delete(self) -> None:
        self.widget.table.selectRow(0)
        # _confirm returns False in this test case
        self.widget._on_permanent_delete_task()

        row = self.conn.execute(
            "SELECT is_deleted FROM tasks WHERE id = ?", (self.t1,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["is_deleted"], 1)
        self.assertEqual(self.widget.table.rowCount(), 1)

    def test_trash_refresh_updates_list(self) -> None:
        self.assertEqual(self.widget.table.rowCount(), 1)
        t2 = add_task("Another Trashed", conn=self.conn)
        soft_delete_task(t2, conn=self.conn)

        self.widget.refresh()
        self.assertEqual(self.widget.table.rowCount(), 2)


class TestMainWindowTrashIntegration(unittest.TestCase):
    """Test MainWindow integration with Trash page."""

    def setUp(self) -> None:
        from task_manager.ui.main_window import MainWindow

        self.db_path, self.conn = _make_temp_db()
        # Patch all components so MainWindow instantiates cleanly in headless mode
        self.patchers = [
            patch("task_manager.ui.dashboard.get_dashboard_stats", return_value={
                "total": 0, "pending": 0, "completed": 0, "overdue": 0,
                "by_category": {}, "by_priority": {}
            }),
            patch("task_manager.ui.task_list.get_active_tasks", return_value=[]),
            patch("task_manager.ui.task_list.get_all_categories", return_value=[]),
            patch("task_manager.ui.task_list.search_tasks", return_value=[]),
            patch("task_manager.ui.categories.get_all_categories", return_value=[]),
            patch("task_manager.ui.trash.get_trash_tasks", return_value=[]),
            patch("task_manager.ui.trash.get_all_categories", return_value=[]),
        ]
        for p in self.patchers:
            p.start()
        self.win = MainWindow()

    def tearDown(self) -> None:
        self.win.close()
        self.win.deleteLater()
        for p in self.patchers:
            p.stop()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_main_window_has_trash_widget_at_index_three(self) -> None:
        trash_widget = self.win._stack.widget(3)
        self.assertIsInstance(trash_widget, TrashWidget)

    def test_main_window_navigation_to_trash(self) -> None:
        # Click sidebar Trash button (index 3)
        self.win._nav_buttons[3].click()
        self.assertEqual(self.win._stack.currentIndex(), 3)
        # Verify active button styling
        self.assertIn("3498db", self.win._nav_buttons[3].styleSheet())


if __name__ == "__main__":
    unittest.main()
