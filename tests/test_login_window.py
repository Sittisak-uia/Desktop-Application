"""Unit tests for task_manager.ui.login_window.

Uses the standard library unittest only -- no pytest dependency.
Creates a QApplication in offscreen mode for headless GUI testing.
Authentication is tested against a temporary SQLite database so the
production tasks.db is never touched.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLineEdit

from task_manager.database import initialize_database, seed_default_user
from task_manager.ui.login_window import LoginWindow

# Ensure a QApplication exists (required by PyQt6 before any widget work)
_app = QApplication.instance() or QApplication(sys.argv)


def _make_temp_db() -> tuple[str, sqlite3.Connection]:
    """Create a temp DB with schema and default admin user."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    seed_default_user(conn)
    return path, conn


class TestLoginWindowWidgets(unittest.TestCase):
    """Verify that all expected widgets exist with correct properties."""

    def setUp(self) -> None:
        self.win = LoginWindow()
        self.win.show()

    def tearDown(self) -> None:
        self.win.close()
        self.win.deleteLater()

    def test_can_be_instantiated(self) -> None:
        self.assertIsInstance(self.win, LoginWindow)

    def test_username_field_exists(self) -> None:
        self.assertIsNotNone(self.win.username_input)
        self.assertIsInstance(self.win.username_input, QLineEdit)

    def test_password_field_exists(self) -> None:
        self.assertIsNotNone(self.win.password_input)
        self.assertIsInstance(self.win.password_input, QLineEdit)

    def test_password_field_echo_mode(self) -> None:
        self.assertEqual(
            self.win.password_input.echoMode(),
            QLineEdit.EchoMode.Password,
        )

    def test_login_button_exists(self) -> None:
        self.assertIsNotNone(self.win.login_button)
        self.assertEqual(self.win.login_button.text(), "Login")

    def test_error_label_hidden_by_default(self) -> None:
        self.assertFalse(self.win.error_label.isVisible())
        self.assertEqual(self.win.error_label.text(), "")

    def test_is_authenticated_false_initially(self) -> None:
        self.assertFalse(self.win.is_authenticated)

    def test_title_contains_task_manager(self) -> None:
        self.assertIn("Task Manager", self.win.windowTitle())


class TestLoginWindowEmptyCredentials(unittest.TestCase):
    """Verify that empty username/password are rejected."""

    def setUp(self) -> None:
        self.win = LoginWindow()
        self.win.show()

    def tearDown(self) -> None:
        self.win.close()
        self.win.deleteLater()

    def test_empty_both_fields(self) -> None:
        self.win.username_input.setText("")
        self.win.password_input.setText("")
        self.win.login_button.click()
        self.assertTrue(self.win.error_label.isVisible())
        self.assertIn("enter both", self.win.error_label.text().lower())
        self.assertFalse(self.win.is_authenticated)

    def test_empty_username_only(self) -> None:
        self.win.username_input.setText("")
        self.win.password_input.setText("admin")
        self.win.login_button.click()
        self.assertTrue(self.win.error_label.isVisible())
        self.assertFalse(self.win.is_authenticated)

    def test_empty_password_only(self) -> None:
        self.win.username_input.setText("admin")
        self.win.password_input.setText("")
        self.win.login_button.click()
        self.assertTrue(self.win.error_label.isVisible())
        self.assertFalse(self.win.is_authenticated)


class TestLoginWindowInvalidCredentials(unittest.TestCase):
    """Verify that wrong credentials are rejected (against a temp DB)."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.win = LoginWindow()
        self.win.show()
        self._patcher = patch(
            "task_manager.ui.login_window.authenticate_user",
            side_effect=lambda u, p: _authenticate_against(u, p, self.conn),
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.win.close()
        self.win.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_wrong_password(self) -> None:
        self.win.username_input.setText("admin")
        self.win.password_input.setText("wrong")
        self.win.login_button.click()
        self.assertTrue(self.win.error_label.isVisible())
        self.assertIn("invalid", self.win.error_label.text().lower())
        self.assertFalse(self.win.is_authenticated)

    def test_unknown_user(self) -> None:
        self.win.username_input.setText("nobody")
        self.win.password_input.setText("admin")
        self.win.login_button.click()
        self.assertTrue(self.win.error_label.isVisible())
        self.assertFalse(self.win.is_authenticated)


class TestLoginWindowValidCredentials(unittest.TestCase):
    """Verify that correct credentials are accepted (against a temp DB)."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.win = LoginWindow()
        self.win.show()
        self._patcher = patch(
            "task_manager.ui.login_window.authenticate_user",
            side_effect=lambda u, p: _authenticate_against(u, p, self.conn),
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.win.close()
        self.win.deleteLater()
        self.conn.close()
        os.unlink(self.db_path)

    def test_valid_credentials(self) -> None:
        self.win.username_input.setText("admin")
        self.win.password_input.setText("admin")
        self.win.login_button.click()
        self.assertTrue(self.win.is_authenticated)


class TestLoginWindowEnterKey(unittest.TestCase):
    """Verify that pressing Enter triggers login."""

    def setUp(self) -> None:
        self.win = LoginWindow()
        self.win.show()

    def tearDown(self) -> None:
        self.win.close()
        self.win.deleteLater()

    def test_enter_in_password_triggers_login(self) -> None:
        self.win.username_input.setText("")
        self.win.password_input.setText("")
        self.win.password_input.returnPressed.emit()
        self.assertTrue(self.win.error_label.isVisible())

    def test_enter_in_username_moves_focus_to_password(self) -> None:
        self.win.username_input.setText("admin")
        self.win.username_input.returnPressed.emit()
        self.assertTrue(self.win.password_input.hasFocus())


# ------------------------------------------------------------------
# Helper used by tests that need a real DB-backed authenticate
# ------------------------------------------------------------------

def _authenticate_against(username: str, password: str, conn: sqlite3.Connection) -> bool:
    """Thin wrapper that calls auth.authenticate_user with a specific conn."""
    from task_manager.auth import authenticate_user
    return authenticate_user(username, password, conn=conn)


if __name__ == "__main__":
    unittest.main()
