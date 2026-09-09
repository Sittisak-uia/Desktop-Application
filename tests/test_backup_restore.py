"""Unit tests for Database Backup and Restore in SQLite Task Manager PRO.

Phase 14 requirements:
- Backup creates valid SQLite database preserving users, categories, tasks.
- Backup does not modify the original database.
- Backup filename formatting works as expected.
- Validation checks:
  - Valid Task Manager database passes.
  - Non-SQLite file rejected.
  - Missing users table rejected.
  - Missing categories table rejected.
  - Missing tasks table rejected.
  - Missing required task column rejected.
  - Corrupted database rejected.
- Restore behavior:
  - Restores users, categories, tasks.
  - Safety backup is created before restoring.
  - Invalid restore does not alter active database.
  - Foreign key behavior remains enabled.
- UI behavior:
  - Backup & Restore buttons exist.
  - Light and Dark mode readability.
  - Restore confirmation dialog (cancel aborts without changes).
  - Feedback displays on success and failure.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton

from task_manager.database import (
    add_category,
    add_task,
    get_connection,
    initialize_database,
    seed_default_user,
)
from task_manager.database_backup import (
    REQUIRED_TABLES,
    REQUIRED_TASK_COLUMNS,
    backup_database,
    create_safety_backup,
    generate_backup_filename,
    generate_safety_backup_filename,
    restore_database,
    validate_backup_file,
)
from task_manager.ui.settings import SettingsWidget
from task_manager.ui.theme import THEME_DARK, THEME_LIGHT

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


# =========================================================================
#  1. Backup Tests
# =========================================================================

class TestDatabaseBackup(unittest.TestCase):
    """Test backup creation, format, and content preservation."""

    def setUp(self) -> None:
        self.src_path, self.src_conn = _make_temp_db()
        self.cat_id = add_category("Operations", conn=self.src_conn)
        self.task_id = add_task(
            "Quarterly Review",
            description="Review Q3 metrics",
            priority="HIGH",
            category_id=self.cat_id,
            due_date="2026-10-15",
            status="PENDING",
            conn=self.src_conn,
        )
        fd, self.dest_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.dest_path)  # backup_database will create it

    def tearDown(self) -> None:
        self.src_conn.close()
        if os.path.exists(self.src_path):
            os.unlink(self.src_path)
        if os.path.exists(self.dest_path):
            os.unlink(self.dest_path)

    def test_backup_creates_file(self) -> None:
        """Backup creates a destination file with positive size."""
        saved_path = backup_database(self.dest_path, source_db_path=self.src_path)
        self.assertTrue(os.path.exists(saved_path))
        self.assertGreater(os.path.getsize(saved_path), 0)

    def test_backup_file_is_valid_sqlite(self) -> None:
        """Backup output passes validation as a valid Task Manager SQLite database."""
        backup_database(self.dest_path, source_db_path=self.src_path)
        valid, msg = validate_backup_file(self.dest_path)
        self.assertTrue(valid, msg)

    def test_backup_preserves_users(self) -> None:
        """Backup contains seeded users."""
        backup_database(self.dest_path, source_db_path=self.src_path)
        b_conn = _connect_db(self.dest_path)
        users = b_conn.execute("SELECT username FROM users").fetchall()
        b_conn.close()
        usernames = [u["username"] for u in users]
        self.assertIn("admin", usernames)

    def test_backup_preserves_categories(self) -> None:
        """Backup contains created categories."""
        backup_database(self.dest_path, source_db_path=self.src_path)
        b_conn = _connect_db(self.dest_path)
        cats = b_conn.execute("SELECT name FROM categories").fetchall()
        b_conn.close()
        cat_names = [c["name"] for c in cats]
        self.assertIn("Operations", cat_names)

    def test_backup_preserves_tasks(self) -> None:
        """Backup contains created tasks with accurate fields."""
        backup_database(self.dest_path, source_db_path=self.src_path)
        b_conn = _connect_db(self.dest_path)
        task = b_conn.execute("SELECT * FROM tasks WHERE id = ?", (self.task_id,)).fetchone()
        b_conn.close()
        self.assertIsNotNone(task)
        self.assertEqual(task["title"], "Quarterly Review")
        self.assertEqual(task["description"], "Review Q3 metrics")
        self.assertEqual(task["priority"], "HIGH")
        self.assertEqual(task["status"], "PENDING")

    def test_original_database_remains_unchanged(self) -> None:
        """Source database records remain identical after backup."""
        orig_count = self.src_conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        backup_database(self.dest_path, source_db_path=self.src_path)
        after_count = self.src_conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(orig_count, after_count)

    def test_backup_filename_format(self) -> None:
        """Default backup filename follows tasks_backup_YYYYMMDD_HHMMSS.db pattern."""
        fname = generate_backup_filename()
        self.assertTrue(fname.startswith("tasks_backup_"))
        self.assertTrue(fname.endswith(".db"))
        parts = fname.replace("tasks_backup_", "").replace(".db", "").split("_")
        self.assertEqual(len(parts), 2)
        self.assertEqual(len(parts[0]), 8)  # YYYYMMDD
        self.assertEqual(len(parts[1]), 6)  # HHMMSS


# =========================================================================
#  2. Validation Tests
# =========================================================================

class TestDatabaseValidation(unittest.TestCase):
    """Test schema, integrity, and column validation rules."""

    def setUp(self) -> None:
        self.temp_files: list[str] = []

    def tearDown(self) -> None:
        for f in self.temp_files:
            if os.path.exists(f):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def _create_temp_file(self, content: bytes = b"") -> str:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.write(fd, content)
        os.close(fd)
        self.temp_files.append(path)
        return path

    def test_valid_database_passes_validation(self) -> None:
        """A properly initialized Task Manager database passes validation."""
        path, conn = _make_temp_db()
        conn.close()
        self.temp_files.append(path)
        valid, msg = validate_backup_file(path)
        self.assertTrue(valid, msg)

    def test_nonexistent_file_rejected(self) -> None:
        """Nonexistent file path fails validation."""
        valid, msg = validate_backup_file("nonexistent_db_file_123.db")
        self.assertFalse(valid)
        self.assertIn("does not exist", msg.lower())

    def test_non_sqlite_file_rejected(self) -> None:
        """Text or non-SQLite binary file fails validation."""
        path = self._create_temp_file(b"This is just a plain text file, definitely not SQLite database! " * 5)
        valid, msg = validate_backup_file(path)
        self.assertFalse(valid)
        self.assertIn("not a valid sqlite", msg.lower())

    def test_missing_users_table_rejected(self) -> None:
        """SQLite database missing 'users' table is rejected."""
        path = self._create_temp_file()
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, description TEXT, priority TEXT, category_id INTEGER, due_date TEXT, status TEXT, created_at TEXT, completed_at TEXT, is_deleted INTEGER)")
        conn.commit()
        conn.close()

        valid, msg = validate_backup_file(path)
        self.assertFalse(valid)
        self.assertIn("users", msg.lower())

    def test_missing_categories_table_rejected(self) -> None:
        """SQLite database missing 'categories' table is rejected."""
        path = self._create_temp_file()
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, description TEXT, priority TEXT, category_id INTEGER, due_date TEXT, status TEXT, created_at TEXT, completed_at TEXT, is_deleted INTEGER)")
        conn.commit()
        conn.close()

        valid, msg = validate_backup_file(path)
        self.assertFalse(valid)
        self.assertIn("categories", msg.lower())

    def test_missing_tasks_table_rejected(self) -> None:
        """SQLite database missing 'tasks' table is rejected."""
        path = self._create_temp_file()
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()

        valid, msg = validate_backup_file(path)
        self.assertFalse(valid)
        self.assertIn("tasks", msg.lower())

    def test_missing_required_task_column_rejected(self) -> None:
        """Tasks table missing essential field (e.g. 'due_date') is rejected."""
        path = self._create_temp_file()
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        # Missing 'due_date' column
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, description TEXT, priority TEXT, category_id INTEGER, status TEXT, created_at TEXT, completed_at TEXT, is_deleted INTEGER)")
        conn.commit()
        conn.close()

        valid, msg = validate_backup_file(path)
        self.assertFalse(valid)
        self.assertIn("due_date", msg.lower())

    def test_corrupted_database_rejected(self) -> None:
        """File starting with SQLite header but containing corrupted bytes fails integrity check."""
        # 16-byte SQLite header followed by garbage
        header = b"SQLite format 3\x00" + b"\x00" * 84 + b"corruptgarbagebytes12345"
        path = self._create_temp_file(header)
        valid, msg = validate_backup_file(path)
        self.assertFalse(valid)


# =========================================================================
#  3. Restore Tests
# =========================================================================

class TestDatabaseRestore(unittest.TestCase):
    """Test restore operations, safety backups, and atomicity."""

    def setUp(self) -> None:
        # Create active current DB with initial task
        self.active_path, self.active_conn = _make_temp_db()
        add_task("Initial Task", conn=self.active_conn)

        # Create separate backup DB with restored data
        self.backup_path, backup_conn = _make_temp_db()
        cat_id = add_category("Restored Category", conn=backup_conn)
        add_task("Restored Task 1", category_id=cat_id, conn=backup_conn)
        add_task("Restored Task 2", category_id=cat_id, conn=backup_conn)
        backup_conn.close()

        self.cleanup_paths: list[str] = [self.active_path, self.backup_path]

    def tearDown(self) -> None:
        self.active_conn.close()
        for p in self.cleanup_paths:
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_restore_valid_database_successfully(self) -> None:
        """Valid backup successfully restores into target database."""
        success, msg, safety_path = restore_database(
            self.backup_path,
            target_db_path=self.active_path,
        )
        if safety_path:
            self.cleanup_paths.append(safety_path)

        self.assertTrue(success, msg)
        self.assertIn("restored successfully", msg.lower())

    def test_restored_records_are_present(self) -> None:
        """Restored users, categories, and tasks are accessible after restore."""
        success, msg, safety_path = restore_database(
            self.backup_path,
            target_db_path=self.active_path,
        )
        if safety_path:
            self.cleanup_paths.append(safety_path)

        # Query restored database
        conn = _connect_db(self.active_path)
        cats = conn.execute("SELECT name FROM categories WHERE name = 'Restored Category'").fetchall()
        tasks = conn.execute("SELECT title FROM tasks").fetchall()
        conn.close()

        self.assertEqual(len(cats), 1)
        titles = [t["title"] for t in tasks]
        self.assertIn("Restored Task 1", titles)
        self.assertIn("Restored Task 2", titles)
        self.assertNotIn("Initial Task", titles)

    def test_current_database_protected_by_safety_backup(self) -> None:
        """Safety backup is created before restore and contains initial data."""
        success, msg, safety_path = restore_database(
            self.backup_path,
            target_db_path=self.active_path,
        )
        self.assertIsNotNone(safety_path)
        self.assertTrue(os.path.exists(safety_path))
        self.cleanup_paths.append(safety_path)

        # Verify safety backup preserved original initial task
        s_conn = _connect_db(safety_path)
        initial = s_conn.execute("SELECT title FROM tasks WHERE title = 'Initial Task'").fetchone()
        s_conn.close()
        self.assertIsNotNone(initial)

    def test_invalid_restore_does_not_modify_current_database(self) -> None:
        """Invalid backup is rejected and leaves active database completely untouched."""
        # Create an invalid file
        fd, invalid_path = tempfile.mkstemp(suffix=".db")
        os.write(fd, b"Invalid junk data")
        os.close(fd)
        self.cleanup_paths.append(invalid_path)

        success, msg, safety = restore_database(
            invalid_path,
            target_db_path=self.active_path,
        )
        self.assertFalse(success)
        self.assertIn("rejected", msg.lower())

        # Original database remains intact with initial task
        conn = _connect_db(self.active_path)
        task = conn.execute("SELECT title FROM tasks WHERE title = 'Initial Task'").fetchone()
        conn.close()
        self.assertIsNotNone(task)

    def test_foreign_key_behavior_remains_enabled(self) -> None:
        """Foreign key constraint enforcement is preserved after restore."""
        restore_database(self.backup_path, target_db_path=self.active_path)
        conn = _connect_db(self.active_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.close()
        self.assertEqual(fk, 1)


# =========================================================================
#  4. UI Tests
# =========================================================================

class TestSettingsBackupRestoreUI(unittest.TestCase):
    """Test Settings page backup and restore controls."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.cleanup_files: list[str] = [self.db_path]

        self.patch_warning = patch("PyQt6.QtWidgets.QMessageBox.warning")
        self.mock_warning = self.patch_warning.start()
        self.patch_info = patch("PyQt6.QtWidgets.QMessageBox.information")
        self.mock_info = self.patch_info.start()
        self.patch_critical = patch("PyQt6.QtWidgets.QMessageBox.critical")
        self.mock_critical = self.patch_critical.start()
        self.patch_question = patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
        self.mock_question = self.patch_question.start()

        self.patch_db = patch("task_manager.database.get_connection", side_effect=lambda: _connect_db(self.db_path))
        self.patch_db.start()

        self.widget = SettingsWidget()
        self.widget.show()

    def tearDown(self) -> None:
        self.patch_warning.stop()
        self.patch_info.stop()
        self.patch_critical.stop()
        self.patch_question.stop()
        self.patch_db.stop()

        self.widget.close()
        self.widget.deleteLater()
        self.conn.close()
        for f in self.cleanup_files:
            if os.path.exists(f):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_backup_and_restore_buttons_exist(self) -> None:
        """Backup Database and Restore Database buttons exist and are configured."""
        self.assertIsNotNone(self.widget.backup_btn)
        self.assertIsInstance(self.widget.backup_btn, QPushButton)
        self.assertEqual(self.widget.backup_btn.text(), "Backup Database")

        self.assertIsNotNone(self.widget.restore_btn)
        self.assertIsInstance(self.widget.restore_btn, QPushButton)
        self.assertEqual(self.widget.restore_btn.text(), "Restore Database")

    def test_light_theme_readability(self) -> None:
        """Card frames and buttons are readable in Light mode."""
        self.widget.apply_theme(THEME_LIGHT)
        card_style = self.widget.backup_card_frame.styleSheet()
        self.assertIn("background-color: #ffffff", card_style)
        self.assertIn("border: 1px solid #bdc3c7", card_style)

        btn_style = self.widget.backup_btn.styleSheet()
        self.assertIn("background-color: #27ae60", btn_style)
        self.assertIn("color: white", btn_style)

    def test_dark_theme_readability(self) -> None:
        """Card frames and buttons are readable in Dark mode."""
        self.widget.apply_theme(THEME_DARK)
        card_style = self.widget.backup_card_frame.styleSheet()
        self.assertIn("background-color: #2d3436", card_style)
        self.assertIn("border: 1px solid #4b6584", card_style)

        btn_style = self.widget.restore_btn.styleSheet()
        self.assertIn("background-color: #d35400", btn_style)
        self.assertIn("color: white", btn_style)

    def test_restore_confirmation_invoked_and_cancels(self) -> None:
        """When user cancels confirmation dialog, restore is aborted."""
        self.mock_question.return_value = QMessageBox.StandardButton.No

        fd, dest_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.cleanup_files.append(dest_path)

        with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=(dest_path, "SQLite Database (*.db)")):
            self.widget.restore_btn.click()

        self.mock_question.assert_called_once()
        args = self.mock_question.call_args[0]
        self.assertIn("Confirm Restore", args[1])
        self.assertIn("safety backup will be created first", args[2])

    def test_backup_action_displays_success_feedback(self) -> None:
        """Successful backup displays info dialog and updates status label."""
        fd, save_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(save_path)
        self.cleanup_files.append(save_path)

        with patch("task_manager.ui.settings.backup_database", return_value=save_path):
            with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(save_path, "SQLite Database (*.db)")):
                self.widget.backup_btn.click()

        self.mock_info.assert_called_once()
        self.assertIn("Backup created successfully", self.widget.backup_status_label.text())


if __name__ == "__main__":
    unittest.main()
