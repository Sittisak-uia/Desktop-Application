"""Settings page for SQLite Task Manager PRO.

Manages application preferences including Light and Dark mode theme switching,
persisting choices via QSettings.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from task_manager.database_backup import (
    backup_database,
    generate_backup_filename,
    restore_database,
)

from task_manager.ui.theme import (
    DARK_BG_CARD,
    DARK_BORDER,
    DARK_TEXT,
    LIGHT_BG_CARD,
    LIGHT_BORDER,
    LIGHT_TEXT,
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    get_combo_style,
    get_current_theme,
    get_subtitle_color,
    get_title_color,
    set_current_theme,
)


class SettingsWidget(QWidget):
    """Widget allowing the user to configure preferences such as application theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_theme = get_current_theme()
        self._build_ui()
        self._connect_signals()
        self.refresh()

    def text(self) -> str:
        """Return page label for compatibility."""
        return "Settings"

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Title
        self.title_label = QLabel("Settings")
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {get_title_color(self._current_theme)};")
        layout.addWidget(self.title_label)

        # Appearance Card / Container Frame
        self.card_frame = QFrame()
        self.card_frame.setObjectName("settings_card")
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Section Header
        self.section_title = QLabel("Appearance & Theme")
        self.section_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        card_layout.addWidget(self.section_title)

        self.section_subtitle = QLabel(
            "Select whether you prefer a clean light palette or a sleek dark mode."
        )
        self.section_subtitle.setFont(QFont("Segoe UI", 10))
        card_layout.addWidget(self.section_subtitle)

        # Current theme indicator
        self.theme_indicator = QLabel(f"Current Theme: {self._current_theme.title()}")
        self.theme_indicator.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        card_layout.addWidget(self.theme_indicator)

        # Theme selection row
        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)

        self.combo_label = QLabel("Theme Mode:")
        self.combo_label.setFont(QFont("Segoe UI", 11))
        theme_row.addWidget(self.combo_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Light", THEME_LIGHT)
        self.theme_combo.addItem("Dark", THEME_DARK)
        self.theme_combo.setMinimumWidth(150)
        self.theme_combo.setStyleSheet(get_combo_style(self._current_theme))
        theme_row.addWidget(self.theme_combo)

        theme_row.addStretch()
        card_layout.addLayout(theme_row)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.apply_btn = QPushButton("Apply Theme")
        self.apply_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #3498db; color: white;"
            "  font-weight: bold; border-radius: 4px; padding: 8px 18px;"
            "}"
            "QPushButton:hover { background-color: #2980b9; }"
        )
        btn_row.addWidget(self.apply_btn)

        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #7f8c8d; color: white;"
            "  font-weight: bold; border-radius: 4px; padding: 8px 18px;"
            "}"
            "QPushButton:hover { background-color: #95a5a6; }"
        )
        btn_row.addWidget(self.reset_btn)

        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        # Status feedback label
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        card_layout.addWidget(self.status_label)

        layout.addWidget(self.card_frame)

        # Database Backup & Restore Card
        self.backup_card_frame = QFrame()
        self.backup_card_frame.setObjectName("backup_card")
        backup_layout = QVBoxLayout(self.backup_card_frame)
        backup_layout.setContentsMargins(16, 16, 16, 16)
        backup_layout.setSpacing(12)

        self.backup_section_title = QLabel("Database Backup & Restore")
        self.backup_section_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        backup_layout.addWidget(self.backup_section_title)

        self.backup_section_subtitle = QLabel(
            "Create a safe backup of your tasks database or restore from a previously saved file."
        )
        self.backup_section_subtitle.setFont(QFont("Segoe UI", 10))
        self.backup_section_subtitle.setWordWrap(True)
        backup_layout.addWidget(self.backup_section_subtitle)

        # Buttons row
        backup_btn_row = QHBoxLayout()
        backup_btn_row.setSpacing(10)

        self.backup_btn = QPushButton("Backup Database")
        self.backup_btn.setObjectName("backup_database_btn")
        self.backup_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #27ae60; color: white;"
            "  font-weight: bold; border-radius: 4px; padding: 8px 18px;"
            "}"
            "QPushButton:hover { background-color: #219150; }"
        )
        backup_btn_row.addWidget(self.backup_btn)

        self.restore_btn = QPushButton("Restore Database")
        self.restore_btn.setObjectName("restore_database_btn")
        self.restore_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #d35400; color: white;"
            "  font-weight: bold; border-radius: 4px; padding: 8px 18px;"
            "}"
            "QPushButton:hover { background-color: #ba4a00; }"
        )
        backup_btn_row.addWidget(self.restore_btn)

        backup_btn_row.addStretch()
        backup_layout.addLayout(backup_btn_row)

        # Feedback label
        self.backup_status_label = QLabel("")
        self.backup_status_label.setFont(QFont("Segoe UI", 10))
        self.backup_status_label.setWordWrap(True)
        backup_layout.addWidget(self.backup_status_label)

        layout.addWidget(self.backup_card_frame)
        layout.addStretch()

        self._update_card_style(self._current_theme)

    def _connect_signals(self) -> None:
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        self.backup_btn.clicked.connect(self._on_backup_clicked)
        self.restore_btn.clicked.connect(self._on_restore_clicked)

    def _update_card_style(self, theme: str) -> None:
        if theme == THEME_DARK:
            card_style = (
                f"QFrame#settings_card, QFrame#backup_card {{"
                f"  background-color: {DARK_BG_CARD};"
                f"  border: 1px solid {DARK_BORDER};"
                f"  border-radius: 8px;"
                f"}}"
            )
            self.card_frame.setStyleSheet(card_style)
            self.backup_card_frame.setStyleSheet(card_style)
            self.section_title.setStyleSheet(f"color: {DARK_TEXT};")
            self.section_subtitle.setStyleSheet(f"color: {get_subtitle_color(theme)};")
            self.backup_section_title.setStyleSheet(f"color: {DARK_TEXT};")
            self.backup_section_subtitle.setStyleSheet(f"color: {get_subtitle_color(theme)};")
            self.theme_indicator.setStyleSheet(f"color: {DARK_TEXT}; font-weight: bold;")
            self.combo_label.setStyleSheet(f"color: {DARK_TEXT};")
        else:
            card_style = (
                f"QFrame#settings_card, QFrame#backup_card {{"
                f"  background-color: {LIGHT_BG_CARD};"
                f"  border: 1px solid {LIGHT_BORDER};"
                f"  border-radius: 8px;"
                f"}}"
            )
            self.card_frame.setStyleSheet(card_style)
            self.backup_card_frame.setStyleSheet(card_style)
            self.section_title.setStyleSheet(f"color: {LIGHT_TEXT};")
            self.section_subtitle.setStyleSheet(f"color: {get_subtitle_color(theme)};")
            self.backup_section_title.setStyleSheet(f"color: {LIGHT_TEXT};")
            self.backup_section_subtitle.setStyleSheet(f"color: {get_subtitle_color(theme)};")
            self.theme_indicator.setStyleSheet(f"color: {LIGHT_TEXT}; font-weight: bold;")
            self.combo_label.setStyleSheet(f"color: {LIGHT_TEXT};")

    def refresh(self) -> None:
        """Reload saved settings from QSettings."""
        self._current_theme = get_current_theme()
        idx = self.theme_combo.findData(self._current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self.theme_indicator.setText(f"Current Theme: {self._current_theme.title()}")
        self.status_label.setText("")
        self.backup_status_label.setText("")
        self.apply_theme(self._current_theme)

    def _on_apply_clicked(self) -> None:
        selected_theme = self.theme_combo.currentData()
        if not selected_theme:
            selected_theme = self.theme_combo.currentText().lower()

        set_current_theme(selected_theme)
        apply_theme(selected_theme)

        main_win = self.window()
        if main_win is not None and hasattr(main_win, "apply_theme") and callable(main_win.apply_theme):
            main_win.apply_theme(selected_theme)
        else:
            self.apply_theme(selected_theme)

        self.theme_indicator.setText(f"Current Theme: {selected_theme.title()}")
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.status_label.setText("Theme applied successfully.")

    def _on_reset_clicked(self) -> None:
        set_current_theme(THEME_LIGHT)
        apply_theme(THEME_LIGHT)

        main_win = self.window()
        if main_win is not None and hasattr(main_win, "apply_theme") and callable(main_win.apply_theme):
            main_win.apply_theme(THEME_LIGHT)
        else:
            self.apply_theme(THEME_LIGHT)

        idx = self.theme_combo.findData(THEME_LIGHT)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

        self.theme_indicator.setText(f"Current Theme: {THEME_LIGHT.title()}")
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.status_label.setText("Theme reset to default (Light).")

    def _on_backup_clicked(self) -> None:
        default_name = generate_backup_filename()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Backup Database",
            default_name,
            "SQLite Database (*.db);;All Files (*)",
        )
        if not file_path:
            return

        try:
            saved_path = backup_database(file_path)
            self.backup_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.backup_status_label.setText(f"Backup created successfully: {os.path.basename(saved_path)}")
            QMessageBox.information(
                self,
                "Backup Successful",
                f"Database backup saved successfully to:\n{saved_path}",
            )
        except Exception as exc:
            self.backup_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.backup_status_label.setText("Backup failed.")
            QMessageBox.critical(
                self,
                "Backup Error",
                f"Failed to backup database:\n{str(exc)}",
            )

    def _on_restore_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore Database",
            "",
            "SQLite Database (*.db);;All Files (*)",
        )
        if not file_path:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            "Restoring a database will replace the current Task Manager data. A safety backup will be created first. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            success, msg, safety_path = restore_database(file_path)
            if not success:
                self.backup_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                self.backup_status_label.setText("Restore failed.")
                QMessageBox.critical(self, "Restore Error", msg)
                return

            main_win = self.window()
            if main_win is not None and hasattr(main_win, "refresh_all_pages") and callable(main_win.refresh_all_pages):
                main_win.refresh_all_pages()

            self.backup_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.backup_status_label.setText("Database restored successfully.")

            safety_msg = f"\n\nA safety backup of your previous database was saved to:\n{safety_path}" if safety_path else ""
            QMessageBox.information(
                self,
                "Restore Successful",
                f"Database has been restored successfully.{safety_msg}",
            )
        except Exception as exc:
            self.backup_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.backup_status_label.setText("Restore failed.")
            QMessageBox.critical(self, "Restore Error", f"Failed to restore database:\n{str(exc)}")

    def apply_theme(self, theme: str) -> None:
        """Update SettingsWidget visuals to match theme."""
        self._current_theme = theme
        self.title_label.setStyleSheet(f"color: {get_title_color(theme)};")
        self.theme_combo.setStyleSheet(get_combo_style(theme))
        self._update_card_style(theme)
