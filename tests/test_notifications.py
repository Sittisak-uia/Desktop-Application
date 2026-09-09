"""Unit tests for task due-date and overdue notifications in SQLite Task Manager PRO.

Phase 12 requirements:
- Overdue definition: status = PENDING, due_date is not NULL/empty, due_date < today, is_deleted = 0.
- Completed tasks must NOT be reported as overdue.
- Tasks without a due date must NOT be reported as overdue.
- Deleted tasks in Trash must NOT generate overdue notifications.
- Multiple overdue tasks are counted correctly.
- Notification UI can be instantiated.
- Notification is readable in Light mode and Dark mode.
- Anti-spam: repeated refresh does not create uncontrolled notification spam.
- View Tasks button navigates to the tasks page.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from task_manager.database import (
    add_task,
    get_overdue_tasks,
    initialize_database,
    seed_default_user,
    soft_delete_task,
    update_task,
)
from task_manager.ui.main_window import MainWindow
from task_manager.ui.notifications import NotificationBanner
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


def _today() -> str:
    return date.today().isoformat()


def _yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _past_days(days: int = 5) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _future_days(days: int = 5) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# =========================================================================
#  1. Database / Overdue Logic Tests
# =========================================================================

class TestOverdueDatabaseLogic(unittest.TestCase):
    """Test overdue calculation rules in database query."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()

    def tearDown(self) -> None:
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_pending_task_with_past_due_date_is_overdue(self) -> None:
        """Pending task with past due date is detected as overdue."""
        task_id = add_task("Overdue Task", status="PENDING", due_date=_yesterday(), conn=self.conn)
        overdue = get_overdue_tasks(conn=self.conn)
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0]["id"], task_id)
        self.assertEqual(overdue[0]["title"], "Overdue Task")

    def test_pending_task_with_today_due_date_not_overdue(self) -> None:
        """Pending task with today's due date is NOT overdue."""
        add_task("Due Today Task", status="PENDING", due_date=_today(), conn=self.conn)
        overdue = get_overdue_tasks(conn=self.conn)
        self.assertEqual(len(overdue), 0)

    def test_pending_task_with_future_due_date_not_overdue(self) -> None:
        """Pending task with future due date is NOT overdue."""
        add_task("Future Task", status="PENDING", due_date=_future_days(3), conn=self.conn)
        overdue = get_overdue_tasks(conn=self.conn)
        self.assertEqual(len(overdue), 0)

    def test_completed_task_with_past_due_date_not_overdue(self) -> None:
        """Completed task with past due date is NOT reported as overdue."""
        add_task("Done Task", status="COMPLETED", due_date=_past_days(10), conn=self.conn)
        overdue = get_overdue_tasks(conn=self.conn)
        self.assertEqual(len(overdue), 0)

    def test_task_without_due_date_not_overdue(self) -> None:
        """Tasks without due date (None or empty string) are NOT reported as overdue."""
        add_task("No Due Date None", status="PENDING", due_date=None, conn=self.conn)
        add_task("No Due Date Empty", status="PENDING", due_date="", conn=self.conn)
        overdue = get_overdue_tasks(conn=self.conn)
        self.assertEqual(len(overdue), 0)

    def test_deleted_task_is_not_overdue(self) -> None:
        """Deleted task in Trash is NOT reported as overdue."""
        task_id = add_task("Deleted Overdue", status="PENDING", due_date=_past_days(2), conn=self.conn)
        soft_delete_task(task_id, conn=self.conn)
        overdue = get_overdue_tasks(conn=self.conn)
        self.assertEqual(len(overdue), 0)

    def test_multiple_overdue_tasks_counted_correctly(self) -> None:
        """Multiple overdue tasks are counted correctly while excluding non-overdue tasks."""
        add_task("Overdue 1", status="PENDING", due_date=_past_days(1), conn=self.conn)
        add_task("Overdue 2", status="PENDING", due_date=_past_days(3), conn=self.conn)
        add_task("Overdue 3", status="PENDING", due_date=_past_days(7), conn=self.conn)
        add_task("Normal Future", status="PENDING", due_date=_future_days(2), conn=self.conn)
        add_task("Completed Past", status="COMPLETED", due_date=_past_days(4), conn=self.conn)
        add_task("No Due", status="PENDING", due_date=None, conn=self.conn)

        overdue = get_overdue_tasks(conn=self.conn)
        self.assertEqual(len(overdue), 3)
        titles = {t["title"] for t in overdue}
        self.assertEqual(titles, {"Overdue 1", "Overdue 2", "Overdue 3"})


# =========================================================================
#  2. Notification Banner UI & Anti-Spam Tests
# =========================================================================

class TestNotificationBannerUI(unittest.TestCase):
    """Test NotificationBanner behavior, dismissal, and anti-spam protection."""

    def setUp(self) -> None:
        self.on_view_mock = MagicMock()
        self.banner = NotificationBanner(on_view_tasks=self.on_view_mock)
        self.banner.show()

    def tearDown(self) -> None:
        self.banner.close()
        self.banner.deleteLater()

    def test_notification_ui_can_be_instantiated(self) -> None:
        """Banner widget can be instantiated properly and components exist."""
        self.assertIsInstance(self.banner, NotificationBanner)
        self.assertIsNotNone(self.banner.message_label)
        self.assertIsNotNone(self.banner.view_btn)
        self.assertIsNotNone(self.banner.dismiss_btn)

    def test_single_overdue_task_displays_title(self) -> None:
        """Single overdue task clearly shows its title in the message."""
        tasks = [{"id": 1, "title": "Submit Tax Report"}]
        shown = self.banner.check_and_notify(tasks)
        self.assertTrue(shown)
        self.assertFalse(self.banner.isHidden())
        msg = self.banner.message_label.text()
        self.assertIn("1 task is overdue", msg)
        self.assertIn("Submit Tax Report", msg)

    def test_two_to_three_overdue_tasks_display_all_titles(self) -> None:
        """2 to 3 overdue tasks display their titles in the banner."""
        tasks = [
            {"id": 1, "title": "Task One"},
            {"id": 2, "title": "Task Two"},
        ]
        self.banner.check_and_notify(tasks)
        msg = self.banner.message_label.text()
        self.assertIn("2 tasks are overdue", msg)
        self.assertIn("Task One", msg)
        self.assertIn("Task Two", msg)

    def test_more_than_three_overdue_tasks_summary_format(self) -> None:
        """More than 3 overdue tasks display the first 3 titles plus count of remainder."""
        tasks = [
            {"id": 1, "title": "Task 1"},
            {"id": 2, "title": "Task 2"},
            {"id": 3, "title": "Task 3"},
            {"id": 4, "title": "Task 4"},
            {"id": 5, "title": "Task 5"},
        ]
        self.banner.check_and_notify(tasks)
        msg = self.banner.message_label.text()
        self.assertIn("5 tasks are overdue", msg)
        self.assertIn("Task 1", msg)
        self.assertIn("Task 2", msg)
        self.assertIn("Task 3", msg)
        self.assertIn("and 2 more", msg)

    def test_view_tasks_button_invokes_callback(self) -> None:
        """Clicking 'View Tasks' triggers the provided navigation callback."""
        self.banner.check_and_notify([{"id": 1, "title": "Fix Bug"}])
        self.banner.view_btn.click()
        self.on_view_mock.assert_called_once()

    def test_dismiss_button_hides_banner(self) -> None:
        """Clicking dismiss button hides banner and marks it as dismissed."""
        self.banner.check_and_notify([{"id": 1, "title": "Fix Bug"}])
        self.assertFalse(self.banner.isHidden())
        self.banner.dismiss_btn.click()
        self.assertTrue(self.banner.isHidden())
        self.assertTrue(self.banner.is_dismissed())

    def test_repeated_refresh_does_not_create_notification_spam(self) -> None:
        """Once dismissed, repeated checks with the same overdue tasks do not re-show the banner."""
        tasks = [{"id": 1, "title": "Fix Bug"}]
        self.banner.check_and_notify(tasks)
        self.banner.dismiss()
        self.assertTrue(self.banner.isHidden())

        # Simulate 5 page refreshes with the same unchanged overdue data
        for _ in range(5):
            shown = self.banner.check_and_notify(tasks)
            self.assertFalse(shown)
            self.assertTrue(self.banner.isHidden())

    def test_relevant_task_data_change_resets_dismissed_and_notifies(self) -> None:
        """If new overdue tasks appear, the banner re-alerts even if previously dismissed."""
        tasks1 = [{"id": 1, "title": "Fix Bug"}]
        self.banner.check_and_notify(tasks1)
        self.banner.dismiss()
        self.assertTrue(self.banner.isHidden())

        # A new task became overdue
        tasks2 = [{"id": 1, "title": "Fix Bug"}, {"id": 2, "title": "Update Docs"}]
        shown = self.banner.check_and_notify(tasks2)
        self.assertTrue(shown)
        self.assertFalse(self.banner.isHidden())
        self.assertFalse(self.banner.is_dismissed())
        self.assertIn("2 tasks are overdue", self.banner.message_label.text())

    def test_empty_overdue_tasks_hides_banner(self) -> None:
        """When all overdue tasks are completed or deleted, banner is automatically hidden."""
        tasks = [{"id": 1, "title": "Urgent"}]
        self.banner.check_and_notify(tasks)
        self.assertFalse(self.banner.isHidden())

        # Overdue tasks cleared
        shown = self.banner.check_and_notify([])
        self.assertFalse(shown)
        self.assertTrue(self.banner.isHidden())


# =========================================================================
#  3. Light and Dark Theme Readability Tests
# =========================================================================

class TestNotificationThemeReadability(unittest.TestCase):
    """Verify Light and Dark theme readability and styles."""

    def setUp(self) -> None:
        self.banner = NotificationBanner()

    def tearDown(self) -> None:
        self.banner.close()
        self.banner.deleteLater()

    def test_notification_readable_in_light_mode(self) -> None:
        """Light mode banner uses amber warning background with high-contrast dark text."""
        self.banner.apply_theme(THEME_LIGHT)
        style = self.banner.styleSheet()
        self.assertIn("#fff3cd", style)
        self.assertIn("#856404", style)
        self.assertIn("#f0ad4e", style)

    def test_notification_readable_in_dark_mode(self) -> None:
        """Dark mode banner uses dark contrast background with readable light-golden text."""
        self.banner.apply_theme(THEME_DARK)
        style = self.banner.styleSheet()
        self.assertIn("#3a2a18", style)
        self.assertIn("#ffe8a1", style)
        self.assertIn("#d58512", style)


# =========================================================================
#  4. MainWindow Integration Tests
# =========================================================================

class TestMainWindowNotificationIntegration(unittest.TestCase):
    """Test MainWindow integration with overdue notification checks."""

    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()
        self.patchers = [
            patch(
                "task_manager.database.get_connection",
                side_effect=lambda: _connect_db(self.db_path),
            ),
            patch("PyQt6.QtWidgets.QMessageBox.critical"),
            patch("PyQt6.QtWidgets.QMessageBox.warning"),
            patch("PyQt6.QtWidgets.QMessageBox.information"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self) -> None:
        for p in self.patchers:
            p.stop()
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_main_window_displays_banner_on_startup_when_overdue(self) -> None:
        """MainWindow automatically displays notification banner on startup if overdue tasks exist."""
        add_task("Past Task", status="PENDING", due_date=_past_days(3), conn=self.conn)

        win = MainWindow()
        try:
            self.assertIsNotNone(win.notification_banner)
            self.assertFalse(win.notification_banner.isHidden())
            self.assertIn("1 task is overdue", win.notification_banner.message_label.text())
        finally:
            win.close()
            win.deleteLater()

    def test_main_window_banner_view_tasks_navigates_to_tasks_page(self) -> None:
        """Clicking 'View Tasks' in MainWindow banner navigates to Tasks page (index 1)."""
        add_task("Past Task", status="PENDING", due_date=_past_days(3), conn=self.conn)

        win = MainWindow()
        try:
            self.assertEqual(win._stack.currentIndex(), 0)  # Starts on Dashboard
            win.notification_banner.view_btn.click()
            self.assertEqual(win._stack.currentIndex(), 1)  # Switched to Tasks
        finally:
            win.close()
            win.deleteLater()

    def test_main_window_apply_theme_updates_banner(self) -> None:
        """Applying theme to MainWindow propagates to notification banner."""
        win = MainWindow()
        try:
            win.apply_theme(THEME_DARK)
            self.assertIn("#3a2a18", win.notification_banner.styleSheet())
            win.apply_theme(THEME_LIGHT)
            self.assertIn("#fff3cd", win.notification_banner.styleSheet())
        finally:
            win.close()
            win.deleteLater()


if __name__ == "__main__":
    unittest.main()
