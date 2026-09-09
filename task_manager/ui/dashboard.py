"""Dashboard page for SQLite Task Manager PRO.

Read/summary widget that displays aggregate task statistics in a set of
summary cards plus priority and category breakdowns.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from task_manager.database import get_dashboard_stats

_PRIORITIES = ["LOW", "MEDIUM", "HIGH"]


class _StatCard(QWidget):
    """A single summary card showing a value and its label."""

    def __init__(self, label: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.setStyleSheet(
            f"background-color: {color}; border-radius: 8px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: white; border: none; background: transparent;")
        layout.addWidget(self.value_label, stretch=2)

        self.caption = QLabel(label)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setFont(QFont("Segoe UI", 11))
        self.caption.setStyleSheet("color: white; border: none; background: transparent;")
        layout.addWidget(self.caption)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))

    def _get_value(self) -> int:
        return int(self.value_label.text())


class DashboardWidget(QWidget):
    """Widget that summarises current active task statistics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_theme: str = "light"
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.title_label = QLabel("Dashboard")
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #2c3e50;")
        header.addWidget(self.title_label)
        header.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(
            "QPushButton { background-color: #3498db; color: white;"
            " padding: 8px 18px; border-radius: 4px; font-weight: bold; }"
        )
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        # Scrollable content so the page stays usable at 800x600
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # ---- Summary cards ----
        self.total_card = _StatCard("Total Tasks", "#3498db")
        self.pending_card = _StatCard("Pending", "#f39c12")
        self.completed_card = _StatCard("Completed", "#27ae60")
        self.overdue_card = _StatCard("Overdue", "#e74c3c")

        cards = QGridLayout()
        cards.setSpacing(12)
        cards.addWidget(self.total_card, 0, 0)
        cards.addWidget(self.pending_card, 0, 1)
        cards.addWidget(self.completed_card, 1, 0)
        cards.addWidget(self.overdue_card, 1, 1)
        content_layout.addLayout(cards)

        # ---- Priority breakdown ----
        priority_section = self._make_section_header("Priority Breakdown")
        content_layout.addWidget(priority_section)

        self.low_label = self._make_breakdown_row()
        self.medium_label = self._make_breakdown_row()
        self.high_label = self._make_breakdown_row()
        priority_box = QVBoxLayout()
        priority_box.setSpacing(6)
        priority_box.addWidget(self.low_label)
        priority_box.addWidget(self.medium_label)
        priority_box.addWidget(self.high_label)
        content_layout.addLayout(priority_box)

        # ---- Category breakdown ----
        category_section = self._make_section_header("Category Breakdown")
        content_layout.addWidget(category_section)

        self.category_container = QWidget()
        self.category_layout = QVBoxLayout(self.category_container)
        self.category_layout.setContentsMargins(0, 0, 0, 0)
        self.category_layout.setSpacing(6)
        content_layout.addWidget(self.category_container)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    def _make_section_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        label.setStyleSheet("color: #2c3e50; padding-top: 8px;")
        return label

    def _make_breakdown_row(self) -> QLabel:
        from task_manager.ui.theme import get_card_row_style
        label = QLabel("0")
        label.setStyleSheet(get_card_row_style(self._current_theme))
        return label

    def _make_category_row(self, name: str, count: int) -> QLabel:
        from task_manager.ui.theme import get_card_row_style
        label = QLabel(f"{name}: {count}")
        label.setStyleSheet(get_card_row_style(self._current_theme))
        return label

    def refresh(self) -> None:
        """Reload statistics from the database and update every label."""
        try:
            stats = get_dashboard_stats()
        except Exception as exc:
            QMessageBox.critical(
                self, "Dashboard Error",
                f"Failed to load dashboard statistics:\n{exc}",
            )
            stats = {
                "total": 0, "pending": 0, "completed": 0, "overdue": 0,
                "by_category": {}, "by_priority": {},
            }

        self.total_card.set_value(stats.get("total", 0))
        self.pending_card.set_value(stats.get("pending", 0))
        self.completed_card.set_value(stats.get("completed", 0))
        self.overdue_card.set_value(stats.get("overdue", 0))

        by_priority = stats.get("by_priority", {})
        self.low_label.setText(f"Low: {by_priority.get('LOW', 0)}")
        self.medium_label.setText(f"Medium: {by_priority.get('MEDIUM', 0)}")
        self.high_label.setText(f"High: {by_priority.get('HIGH', 0)}")

        by_category = stats.get("by_category", {})
        while self.category_layout.count():
            item = self.category_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not by_category:
            empty_label = QLabel("No categories in use yet.")
            empty_label.setStyleSheet("color: #7f8c8d; padding: 8px;")
            self.category_layout.addWidget(empty_label)
        else:
            for name, count in sorted(by_category.items()):
                self.category_layout.addWidget(self._make_category_row(name, count))

    def apply_theme(self, theme: str) -> None:
        """Update DashboardWidget styling to match the specified theme."""
        from task_manager.ui.theme import get_card_row_style, get_title_color
        self._current_theme = theme.lower()
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {get_title_color(self._current_theme)};")
        if hasattr(self, "low_label") and hasattr(self, "medium_label") and hasattr(self, "high_label"):
            row_style = get_card_row_style(self._current_theme)
            self.low_label.setStyleSheet(row_style)
            self.medium_label.setStyleSheet(row_style)
            self.high_label.setStyleSheet(row_style)
        self.refresh()