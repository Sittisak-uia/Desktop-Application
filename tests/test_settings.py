"""Focused unit tests for task_manager.ui.settings and theme switching (Phase 10).

Uses the standard library unittest only -- no pytest dependency.
Tests settings instantiation, theme selection, QSettings persistence,
readability tokens in light and dark modes, and MainWindow navigation.
"""

import sys
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from task_manager.ui.settings import SettingsWidget
from task_manager.ui.theme import (
    DARK_BG_CARD,
    DARK_TEXT,
    LIGHT_TEXT,
    THEME_DARK,
    THEME_LIGHT,
    create_dark_palette,
    create_light_palette,
    get_combo_style,
    get_content_stack_style,
    get_current_theme,
    get_input_style,
    get_settings,
    get_sidebar_style,
    get_table_style,
    get_title_color,
    set_current_theme,
)

# Ensure a QApplication exists for headless GUI testing
_app = QApplication.instance() or QApplication(sys.argv)


class TestSettingsWidgetInstantiation(unittest.TestCase):
    """Verify SettingsWidget can be created and has all required controls."""

    def setUp(self) -> None:
        set_current_theme(THEME_LIGHT)
        self.widget = SettingsWidget()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()
        set_current_theme(THEME_LIGHT)

    def test_can_be_instantiated(self) -> None:
        self.assertIsInstance(self.widget, SettingsWidget)

    def test_page_text_property(self) -> None:
        self.assertEqual(self.widget.text(), "Settings")

    def test_theme_controls_exist(self) -> None:
        self.assertIsNotNone(self.widget.theme_combo)
        self.assertIsNotNone(self.widget.theme_indicator)
        self.assertIsNotNone(self.widget.apply_btn)
        self.assertIsNotNone(self.widget.reset_btn)
        self.assertIsNotNone(self.widget.status_label)

    def test_theme_combo_has_light_and_dark_options(self) -> None:
        self.assertEqual(self.widget.theme_combo.count(), 2)
        items = [self.widget.theme_combo.itemText(i) for i in range(2)]
        self.assertIn("Light", items)
        self.assertIn("Dark", items)


class TestThemeSelectionAndPersistence(unittest.TestCase):
    """Verify selecting themes, QSettings persistence, and reload."""

    def setUp(self) -> None:
        set_current_theme(THEME_LIGHT)
        self.widget = SettingsWidget()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()
        set_current_theme(THEME_LIGHT)

    def test_light_theme_can_be_selected(self) -> None:
        idx = self.widget.theme_combo.findData(THEME_LIGHT)
        self.widget.theme_combo.setCurrentIndex(idx)
        self.widget.apply_btn.click()

        self.assertEqual(get_current_theme(), THEME_LIGHT)
        self.assertIn("Light", self.widget.theme_indicator.text())

    def test_dark_theme_can_be_selected(self) -> None:
        idx = self.widget.theme_combo.findData(THEME_DARK)
        self.widget.theme_combo.setCurrentIndex(idx)
        self.widget.apply_btn.click()

        self.assertEqual(get_current_theme(), THEME_DARK)
        self.assertIn("Dark", self.widget.theme_indicator.text())

    def test_qsettings_stores_selected_theme(self) -> None:
        idx = self.widget.theme_combo.findData(THEME_DARK)
        self.widget.theme_combo.setCurrentIndex(idx)
        self.widget.apply_btn.click()

        settings = get_settings()
        stored = settings.value("theme")
        self.assertEqual(str(stored).lower(), THEME_DARK)

    def test_theme_persists_after_recreating_settings_widget(self) -> None:
        # Save dark theme
        idx = self.widget.theme_combo.findData(THEME_DARK)
        self.widget.theme_combo.setCurrentIndex(idx)
        self.widget.apply_btn.click()

        # Simulate restarting application by creating a brand new SettingsWidget
        new_widget = SettingsWidget()
        try:
            self.assertEqual(new_widget._current_theme, THEME_DARK)
            self.assertEqual(new_widget.theme_combo.currentData(), THEME_DARK)
            self.assertIn("Dark", new_widget.theme_indicator.text())
        finally:
            new_widget.close()
            new_widget.deleteLater()

    def test_reset_to_default_restores_light(self) -> None:
        # First set to dark
        idx = self.widget.theme_combo.findData(THEME_DARK)
        self.widget.theme_combo.setCurrentIndex(idx)
        self.widget.apply_btn.click()
        self.assertEqual(get_current_theme(), THEME_DARK)

        # Now click reset
        self.widget.reset_btn.click()
        self.assertEqual(get_current_theme(), THEME_LIGHT)
        self.assertIn("Light", self.widget.theme_indicator.text())
        self.assertEqual(self.widget.theme_combo.currentData(), THEME_LIGHT)


class TestThemeReadabilityAndStyling(unittest.TestCase):
    """Verify readability tokens and styling for light and dark modes."""

    def setUp(self) -> None:
        set_current_theme(THEME_LIGHT)

    def tearDown(self) -> None:
        set_current_theme(THEME_LIGHT)

    def test_readability_in_light_mode(self) -> None:
        # Palette: text is dark #2c3e50, background is light
        pal = create_light_palette()
        self.assertEqual(pal.color(pal.ColorRole.WindowText).name().lower(), LIGHT_TEXT.lower())
        self.assertEqual(pal.color(pal.ColorRole.Text).name().lower(), LIGHT_TEXT.lower())

        # Table style: explicit white background with dark text
        table_style = get_table_style(THEME_LIGHT)
        self.assertIn(LIGHT_TEXT, table_style)
        self.assertIn("background-color: white", table_style)

        # Title color
        self.assertEqual(get_title_color(THEME_LIGHT), LIGHT_TEXT)

    def test_readability_in_dark_mode(self) -> None:
        # Palette: text is light #f5f6fa, background is dark #1e272e
        pal = create_dark_palette()
        self.assertEqual(pal.color(pal.ColorRole.WindowText).name().lower(), DARK_TEXT.lower())
        self.assertEqual(pal.color(pal.ColorRole.Text).name().lower(), DARK_TEXT.lower())

        # Table style: dark background with light text
        table_style = get_table_style(THEME_DARK)
        self.assertIn(DARK_TEXT, table_style)
        self.assertIn(DARK_BG_CARD, table_style)

        # Input and Combo styles: readable dark styling
        input_style = get_input_style(THEME_DARK)
        self.assertIn(DARK_TEXT, input_style)
        self.assertIn(DARK_BG_CARD, input_style)

        combo_style = get_combo_style(THEME_DARK)
        self.assertIn(DARK_TEXT, combo_style)
        self.assertIn(DARK_BG_CARD, combo_style)

        # Title color
        self.assertEqual(get_title_color(THEME_DARK), DARK_TEXT)


class TestMainWindowSettingsIntegration(unittest.TestCase):
    """Test MainWindow integration with Settings page and theme switching."""

    def setUp(self) -> None:
        set_current_theme(THEME_LIGHT)
        from task_manager.ui.main_window import MainWindow

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
        set_current_theme(THEME_LIGHT)

    def test_main_window_has_settings_widget_at_index_four(self) -> None:
        settings_widget = self.win._stack.widget(4)
        self.assertIsInstance(settings_widget, SettingsWidget)

    def test_main_window_navigation_to_settings(self) -> None:
        # Click sidebar Settings button (index 4)
        self.win._nav_buttons[4].click()
        self.assertEqual(self.win._stack.currentIndex(), 4)
        self.assertIn("3498db", self.win._nav_buttons[4].styleSheet())

    def test_existing_pages_remain_accessible(self) -> None:
        # All 5 pages accessible
        for idx in range(5):
            self.win._nav_buttons[idx].click()
            self.assertEqual(self.win._stack.currentIndex(), idx)

    def test_theme_switching_updates_all_pages(self) -> None:
        # Switch to dark
        self.win.apply_theme(THEME_DARK)
        self.assertEqual(self.win._current_theme, THEME_DARK)
        self.assertIn("#1e272e", self.win._stack.styleSheet())
        self.assertIn("#181e24", self.win._sidebar.styleSheet())

        # Switch back to light
        self.win.apply_theme(THEME_LIGHT)
        self.assertEqual(self.win._current_theme, THEME_LIGHT)
        self.assertIn("#ecf0f1", self.win._stack.styleSheet())
        self.assertIn("#2c3e50", self.win._sidebar.styleSheet())


if __name__ == "__main__":
    unittest.main()
