"""Unit tests for task_manager.database module.

Uses the standard library unittest only -- no pytest dependency.
Every test uses an in-memory SQLite database for isolation.
"""

import csv
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from task_manager.database import (
    _DB_FILENAME,
    add_category,
    add_task,
    backup_database,
    delete_category,
    duplicate_task,
    export_tasks_to_csv,
    get_active_tasks,
    get_all_categories,
    get_connection,
    get_dashboard_stats,
    get_due_today_tasks,
    get_overdue_tasks,
    get_task_by_id,
    get_trash_tasks,
    get_user_by_username,
    import_tasks_from_csv,
    initialize_database,
    permanent_delete_task,
    restore_database,
    restore_task,
    seed_default_user,
    search_tasks,
    soft_delete_task,
    update_category,
    update_task,
)
from task_manager.models import Category, Task, User


def _in_memory_conn() -> sqlite3.Connection:
    """Return a fresh in-memory connection with schema and seed data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    seed_default_user(conn)
    return conn


# =====================================================================
#  SCHEMA / SEED
# =====================================================================

class TestInitializeDatabase(unittest.TestCase):
    def test_creates_tables(self) -> None:
        conn = _in_memory_conn()
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("users", tables)
        self.assertIn("categories", tables)
        self.assertIn("tasks", tables)
        conn.close()

    def test_idempotent(self) -> None:
        conn = _in_memory_conn()
        initialize_database(conn)
        initialize_database(conn)
        conn.close()


class TestForeignKeyEnforcement(unittest.TestCase):
    def test_foreign_keys_enabled_on_fresh_connection(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = get_connection(path)
            try:
                self.assertEqual(
                    conn.execute("PRAGMA foreign_keys").fetchone()[0],
                    1,
                )
            finally:
                conn.close()
        finally:
            os.unlink(path)

    def test_foreign_keys_enabled_by_default_connection(self) -> None:
        """The default (production) connection must also enforce FKs."""
        conn = get_connection()
        try:
            self.assertEqual(
                conn.execute("PRAGMA foreign_keys").fetchone()[0],
                1,
            )
        finally:
            conn.close()


class TestSeedDefaultUser(unittest.TestCase):
    def test_creates_admin(self) -> None:
        conn = _in_memory_conn()
        user = get_user_by_username("admin", conn=conn)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "admin")
        conn.close()

    def test_admin_has_hash_and_salt(self) -> None:
        conn = _in_memory_conn()
        user = get_user_by_username("admin", conn=conn)
        self.assertTrue(user["password_hash"])
        self.assertTrue(user["salt"])
        conn.close()

    def test_idempotent(self) -> None:
        conn = _in_memory_conn()
        seed_default_user(conn)
        row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        self.assertEqual(row["cnt"], 1)
        conn.close()


# =====================================================================
#  USER
# =====================================================================

class TestGetUserByUsername(unittest.TestCase):
    def test_existing_user(self) -> None:
        conn = _in_memory_conn()
        user = get_user_by_username("admin", conn=conn)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "admin")
        conn.close()

    def test_nonexistent_user(self) -> None:
        conn = _in_memory_conn()
        user = get_user_by_username("nobody", conn=conn)
        self.assertIsNone(user)
        conn.close()


# =====================================================================
#  CATEGORIES
# =====================================================================

class TestCategoryCRUD(unittest.TestCase):
    def test_add_and_get(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("Work", conn=conn)
        cats = get_all_categories(conn=conn)
        self.assertEqual(len(cats), 1)
        self.assertEqual(cats[0]["name"], "Work")
        self.assertEqual(cats[0]["id"], cat_id)
        conn.close()

    def test_add_empty_name_raises(self) -> None:
        conn = _in_memory_conn()
        with self.assertRaises(ValueError):
            add_category("", conn=conn)
        conn.close()

    def test_add_whitespace_only_raises(self) -> None:
        conn = _in_memory_conn()
        with self.assertRaises(ValueError):
            add_category("   ", conn=conn)
        conn.close()

    def test_add_duplicate_raises(self) -> None:
        conn = _in_memory_conn()
        add_category("Work", conn=conn)
        with self.assertRaises(sqlite3.IntegrityError):
            add_category("Work", conn=conn)
        conn.close()

    def test_update(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("Old", conn=conn)
        update_category(cat_id, "New", conn=conn)
        cats = get_all_categories(conn=conn)
        self.assertEqual(cats[0]["name"], "New")
        conn.close()

    def test_update_empty_name_raises(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("X", conn=conn)
        with self.assertRaises(ValueError):
            update_category(cat_id, "", conn=conn)
        conn.close()

    def test_delete_unassigns_tasks(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("DeleteMe", conn=conn)
        task_id = add_task("T", category_id=cat_id, conn=conn)
        delete_category(cat_id, conn=conn)
        task = get_task_by_id(task_id, conn=conn)
        self.assertIsNone(task["category_id"])
        self.assertEqual(get_all_categories(conn=conn), [])
        conn.close()

    def test_delete_category_sets_task_category_to_null(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("Test Category", conn=conn)
        task_id = add_task("Assigned Task", category_id=cat_id, conn=conn)
        delete_category(cat_id, conn=conn)
        task = get_task_by_id(task_id, conn=conn)
        self.assertIsNotNone(task)
        self.assertIsNone(task["category_id"])
        conn.close()

    def test_delete_category_keeps_unrelated_tasks(self) -> None:
        conn = _in_memory_conn()
        cat_a = add_category("A", conn=conn)
        cat_b = add_category("B", conn=conn)
        task_a = add_task("In A", category_id=cat_a, conn=conn)
        task_b = add_task("In B", category_id=cat_b, conn=conn)
        task_none = add_task("No Category", conn=conn)
        delete_category(cat_a, conn=conn)
        # Unrelated tasks are untouched and their categories stay intact.
        self.assertEqual(get_task_by_id(task_b, conn=conn)["category_id"], cat_b)
        self.assertEqual(get_task_by_id(task_none, conn=conn)["category_id"], None)
        # The deleted category's own task still exists, just unassigned.
        task = get_task_by_id(task_a, conn=conn)
        self.assertIsNotNone(task)
        self.assertIsNone(task["category_id"])
        conn.close()

    def test_get_all_empty(self) -> None:
        conn = _in_memory_conn()
        self.assertEqual(get_all_categories(conn=conn), [])
        conn.close()

    def test_get_all_sorted(self) -> None:
        conn = _in_memory_conn()
        add_category("Zebra", conn=conn)
        add_category("Alpha", conn=conn)
        cats = get_all_categories(conn=conn)
        names = [c["name"] for c in cats]
        self.assertEqual(names, ["Alpha", "Zebra"])
        conn.close()


# =====================================================================
#  TASKS — basic CRUD
# =====================================================================

class TestAddTask(unittest.TestCase):
    def test_add_pending_task(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("Buy milk", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["title"], "Buy milk")
        self.assertEqual(task["status"], "PENDING")
        self.assertEqual(task["priority"], "MEDIUM")
        self.assertIsNone(task["completed_at"])
        self.assertTrue(task["created_at"])
        self.assertFalse(task["is_deleted"])
        conn.close()

    def test_add_completed_task_sets_completed_at(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("Done", status="COMPLETED", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["status"], "COMPLETED")
        self.assertIsNotNone(task["completed_at"])
        conn.close()

    def test_empty_title_raises(self) -> None:
        conn = _in_memory_conn()
        with self.assertRaises(ValueError):
            add_task("", conn=conn)
        conn.close()

    def test_invalid_priority_raises(self) -> None:
        conn = _in_memory_conn()
        with self.assertRaises(ValueError):
            add_task("T", priority="URGENT", conn=conn)
        conn.close()

    def test_invalid_status_raises(self) -> None:
        conn = _in_memory_conn()
        with self.assertRaises(ValueError):
            add_task("T", status="DONE", conn=conn)
        conn.close()

    def test_invalid_due_date_raises(self) -> None:
        conn = _in_memory_conn()
        with self.assertRaises(ValueError):
            add_task("T", due_date="not-a-date", conn=conn)
        conn.close()

    def test_valid_due_date(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", due_date="2026-01-15", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["due_date"], "2026-01-15")
        conn.close()

    def test_none_category(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", category_id=None, conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertIsNone(task["category_id"])
        conn.close()

    def test_valid_category(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("Work", conn=conn)
        tid = add_task("T", category_id=cat_id, conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["category_id"], cat_id)
        conn.close()

    def test_description_default_empty(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["description"], "")
        conn.close()


class TestUpdateTask(unittest.TestCase):
    def test_update_fields(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("Old", description="d", priority="LOW", conn=conn)
        update_task(tid, "New", description="new d", priority="HIGH", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["title"], "New")
        self.assertEqual(task["description"], "new d")
        self.assertEqual(task["priority"], "HIGH")
        conn.close()

    def test_pending_to_completed_sets_completed_at(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        update_task(tid, "T", status="COMPLETED", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertIsNotNone(task["completed_at"])
        conn.close()

    def test_completed_to_pending_clears_completed_at(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", status="COMPLETED", conn=conn)
        update_task(tid, "T", status="PENDING", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertIsNone(task["completed_at"])
        conn.close()

    def test_completed_to_completed_keeps_completed_at(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", status="COMPLETED", conn=conn)
        task_before = get_task_by_id(tid, conn=conn)
        old_ca = task_before["completed_at"]
        update_task(tid, "T", status="COMPLETED", conn=conn)
        task_after = get_task_by_id(tid, conn=conn)
        self.assertEqual(task_after["completed_at"], old_ca)
        conn.close()

    def test_pending_to_pending_keeps_null(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        update_task(tid, "T", status="PENDING", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertIsNone(task["completed_at"])
        conn.close()

    def test_update_nonexistent_raises(self) -> None:
        conn = _in_memory_conn()
        with self.assertRaises(ValueError):
            update_task(9999, "X", conn=conn)
        conn.close()

    def test_invalid_priority_raises(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        with self.assertRaises(ValueError):
            update_task(tid, "T", priority="LOWEST", conn=conn)
        conn.close()


class TestSoftDelete(unittest.TestCase):
    def test_soft_delete(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        soft_delete_task(tid, conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertTrue(task["is_deleted"])
        self.assertEqual(get_active_tasks(conn=conn), [])
        conn.close()

    def test_soft_delete_twice_is_safe(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        soft_delete_task(tid, conn=conn)
        soft_delete_task(tid, conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertTrue(task["is_deleted"])
        conn.close()


class TestRestore(unittest.TestCase):
    def test_restore(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        soft_delete_task(tid, conn=conn)
        restore_task(tid, conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertFalse(task["is_deleted"])
        self.assertEqual(len(get_active_tasks(conn=conn)), 1)
        conn.close()

    def test_restore_non_trashed_is_safe(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        restore_task(tid, conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertFalse(task["is_deleted"])
        conn.close()


class TestPermanentDelete(unittest.TestCase):
    def test_permanent_delete(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        soft_delete_task(tid, conn=conn)
        permanent_delete_task(tid, conn=conn)
        self.assertIsNone(get_task_by_id(tid, conn=conn))
        conn.close()

    def test_cannot_permanently_delete_active_task(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", conn=conn)
        permanent_delete_task(tid, conn=conn)
        self.assertIsNotNone(get_task_by_id(tid, conn=conn))
        conn.close()


class TestDuplicateTask(unittest.TestCase):
    def test_duplicate(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("W", conn=conn)
        tid = add_task(
            "Original", description="desc", priority="HIGH",
            category_id=cat_id, due_date="2026-06-01", conn=conn,
        )
        new_id = duplicate_task(tid, conn=conn)
        original = get_task_by_id(tid, conn=conn)
        dup = get_task_by_id(new_id, conn=conn)
        self.assertNotEqual(tid, new_id)
        self.assertEqual(dup["title"], "Original")
        self.assertEqual(dup["description"], "desc")
        self.assertEqual(dup["priority"], "HIGH")
        self.assertEqual(dup["category_id"], cat_id)
        self.assertEqual(dup["due_date"], "2026-06-01")
        self.assertEqual(dup["status"], "PENDING")
        self.assertIsNone(dup["completed_at"])
        self.assertIsNotNone(dup["created_at"])
        conn.close()

    def test_duplicate_nonexistent_raises(self) -> None:
        conn = _in_memory_conn()
        with self.assertRaises(ValueError):
            duplicate_task(9999, conn=conn)
        conn.close()


class TestGetActiveTasks(unittest.TestCase):
    def test_excludes_deleted(self) -> None:
        conn = _in_memory_conn()
        t1 = add_task("A", conn=conn)
        t2 = add_task("B", conn=conn)
        soft_delete_task(t1, conn=conn)
        active = get_active_tasks(conn=conn)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["title"], "B")
        conn.close()

    def test_empty_when_all_deleted(self) -> None:
        conn = _in_memory_conn()
        t1 = add_task("A", conn=conn)
        soft_delete_task(t1, conn=conn)
        self.assertEqual(get_active_tasks(conn=conn), [])
        conn.close()


# =====================================================================
#  SEARCH / FILTER
# =====================================================================

class TestSearchTasks(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _in_memory_conn()
        self.cat_id = add_category("Work", self.conn)
        add_task("Buy milk", priority="LOW", category_id=self.cat_id,
                 due_date="2026-09-15", conn=self.conn)
        add_task("Write report", description="Important report",
                 priority="HIGH", conn=self.conn)
        add_task("Call mom", priority="MEDIUM", status="COMPLETED",
                 conn=self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_no_filters_returns_all_active(self) -> None:
        result = search_tasks(conn=self.conn)
        self.assertEqual(len(result), 3)

    def test_keyword_filter(self) -> None:
        result = search_tasks(keyword="milk", conn=self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Buy milk")

    def test_keyword_in_description(self) -> None:
        result = search_tasks(keyword="Important", conn=self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Write report")

    def test_category_filter(self) -> None:
        result = search_tasks(category_id=self.cat_id, conn=self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Buy milk")

    def test_priority_filter(self) -> None:
        result = search_tasks(priority="HIGH", conn=self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Write report")

    def test_status_filter(self) -> None:
        result = search_tasks(status="COMPLETED", conn=self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Call mom")

    def test_combined_filters(self) -> None:
        result = search_tasks(priority="LOW", category_id=self.cat_id, conn=self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Buy milk")

    def test_no_match(self) -> None:
        result = search_tasks(keyword="nonexistent", conn=self.conn)
        self.assertEqual(len(result), 0)

    def test_excludes_trashed(self) -> None:
        t = add_task("TrashMe", conn=self.conn)
        soft_delete_task(t, self.conn)
        result = search_tasks(conn=self.conn)
        self.assertEqual(len(result), 3)


# =====================================================================
#  TRASH
# =====================================================================

class TestGetTrashTasks(unittest.TestCase):
    def test_trash_list(self) -> None:
        conn = _in_memory_conn()
        t1 = add_task("Active", conn=conn)
        t2 = add_task("Trashed", conn=conn)
        soft_delete_task(t2, conn=conn)
        trash = get_trash_tasks(conn=conn)
        self.assertEqual(len(trash), 1)
        self.assertEqual(trash[0]["title"], "Trashed")
        conn.close()

    def test_empty_trash(self) -> None:
        conn = _in_memory_conn()
        self.assertEqual(get_trash_tasks(conn=conn), [])
        conn.close()


# =====================================================================
#  DASHBOARD
# =====================================================================

class TestDashboardStats(unittest.TestCase):
    def test_empty_database(self) -> None:
        conn = _in_memory_conn()
        stats = get_dashboard_stats(conn=conn)
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["completed"], 0)
        self.assertEqual(stats["pending"], 0)
        self.assertEqual(stats["due_today"], 0)
        self.assertEqual(stats["overdue"], 0)
        self.assertEqual(stats["by_category"], {})
        self.assertEqual(stats["by_priority"], {})
        conn.close()

    def test_counts(self) -> None:
        conn = _in_memory_conn()
        add_task("P1", priority="LOW", conn=conn)
        add_task("P2", priority="HIGH", conn=conn)
        add_task("C1", status="COMPLETED", conn=conn)
        stats = get_dashboard_stats(conn=conn)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["pending"], 2)
        conn.close()

    def test_by_priority(self) -> None:
        conn = _in_memory_conn()
        add_task("L", priority="LOW", conn=conn)
        add_task("M", priority="MEDIUM", conn=conn)
        add_task("H", priority="HIGH", conn=conn)
        add_task("H2", priority="HIGH", conn=conn)
        stats = get_dashboard_stats(conn=conn)
        self.assertEqual(stats["by_priority"], {"LOW": 1, "MEDIUM": 1, "HIGH": 2})
        conn.close()

    def test_by_category(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("Work", conn=conn)
        add_task("A", category_id=cat_id, conn=conn)
        add_task("B", category_id=cat_id, conn=conn)
        add_task("C", conn=conn)
        stats = get_dashboard_stats(conn=conn)
        self.assertEqual(stats["by_category"]["Work"], 2)
        self.assertEqual(stats["by_category"]["Uncategorized"], 1)
        conn.close()

    def test_due_today(self) -> None:
        conn = _in_memory_conn()
        today = date.today().isoformat()
        add_task("Today", due_date=today, conn=conn)
        add_task("Future", due_date="2099-01-01", conn=conn)
        stats = get_dashboard_stats(conn=conn)
        self.assertEqual(stats["due_today"], 1)
        conn.close()

    def test_overdue(self) -> None:
        conn = _in_memory_conn()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        add_task("Late", due_date=yesterday, conn=conn)
        add_task("Future", due_date="2099-01-01", conn=conn)
        stats = get_dashboard_stats(conn=conn)
        self.assertEqual(stats["overdue"], 1)
        conn.close()

    def test_completed_not_counted_as_overdue(self) -> None:
        conn = _in_memory_conn()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        add_task("Done", due_date=yesterday, status="COMPLETED", conn=conn)
        stats = get_dashboard_stats(conn=conn)
        self.assertEqual(stats["overdue"], 0)
        self.assertEqual(stats["completed"], 1)
        conn.close()

    def test_deleted_tasks_excluded(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("Gone", conn=conn)
        soft_delete_task(tid, conn=conn)
        stats = get_dashboard_stats(conn=conn)
        self.assertEqual(stats["total"], 0)
        conn.close()


# =====================================================================
#  NOTIFICATION QUERIES
# =====================================================================

class TestDueTodayTasks(unittest.TestCase):
    def test_returns_due_today_pending(self) -> None:
        conn = _in_memory_conn()
        today = date.today().isoformat()
        tid = add_task("Due today", due_date=today, conn=conn)
        result = get_due_today_tasks(conn=conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], tid)
        conn.close()

    def test_excludes_completed(self) -> None:
        conn = _in_memory_conn()
        today = date.today().isoformat()
        add_task("Done", due_date=today, status="COMPLETED", conn=conn)
        self.assertEqual(get_due_today_tasks(conn=conn), [])
        conn.close()

    def test_excludes_future(self) -> None:
        conn = _in_memory_conn()
        add_task("Future", due_date="2099-01-01", conn=conn)
        self.assertEqual(get_due_today_tasks(conn=conn), [])
        conn.close()


class TestOverdueTasks(unittest.TestCase):
    def test_returns_overdue_pending(self) -> None:
        conn = _in_memory_conn()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tid = add_task("Late", due_date=yesterday, conn=conn)
        result = get_overdue_tasks(conn=conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], tid)
        conn.close()

    def test_excludes_today(self) -> None:
        conn = _in_memory_conn()
        today = date.today().isoformat()
        add_task("Today", due_date=today, conn=conn)
        self.assertEqual(get_overdue_tasks(conn=conn), [])
        conn.close()

    def test_excludes_completed(self) -> None:
        conn = _in_memory_conn()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        add_task("Done", due_date=yesterday, status="COMPLETED", conn=conn)
        self.assertEqual(get_overdue_tasks(conn=conn), [])
        conn.close()

    def test_excludes_no_due_date(self) -> None:
        conn = _in_memory_conn()
        add_task("No date", conn=conn)
        self.assertEqual(get_overdue_tasks(conn=conn), [])
        conn.close()


# =====================================================================
#  CSV EXPORT / IMPORT
# =====================================================================

class TestCSVExport(unittest.TestCase):
    def test_export_creates_file(self) -> None:
        conn = _in_memory_conn()
        add_task("T1", conn=conn)
        add_task("T2", priority="LOW", conn=conn)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            count = export_tasks_to_csv(path, conn=conn)
            self.assertEqual(count, 2)
            with open(path, encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = next(reader)
                rows = list(reader)
            self.assertEqual(len(header), 8)
            self.assertEqual(len(rows), 2)
        finally:
            os.unlink(path)
        conn.close()

    def test_export_empty(self) -> None:
        conn = _in_memory_conn()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            count = export_tasks_to_csv(path, conn=conn)
            self.assertEqual(count, 0)
            with open(path, encoding="utf-8") as fh:
                reader = csv.reader(fh)
                next(reader)
                self.assertEqual(list(reader), [])
        finally:
            os.unlink(path)
        conn.close()


class TestCSVImport(unittest.TestCase):
    def _write_csv(self, rows: list[list[str]], path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "title", "description", "priority", "category_id",
                "due_date", "status", "created_at", "completed_at",
            ])
            for row in rows:
                writer.writerow(row)

    def test_import_valid(self) -> None:
        conn = _in_memory_conn()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            self._write_csv([
                ["Task1", "desc", "LOW", "", "2026-06-01", "PENDING", "2026-01-01T00:00:00", ""],
                ["Task2", "", "HIGH", "", "", "COMPLETED", "2026-01-02T00:00:00", "2026-01-03T00:00:00"],
            ], path)
            imported, errors = import_tasks_from_csv(path, conn=conn)
            self.assertEqual(imported, 2)
            self.assertEqual(errors, [])
            tasks = get_active_tasks(conn=conn)
            self.assertEqual(len(tasks), 2)
        finally:
            os.unlink(path)
        conn.close()

    def test_import_skips_bad_rows(self) -> None:
        conn = _in_memory_conn()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            self._write_csv([
                ["Good", "desc", "MEDIUM", "", "2026-01-01", "PENDING", "2026-01-01T00:00:00", ""],
                ["", "desc", "MEDIUM", "", "2026-01-01", "PENDING", "2026-01-01T00:00:00", ""],
                ["Bad", "desc", "URGENT", "", "2026-01-01", "PENDING", "2026-01-01T00:00:00", ""],
                ["AlsoBad", "", "LOW", "", "not-a-date", "PENDING", "2026-01-01T00:00:00", ""],
            ], path)
            imported, errors = import_tasks_from_csv(path, conn=conn)
            self.assertEqual(imported, 1)
            self.assertEqual(len(errors), 3)
            tasks = get_active_tasks(conn=conn)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["title"], "Good")
        finally:
            os.unlink(path)
        conn.close()

    def test_import_empty_file(self) -> None:
        conn = _in_memory_conn()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            imported, errors = import_tasks_from_csv(path, conn=conn)
            self.assertEqual(imported, 0)
            self.assertTrue(len(errors) > 0)
        finally:
            os.unlink(path)
        conn.close()

    def test_import_missing_file(self) -> None:
        conn = _in_memory_conn()
        imported, errors = import_tasks_from_csv("nonexistent.csv", conn=conn)
        self.assertEqual(imported, 0)
        self.assertTrue(len(errors) > 0)
        conn.close()

    def test_import_bad_header(self) -> None:
        conn = _in_memory_conn()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("col1,col2,col3\n")
                fh.write("a,b,c\n")
            imported, errors = import_tasks_from_csv(path, conn=conn)
            self.assertEqual(imported, 0)
            self.assertTrue(len(errors) > 0)
        finally:
            os.unlink(path)
        conn.close()


# =====================================================================
#  BACKUP / RESTORE
# =====================================================================

class TestBackupRestore(unittest.TestCase):
    def _make_real_db(self, path: str) -> None:
        """Create a file-based DB at *path* with schema, seed, and a task."""
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        initialize_database(conn)
        seed_default_user(conn)
        add_task("BackupMe", conn=conn)
        conn.close()

    def test_backup_creates_file(self) -> None:
        import task_manager.database as db_mod

        test_fn = "tasks_test_bk_file.db"
        tm_dir = os.path.dirname(db_mod.__file__)
        db_path = os.path.join(tm_dir, test_fn)
        backup_path = db_path + ".bak_test"

        old_fn = db_mod._DB_FILENAME
        try:
            self._make_real_db(db_path)
            db_mod._DB_FILENAME = test_fn
            backup_database(backup_path)
            self.assertTrue(os.path.exists(backup_path))
            # Verify the backup is a valid SQLite DB
            bk = sqlite3.connect(backup_path)
            row = bk.execute("SELECT COUNT(*) FROM tasks").fetchone()
            self.assertEqual(row[0], 1)
            bk.close()
        finally:
            db_mod._DB_FILENAME = old_fn
            if os.path.exists(db_path):
                os.unlink(db_path)
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_restore_replaces_database(self) -> None:
        import task_manager.database as db_mod

        test_fn = "tasks_test_restore_file.db"
        tm_dir = os.path.dirname(db_mod.__file__)
        db_path = os.path.join(tm_dir, test_fn)
        backup_path = db_path + ".bak_test2"

        old_fn = db_mod._DB_FILENAME
        try:
            # Create original DB with 1 task
            self._make_real_db(db_path)
            db_mod._DB_FILENAME = test_fn

            # Backup it
            backup_database(backup_path)

            # Modify original: add another task
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            add_task("Extra", conn=conn)
            conn.close()

            # Verify original has 2 tasks
            conn = sqlite3.connect(db_path)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 2)
            conn.close()

            # Restore from backup (should revert to 1 task)
            restore_database(backup_path)

            conn = sqlite3.connect(db_path)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)
            conn.close()
        finally:
            db_mod._DB_FILENAME = old_fn
            if os.path.exists(db_path):
                os.unlink(db_path)
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_backup_nonexistent_raises(self) -> None:
        import task_manager.database as db_mod

        old_fn = db_mod._DB_FILENAME
        db_mod._DB_FILENAME = "nonexistent_db_xyz.db"
        try:
            with self.assertRaises(FileNotFoundError):
                backup_database("/tmp/no_such_file.bak")
        finally:
            db_mod._DB_FILENAME = old_fn

    def test_restore_nonexistent_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            restore_database("/tmp/no_such_backup_xyz.db")


# =====================================================================
#  EDGE CASES
# =====================================================================

class TestEdgeCases(unittest.TestCase):
    def test_add_task_whitespace_title_stripped(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("  Hello  ", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["title"], "Hello")
        conn.close()

    def test_priority_case_insensitive(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", priority="low", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["priority"], "LOW")
        conn.close()

    def test_status_case_insensitive(self) -> None:
        conn = _in_memory_conn()
        tid = add_task("T", status="completed", conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertEqual(task["status"], "COMPLETED")
        conn.close()

    def test_category_fk_set_null_on_delete(self) -> None:
        conn = _in_memory_conn()
        cat_id = add_category("Temp", conn=conn)
        tid = add_task("T", category_id=cat_id, conn=conn)
        delete_category(cat_id, conn=conn)
        task = get_task_by_id(tid, conn=conn)
        self.assertIsNone(task["category_id"])
        conn.close()

    def test_search_case_insensitive_keyword(self) -> None:
        conn = _in_memory_conn()
        add_task("Hello World", conn=conn)
        result = search_tasks(keyword="hello", conn=conn)
        self.assertEqual(len(result), 1)
        conn.close()

    def test_get_task_nonexistent(self) -> None:
        conn = _in_memory_conn()
        self.assertIsNone(get_task_by_id(9999, conn=conn))
        conn.close()


if __name__ == "__main__":
    unittest.main()
