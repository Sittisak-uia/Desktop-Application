"""Unit tests for task_manager.ui.dashboard.

Uses the standard library unittest only -- no pytest dependency.
Statistics come from a temporary SQLite database via the existing
database layer, so the production tasks.db is never touched.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from task_manager.database import (
    add_category,
    add_task,
    get_dashboard_stats,
    initialize_database,
    seed_default_user,
    soft_delete_task,
    update_task,
)
from task_manager.ui.dashboard import DashboardWidget

_app = QApplication.instance() or QApplication(sys.argv)


def _make_temp_db() -> tuple[str, sqlite3.Connection]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    seed_default_user(conn)
    return path, conn


def _today() -> str:
    return date.today().isoformat()


def _future() -> str:
    return (date.today() + timedelta(days=5)).isoformat()


def _past() -> str:
    return (date.today() - timedelta(days=5)).isoformat()


def _make_widget(conn: sqlite3.Connection) -> tuple[DashboardWidget, object]:
    patcher = patch(
        "task_manager.ui.dashboard.get_dashboard_stats",
        side_effect=lambda: get_dashboard_stats(conn=conn),
    )
    patcher.start()
    widget = DashboardWidget()
    return widget, patcher


class _BaseCase(unittest.TestCase):
    """Shared setup: temp DB plus patched dashboard stats."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.widget, self.patcher = _make_widget(self.conn)
        self.widget.show()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)


class TestDashboardInstantiation(_BaseCase):
    """Test DashboardWidget can be instantiated."""

    def test_can_be_instantiated(self) -> None:
        self.assertIsInstance(self.widget, DashboardWidget)

    def test_refresh_button_exists(self) -> None:
        self.assertIsNotNone(self.widget.refresh_btn)
        self.assertEqual(self.widget.refresh_btn.text(), "Refresh")

    def test_summary_cards_exist(self) -> None:
        self.assertIsNotNone(self.widget.total_card)
        self.assertIsNotNone(self.widget.pending_card)
        self.assertIsNotNone(self.widget.completed_card)
        self.assertIsNotNone(self.widget.overdue_card)


class TestDashboardEmpty(_BaseCase):
    """Empty database displays zero totals."""

    def test_zero_totals(self) -> None:
        self.assertEqual(self.widget.total_card._get_value(), 0)
        self.assertEqual(self.widget.pending_card._get_value(), 0)
        self.assertEqual(self.widget.completed_card._get_value(), 0)
        self.assertEqual(self.widget.overdue_card._get_value(), 0)

    def test_zero_priority_counts(self) -> None:
        self.assertIn("Low: 0", self.widget.low_label.text())
        self.assertIn("Medium: 0", self.widget.medium_label.text())
        self.assertIn("High: 0", self.widget.high_label.text())

    def test_category_section_handles_empty(self) -> None:
        # No tasks -> the category section shows an empty hint label
        self.assertGreaterEqual(self.widget.category_layout.count(), 1)


class TestDashboardCounts(_BaseCase):
    """Test individual statistic totals."""

    def setUp(self) -> None:
        super().setUp()
        add_task("Task A", status="PENDING", conn=self.conn)
        add_task("Task B", status="COMPLETED", conn=self.conn)
        add_task("Task C", status="PENDING", due_date=_future(), conn=self.conn)
        add_task("Task D", status="PENDING", due_date=_past(), conn=self.conn)
        add_task("Task E", status="COMPLETED", due_date=_past(), conn=self.conn)
        self.widget.refresh()

    def test_total_active_count(self) -> None:
        self.assertEqual(self.widget.total_card._get_value(), 5)

    def test_pending_count(self) -> None:
        self.assertEqual(self.widget.pending_card._get_value(), 3)

    def test_completed_count(self) -> None:
        self.assertEqual(self.widget.completed_card._get_value(), 2)

    def test_overdue_count(self) -> None:
        # Only pending tasks with a past due date count as overdue.
        self.assertEqual(self.widget.overdue_card._get_value(), 1)

    def test_completed_overdue_not_counted(self) -> None:
        # Task E is completed with a past due date but must NOT be overdue.
        task_e = self.conn.execute(
            "SELECT * FROM tasks WHERE title = ?", ("Task E",)
        ).fetchone()
        self.assertEqual(task_e["status"], "COMPLETED")
        self.assertIsNotNone(task_e["due_date"])
        self.assertEqual(self.widget.overdue_card._get_value(), 1)

    def test_task_without_due_date_not_overdue(self) -> None:
        # Task A has no due date and must not be overdue.
        self.assertEqual(self.widget.overdue_card._get_value(), 1)


class TestDashboardDeletedExcluded(_BaseCase):
    """Deleted tasks are excluded from statistics."""

    def setUp(self) -> None:
        super().setUp()
        add_task("Keep Me", status="PENDING", conn=self.conn)
        add_task("Delete Me", status="PENDING", conn=self.conn)
        self.to_delete = self.conn.execute(
            "SELECT id FROM tasks WHERE title = ?", ("Delete Me",)
        ).fetchone()["id"]
        soft_delete_task(self.to_delete, conn=self.conn)
        self.widget.refresh()

    def test_deleted_excluded_from_total(self) -> None:
        self.assertEqual(self.widget.total_card._get_value(), 1)

    def test_deleted_excluded_from_pending(self) -> None:
        self.assertEqual(self.widget.pending_card._get_value(), 1)


class TestDashboardPriority(_BaseCase):
    """Priority breakdown counts are correct."""

    def setUp(self) -> None:
        super().setUp()
        add_task("Low A", priority="LOW", conn=self.conn)
        add_task("Low B", priority="LOW", conn=self.conn)
        add_task("Medium A", priority="MEDIUM", conn=self.conn)
        add_task("High A", priority="HIGH", conn=self.conn)
        add_task("High B", priority="HIGH", conn=self.conn)
        add_task("High C", priority="HIGH", conn=self.conn)
        self.widget.refresh()

    def test_low_count(self) -> None:
        self.assertIn("Low: 2", self.widget.low_label.text())

    def test_medium_count(self) -> None:
        self.assertIn("Medium: 1", self.widget.medium_label.text())

    def test_high_count(self) -> None:
        self.assertIn("High: 3", self.widget.high_label.text())


class TestDashboardCategory(_BaseCase):
    """Category breakdown counts are correct."""

    def setUp(self) -> None:
        super().setUp()
        work_id = add_category("Work", conn=self.conn)
        personal_id = add_category("Personal", conn=self.conn)
        add_task("Work Task 1", category_id=work_id, conn=self.conn)
        add_task("Work Task 2", category_id=work_id, conn=self.conn)
        add_task("Personal Task", category_id=personal_id, conn=self.conn)
        add_task("No Cat Task", category_id=None, conn=self.conn)
        self.widget.refresh()

    def test_category_counts(self) -> None:
        texts = self._category_texts()
        self.assertIn("Work: 2", texts)
        self.assertIn("Personal: 1", texts)

    def test_uncategorized_count(self) -> None:
        texts = self._category_texts()
        self.assertIn("Uncategorized: 1", texts)

    def test_deleted_excluded_from_category_counts(self) -> None:
        to_delete = self.conn.execute(
            "SELECT id FROM tasks WHERE title = ?", ("Work Task 2",)
        ).fetchone()["id"]
        soft_delete_task(to_delete, conn=self.conn)
        self.widget.refresh()
        texts = self._category_texts()
        self.assertIn("Work: 1", texts)

    def _category_texts(self) -> list[str]:
        texts = []
        for i in range(self.widget.category_layout.count()):
            item = self.widget.category_layout.itemAt(i)
            w = item.widget()
            if w is not None:
                texts.append(w.text())
        return texts


class TestDashboardRefresh(_BaseCase):
    """Refresh updates displayed statistics."""

    def test_refresh_updates_totals(self) -> None:
        self.assertEqual(self.widget.total_card._get_value(), 0)
        add_task("New Task", conn=self.conn)
        self.widget.refresh()
        self.assertEqual(self.widget.total_card._get_value(), 1)

    def test_refresh_updates_priority(self) -> None:
        add_task("Med Task", priority="MEDIUM", conn=self.conn)
        self.widget.refresh()
        self.assertIn("Medium: 1", self.widget.medium_label.text())


class TestDashboardMissingCategories(_BaseCase):
    """Dashboard handles missing/empty categories safely."""

    def setUp(self) -> None:
        super().setUp()
        # Create a task whose category was deleted (category_id orphaned).
        add_task("Orphan Cat", category_id=None, conn=self.conn)
        # Directly insert a task with a nonexistent category_id, bypassing
        # the FK constraint to simulate an orphaned reference.
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.conn.execute(
            """INSERT INTO tasks
               (title, description, priority, category_id, due_date,
                status, is_deleted, created_at, completed_at)
               VALUES ('Ghost Cat', '', 'LOW', 99999, NULL, 'PENDING', 0, '', NULL)"""
        )
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.commit()
        self.widget.refresh()

    def test_does_not_crash(self) -> None:
        self.assertEqual(self.widget.total_card._get_value(), 2)

    def test_unmapped_category_shows_as_uncategorized(self) -> None:
        texts = []
        for i in range(self.widget.category_layout.count()):
            item = self.widget.category_layout.itemAt(i)
            w = item.widget()
            if w is not None:
                texts.append(w.text())
        self.assertIn("Uncategorized: 2", texts)


class TestDashboardReadOnly(_BaseCase):
    """Dashboard must not modify task data."""

    def setUp(self) -> None:
        super().setUp()
        add_task("Immutable", status="PENDING", conn=self.conn)
        self.before = self.conn.execute("SELECT * FROM tasks").fetchall()
        self.widget.refresh()

    def test_task_data_unchanged(self) -> None:
        after = self.conn.execute("SELECT * FROM tasks").fetchall()
        self.assertEqual(len(self.before), len(after))
        for row_before, row_after in zip(self.before, after):
            self.assertEqual(dict(row_before), dict(row_after))


if __name__ == "__main__":
    unittest.main()