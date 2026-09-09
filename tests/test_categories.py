"""Focused unit tests for task_manager.ui.categories.

Uses the standard library unittest only -- no pytest dependency.
All database functions are routed to a temporary SQLite database so the
production tasks.db is never touched.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from task_manager.database import (
    add_category,
    add_task,
    delete_category,
    get_all_categories,
    initialize_database,
    search_tasks,
    seed_default_user,
    update_category,
)
from task_manager.ui.categories import CategoriesWidget, _INPUT_DIALOG_STYLE, _MESSAGE_STYLE

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


def _make_widget(conn: sqlite3.Connection) -> CategoriesWidget:
    patchers = [
        patch("task_manager.ui.categories.get_all_categories",
              side_effect=lambda: get_all_categories(conn=conn)),
        patch("task_manager.ui.categories.add_category",
              side_effect=lambda name: add_category(name, conn=conn)),
        patch("task_manager.ui.categories.update_category",
              side_effect=lambda cid, name: update_category(cid, name, conn=conn)),
        patch("task_manager.ui.categories.delete_category",
              side_effect=lambda cid: delete_category(cid, conn=conn)),
        patch("task_manager.ui.categories._confirm", return_value=False),
        patch("task_manager.ui.categories._show_critical"),
        patch("task_manager.ui.categories._show_warning"),
        patch.object(CategoriesWidget, "_prompt_for_name",
                     return_value=("", False)),
    ]
    for p in patchers:
        p.start()
    try:
        widget = CategoriesWidget()
    except Exception:
        for p in patchers:
            p.stop()
        raise
    return widget, patchers


class _BaseCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.widget, self._patchers = _make_widget(self.conn)
        self._text_patcher = self._patchers[-1]
        self.widget.show()

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def _names(self) -> list[str]:
        return [self.widget.table.item(r, 0).text()
                for r in range(self.widget.table.rowCount())]


class TestCategories(_BaseCase):
    """Focused category CRUD behaviour."""

    def test_can_be_instantiated(self) -> None:
        self.assertIsInstance(self.widget, CategoriesWidget)

    def test_existing_categories_are_displayed(self) -> None:
        add_category("Work", conn=self.conn)
        self.widget.refresh()
        self.assertIn("Work", self._names())

    def test_add_category_works(self) -> None:
        self._set_input("New Cat", accepted=True)
        self.widget._on_add()
        self.assertIn("New Cat", self._names())
        names = get_all_categories(conn=self.conn)
        self.assertTrue(any(c["name"] == "New Cat" for c in names))

    def test_blank_category_is_rejected(self) -> None:
        self._set_input("   ", accepted=True)
        with patch("task_manager.ui.categories._show_warning") as warn:
            self.widget._on_add()
        self.assertTrue(warn.called)
        self.assertEqual(self.widget.table.rowCount(), 0)

    def test_duplicate_category_is_rejected(self) -> None:
        add_category("Work", conn=self.conn)
        self.widget.refresh()
        self._set_input("Work", accepted=True)
        with patch("task_manager.ui.categories._show_warning") as warn:
            self.widget._on_add()
        self.assertTrue(warn.called)
        # Only one "Work" remains.
        self.assertEqual(self._names().count("Work"), 1)

    def test_edit_category_works(self) -> None:
        cid = add_category("Old", conn=self.conn)
        self.widget.refresh()
        self._select_first()
        self._set_input("Renamed", accepted=True)
        self.widget._on_edit()
        self.assertIn("Renamed", self._names())
        self.assertNotIn("Old", self._names())

    def test_delete_category_works(self) -> None:
        add_category("Temp", conn=self.conn)
        self.widget.refresh()
        self._select_first()
        with patch("task_manager.ui.categories._confirm", return_value=True):
            self.widget._on_delete()
        self.assertNotIn("Temp", self._names())

    def test_delete_category_does_not_delete_tasks(self) -> None:
        cid = add_category("Del", conn=self.conn)
        add_task("Keep Me", category_id=cid, conn=self.conn)
        self.widget.refresh()
        self._select_row("Del")
        with patch("task_manager.ui.categories._confirm", return_value=True):
            self.widget._on_delete()
        task = self.conn.execute(
            "SELECT * FROM tasks WHERE title = ?", ("Keep Me",)
        ).fetchone()
        self.assertIsNotNone(task)
        self.assertIsNone(task["category_id"])

    def test_deleted_category_displays_as_uncategorized(self) -> None:
        from task_manager.ui.task_list import TaskListWidget

        cid = add_category("Critical", conn=self.conn)
        add_task("Critical Task", category_id=cid, conn=self.conn)
        self.widget.refresh()
        self._select_row("Critical")
        with patch("task_manager.ui.categories._confirm", return_value=True):
            self.widget._on_delete()

        def _search(keyword="", category_id=None, priority=None, status=None,
                    conn=None):
            return search_tasks(
                keyword=keyword, category_id=category_id, priority=priority,
                status=status, conn=self.conn,
            )

        with patch("task_manager.ui.task_list.get_all_categories",
                   side_effect=lambda: get_all_categories(conn=self.conn)), \
             patch("task_manager.ui.task_list.search_tasks", side_effect=_search):
            list_widget = TaskListWidget()
            list_widget.show()
            try:
                self.assertEqual(list_widget.table.rowCount(), 1)
                self.assertEqual(list_widget.table.item(0, 2).text(), "Uncategorized")
            finally:
                list_widget.close()
                list_widget.deleteLater()

    def test_no_selection_does_not_crash(self) -> None:
        with patch("task_manager.ui.categories._show_warning"):
            self.widget._on_edit()
            self.widget._on_delete()

    def test_table_styles_are_readable(self) -> None:
        style = self.widget.table.styleSheet()
        # Cell text and header text must be dark on the light background.
        self.assertIn("color: #2c3e50", style)
        self.assertIn("QHeaderView::section", style)
        # Dialogs and message boxes use dark readable text too.
        self.assertIn("#2c3e50", _INPUT_DIALOG_STYLE)
        self.assertIn("#2c3e50", _MESSAGE_STYLE)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_input(self, text: str, accepted: bool) -> None:
        self._text_patcher.stop()
        self._text_patcher = patch.object(
            CategoriesWidget, "_prompt_for_name",
            return_value=(text, accepted),
        )
        self._text_patcher.start()

    def _select_first(self) -> None:
        self.widget.table.selectRow(0)

    def _select_row(self, name: str) -> None:
        for r in range(self.widget.table.rowCount()):
            if self.widget.table.item(r, 0).text() == name:
                self.widget.table.selectRow(r)
                return
        self.fail(f"No row named '{name}'")


if __name__ == "__main__":
    unittest.main()