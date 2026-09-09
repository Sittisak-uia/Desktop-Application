"""Unit tests for task_manager.ui.task_list.

Uses the standard library unittest only -- no pytest dependency.
Tasks are loaded from a temporary SQLite database so the production
tasks.db is never touched.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QMessageBox, QTableWidget

from task_manager.database import (
    add_category,
    add_task,
    get_active_tasks,
    get_task_by_id,
    initialize_database,
    seed_default_user,
    soft_delete_task,
    update_task,
)

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


def _get_cat_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
    return row["id"]


def _cats(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def _search_tasks(conn: sqlite3.Connection, keyword: str = "",
                  category_id: int | None = None,
                  priority: str | None = None,
                  status: str | None = None) -> list[dict]:
    clauses = ["is_deleted = 0"]
    params: list = []
    if keyword:
        clauses.append("(title LIKE ? OR description LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like])
    if category_id is not None:
        clauses.append("category_id = ?")
        params.append(category_id)
    if priority is not None:
        priority = priority.upper()
        if priority in ("LOW", "MEDIUM", "HIGH"):
            clauses.append("priority = ?")
            params.append(priority)
    if status is not None:
        status = status.upper()
        if status in ("PENDING", "COMPLETED"):
            clauses.append("status = ?")
            params.append(status)
    where = " AND ".join(clauses)
    sql = f"SELECT * FROM tasks WHERE {where} ORDER BY id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def _make_patches(conn: sqlite3.Connection) -> list:
    return [
        patch("task_manager.ui.task_list.get_all_categories",
              side_effect=lambda: _cats(conn)),
        patch("task_manager.ui.task_list.search_tasks",
              side_effect=lambda **kw: _search_tasks(conn,
                  keyword=kw.get("keyword", ""),
                  category_id=kw.get("category_id"),
                  priority=kw.get("priority"),
                  status=kw.get("status"))),
        patch("task_manager.ui.task_list.add_task",
              side_effect=lambda **kw: add_task(**kw, conn=conn)),
        patch("task_manager.ui.task_list.update_task",
              side_effect=lambda **kw: update_task(**kw, conn=conn)),
        patch("task_manager.ui.task_list.soft_delete_task",
              side_effect=lambda tid: soft_delete_task(tid, conn=conn)),
        patch("task_manager.ui.task_list.get_task_by_id",
              side_effect=lambda tid: get_task_by_id(tid, conn=conn)),
        patch("PyQt6.QtWidgets.QMessageBox.warning"),
        patch("PyQt6.QtWidgets.QMessageBox.information"),
        patch("PyQt6.QtWidgets.QMessageBox.critical"),
        patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes),
    ]


class TestTaskListInstantiation(unittest.TestCase):
    """Test TaskListWidget can be instantiated."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()
        self.widget.show()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_can_be_instantiated(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.assertIsInstance(self.widget, TaskListWidget)

    def test_table_exists(self) -> None:
        self.assertIsNotNone(self.widget.table)
        self.assertIsInstance(self.widget.table, QTableWidget)

    def test_search_input_exists(self) -> None:
        self.assertIsNotNone(self.widget.search_input)

    def test_priority_filter_exists(self) -> None:
        self.assertIsNotNone(self.widget.priority_filter)

    def test_status_filter_exists(self) -> None:
        self.assertIsNotNone(self.widget.status_filter)

    def test_category_filter_exists(self) -> None:
        self.assertIsNotNone(self.widget.category_filter)

    def test_add_button_exists(self) -> None:
        self.assertIsNotNone(self.widget.add_btn)

    def test_edit_button_exists(self) -> None:
        self.assertIsNotNone(self.widget.edit_btn)

    def test_complete_button_exists(self) -> None:
        self.assertIsNotNone(self.widget.complete_btn)

    def test_delete_button_exists(self) -> None:
        self.assertIsNotNone(self.widget.delete_btn)

    def test_page_styles_are_readable(self) -> None:
        # Table cells and header use dark text on the light table.
        style = self.widget.table.styleSheet()
        self.assertIn("color: #2c3e50", style)
        self.assertIn("QHeaderView::section", style)
        # Search input and filter combo boxes use dark text too.
        self.assertIn("color: #2c3e50", self.widget.search_input.styleSheet())
        for combo in (
            self.widget.priority_filter,
            self.widget.status_filter,
            self.widget.category_filter,
        ):
            self.assertIn("color: #2c3e50", combo.styleSheet())


class TestTaskListEmptyDatabase(unittest.TestCase):
    """Test TaskListWidget with empty database."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_empty_table_displays_correctly(self) -> None:
        self.assertEqual(self.widget.table.rowCount(), 0)


class TestTaskListDisplay(unittest.TestCase):
    """Test TaskListWidget displays tasks correctly."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        work_id = _get_cat_id(self.conn, "Work")
        add_task("Task 1", priority="LOW", category_id=work_id,
                 due_date="2026-12-31", conn=self.conn)
        add_task("Task 2", priority="HIGH", status="COMPLETED", conn=self.conn)
        add_task("Task 3", priority="MEDIUM", due_date=None, conn=self.conn)

        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_tasks_are_displayed(self) -> None:
        self.assertEqual(self.widget.table.rowCount(), 3)

    def test_title_is_displayed(self) -> None:
        titles = set()
        for row in range(self.widget.table.rowCount()):
            item = self.widget.table.item(row, 0)
            if item:
                titles.add(item.text())
        self.assertEqual(titles, {"Task 1", "Task 2", "Task 3"})

    def test_priority_is_displayed(self) -> None:
        priorities = set()
        for row in range(self.widget.table.rowCount()):
            item = self.widget.table.item(row, 1)
            if item:
                priorities.add(item.text())
        self.assertTrue(priorities.issubset({"Low", "Medium", "High"}))

    def test_status_is_displayed(self) -> None:
        statuses = set()
        for row in range(self.widget.table.rowCount()):
            item = self.widget.table.item(row, 4)
            if item:
                statuses.add(item.text())
        self.assertTrue(statuses.issubset({"Pending", "Completed"}))

    def test_category_is_displayed(self) -> None:
        categories = set()
        for row in range(self.widget.table.rowCount()):
            item = self.widget.table.item(row, 2)
            if item:
                categories.add(item.text())
        self.assertIn("Work", categories)
        self.assertIn("Uncategorized", categories)


class TestTaskListSoftDelete(unittest.TestCase):
    """Test soft delete functionality."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        add_task("Delete Me", conn=self.conn)
        self.task_id = get_active_tasks(conn=self.conn)[0]["id"]

        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_deleted_task_not_in_active_list(self) -> None:
        task = get_task_by_id(self.task_id, conn=self.conn)
        self.assertIsNotNone(task)
        self.assertEqual(task["is_deleted"], 0)

        soft_delete_task(self.task_id, conn=self.conn)

        task_after = get_task_by_id(self.task_id, conn=self.conn)
        self.assertIsNotNone(task_after)
        self.assertEqual(task_after["is_deleted"], 1)

        active = get_active_tasks(conn=self.conn)
        self.assertEqual(len(active), 0)


class TestTaskListComplete(unittest.TestCase):
    """Test complete/pending status changes."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        add_task("Pending Task", conn=self.conn)
        self.task_id = get_active_tasks(conn=self.conn)[0]["id"]

        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_pending_to_completed_sets_completed_at(self) -> None:
        task = get_task_by_id(self.task_id, conn=self.conn)
        self.assertEqual(task["status"], "PENDING")
        self.assertIsNone(task["completed_at"])

        update_task(
            task_id=self.task_id,
            title=task["title"],
            description=task["description"],
            priority=task["priority"],
            category_id=task["category_id"],
            due_date=task["due_date"],
            status="COMPLETED",
            conn=self.conn,
        )

        task_after = get_task_by_id(self.task_id, conn=self.conn)
        self.assertEqual(task_after["status"], "COMPLETED")
        self.assertIsNotNone(task_after["completed_at"])

    def test_completed_to_pending_clears_completed_at(self) -> None:
        update_task(
            task_id=self.task_id,
            title="Pending Task",
            description="",
            priority="MEDIUM",
            category_id=None,
            due_date=None,
            status="COMPLETED",
            conn=self.conn,
        )

        task = get_task_by_id(self.task_id, conn=self.conn)
        self.assertEqual(task["status"], "COMPLETED")
        self.assertIsNotNone(task["completed_at"])

        update_task(
            task_id=self.task_id,
            title=task["title"],
            description=task["description"],
            priority=task["priority"],
            category_id=task["category_id"],
            due_date=task["due_date"],
            status="PENDING",
            conn=self.conn,
        )

        task_after = get_task_by_id(self.task_id, conn=self.conn)
        self.assertEqual(task_after["status"], "PENDING")
        self.assertIsNone(task_after["completed_at"])


class TestTaskListSearch(unittest.TestCase):
    """Test search functionality."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        add_task("Buy groceries", conn=self.conn)
        add_task("Meeting notes", conn=self.conn)
        add_task("Personal errands", conn=self.conn)

        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_search_finds_matching_tasks(self) -> None:
        self.widget.search_input.setText("groceries")
        self.assertEqual(self.widget.table.rowCount(), 1)
        item = self.widget.table.item(0, 0)
        self.assertIsNotNone(item)
        self.assertEqual(item.text(), "Buy groceries")

    def test_search_is_case_insensitive(self) -> None:
        self.widget.search_input.setText("MEETING")
        self.assertEqual(self.widget.table.rowCount(), 1)
        item = self.widget.table.item(0, 0)
        self.assertIsNotNone(item)
        self.assertEqual(item.text(), "Meeting notes")

    def test_search_no_match(self) -> None:
        self.widget.search_input.setText("xyz")
        self.assertEqual(self.widget.table.rowCount(), 0)


class TestTaskListFilters(unittest.TestCase):
    """Test filter functionality."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        work_id = _get_cat_id(self.conn, "Work")
        personal_id = _get_cat_id(self.conn, "Personal")
        add_task("Low Priority", priority="LOW", category_id=work_id, conn=self.conn)
        add_task("High Priority", priority="HIGH", category_id=personal_id, conn=self.conn)
        add_task("Medium Priority", priority="MEDIUM", status="COMPLETED", conn=self.conn)

        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_priority_filter(self) -> None:
        self.widget.priority_filter.setCurrentText("Low")
        self.assertEqual(self.widget.table.rowCount(), 1)
        item = self.widget.table.item(0, 0)
        self.assertIsNotNone(item)
        self.assertEqual(item.text(), "Low Priority")

    def test_status_filter(self) -> None:
        self.widget.status_filter.setCurrentText("Completed")
        self.assertEqual(self.widget.table.rowCount(), 1)
        item = self.widget.table.item(0, 0)
        self.assertIsNotNone(item)
        self.assertEqual(item.text(), "Medium Priority")

    def test_category_filter(self) -> None:
        for i in range(self.widget.category_filter.count()):
            if self.widget.category_filter.itemText(i) == "Work":
                self.widget.category_filter.setCurrentIndex(i)
                break
        self.assertEqual(self.widget.table.rowCount(), 1)
        item = self.widget.table.item(0, 0)
        self.assertIsNotNone(item)
        self.assertEqual(item.text(), "Low Priority")


class TestTaskListUncategorized(unittest.TestCase):
    """Test Uncategorized tasks are displayed correctly."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        add_task("No Category", category_id=None, conn=self.conn)

        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_uncategorized_task_shows_uncategorized(self) -> None:
        self.assertEqual(self.widget.table.rowCount(), 1)
        item = self.widget.table.item(0, 2)
        self.assertIsNotNone(item)
        self.assertEqual(item.text(), "Uncategorized")


class TestTaskListNoSelection(unittest.TestCase):
    """Test that no-selection actions do not crash."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_edit_no_selection(self) -> None:
        self.widget.table.clearSelection()
        self.widget._on_edit_task()

    def test_complete_no_selection(self) -> None:
        self.widget.table.clearSelection()
        self.widget._on_complete_task()

    def test_delete_no_selection(self) -> None:
        self.widget.table.clearSelection()
        self.widget._on_delete_task()


class TestTaskListRefresh(unittest.TestCase):
    """Test refresh functionality."""

    def setUp(self) -> None:
        from task_manager.ui.task_list import TaskListWidget
        self.db_path, self.conn = _make_temp_db()
        self._patchers = _make_patches(self.conn)
        for p in self._patchers:
            p.start()
        self.widget = TaskListWidget()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_refresh_updates_table(self) -> None:
        self.assertEqual(self.widget.table.rowCount(), 0)

        add_task("New Task", conn=self.conn)
        self.widget.refresh()
        self.assertEqual(self.widget.table.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()
