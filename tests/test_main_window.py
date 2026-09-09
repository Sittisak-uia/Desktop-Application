"""Unit tests for task_manager.ui.main_window.

Uses the standard library unittest only -- no pytest dependency.
Creates a QApplication in offscreen mode for headless GUI testing.
"""

import sys
import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QStackedWidget

from task_manager.ui.main_window import MainWindow

# Ensure a QApplication exists
_app = QApplication.instance() or QApplication(sys.argv)


class TestMainWindowStructure(unittest.TestCase):
    """Verify window structure, title, and minimum size."""

    def setUp(self) -> None:
        self.win = MainWindow()
        self.win.show()

    def tearDown(self) -> None:
        self.win.close()
        self.win.deleteLater()

    def test_can_be_instantiated(self) -> None:
        self.assertIsInstance(self.win, MainWindow)

    def test_title(self) -> None:
        self.assertEqual(self.win.windowTitle(), "Task Manager PRO")

    def test_minimum_size(self) -> None:
        size = self.win.minimumSize()
        self.assertGreaterEqual(size.width(), 800)
        self.assertGreaterEqual(size.height(), 600)

    def test_stacked_widget_exists(self) -> None:
        self.assertIsNotNone(self.win._stack)
        self.assertIsInstance(self.win._stack, QStackedWidget)

    def test_stack_background_stylesheet_is_scoped(self) -> None:
        # A bare `background-color:` rule would cascade onto page
        # descendants and force light backgrounds on unstyled controls;
        # it must be scoped to the stack itself so pages stay readable.
        style = self.win._stack.styleSheet()
        self.assertIn("QStackedWidget#content_stack", style)
        self.assertEqual(self.win._stack.objectName(), "content_stack")

    def test_five_navigation_pages(self) -> None:
        self.assertEqual(self.win._stack.count(), 5)

    def test_five_sidebar_buttons(self) -> None:
        self.assertEqual(len(self.win._nav_buttons), 5)


class TestSidebarNavigation(unittest.TestCase):
    """Verify sidebar buttons switch pages correctly."""

    def setUp(self) -> None:
        self.win = MainWindow()
        self.win.show()

    def tearDown(self) -> None:
        self.win.close()
        self.win.deleteLater()

    def test_click_dashboard(self) -> None:
        self.win._nav_buttons[0].click()
        self.assertEqual(self.win._stack.currentIndex(), 0)

    def test_click_tasks(self) -> None:
        self.win._nav_buttons[1].click()
        self.assertEqual(self.win._stack.currentIndex(), 1)

    def test_click_categories(self) -> None:
        self.win._nav_buttons[2].click()
        self.assertEqual(self.win._stack.currentIndex(), 2)

    def test_click_trash(self) -> None:
        self.win._nav_buttons[3].click()
        self.assertEqual(self.win._stack.currentIndex(), 3)

    def test_click_settings(self) -> None:
        self.win._nav_buttons[4].click()
        self.assertEqual(self.win._stack.currentIndex(), 4)

    def test_active_button_changes(self) -> None:
        # Default is index 0 (Dashboard)
        self.assertIn("3498db", self.win._nav_buttons[0].styleSheet())
        # Click Tasks
        self.win._nav_buttons[1].click()
        self.assertIn("3498db", self.win._nav_buttons[1].styleSheet())
        # Dashboard button should no longer be active
        self.assertNotIn("3498db", self.win._nav_buttons[0].styleSheet())

    def test_all_buttons_have_names(self) -> None:
        expected = ["nav_dashboard", "nav_tasks", "nav_categories",
                     "nav_trash", "nav_settings"]
        for btn, name in zip(self.win._nav_buttons, expected):
            self.assertEqual(btn.objectName(), name)

    def test_pages_have_object_names(self) -> None:
        expected = ["page_dashboard", "page_tasks", "page_categories",
                     "page_trash", "page_settings"]
        for idx, name in enumerate(expected):
            page = self.win._stack.widget(idx)
            self.assertEqual(page.objectName(), name)

    def test_placeholder_text(self) -> None:
        from task_manager.ui.categories import CategoriesWidget
        from task_manager.ui.dashboard import DashboardWidget
        from task_manager.ui.task_list import TaskListWidget
        # Indices 0 (Dashboard), 1 (Tasks), 2 (Categories) are real widgets.
        expected = {3: "Trash", 4: "Settings"}
        for idx, text in expected.items():
            page = self.win._stack.widget(idx)
            self.assertIn(text, page.text())
        self.assertIsInstance(self.win._stack.widget(0), DashboardWidget)
        self.assertIsInstance(self.win._stack.widget(1), TaskListWidget)
        self.assertIsInstance(self.win._stack.widget(2), CategoriesWidget)


class TestMainWindowResize(unittest.TestCase):
    """Verify window handles resizing gracefully."""

    def setUp(self) -> None:
        self.win = MainWindow()
        self.win.show()

    def tearDown(self) -> None:
        self.win.close()
        self.win.deleteLater()

    def test_resize_larger(self) -> None:
        self.win.resize(1200, 900)
        self.assertEqual(self.win.width(), 1200)
        self.assertEqual(self.win.height(), 900)

    def test_resize_smaller(self) -> None:
        self.win.resize(800, 600)
        self.assertEqual(self.win.width(), 800)
        self.assertEqual(self.win.height(), 600)


if __name__ == "__main__":
    unittest.main()
