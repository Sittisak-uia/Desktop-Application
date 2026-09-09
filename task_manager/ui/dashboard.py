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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._label = label
        self._color = color
        self.setMinimumHeight(115)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        layout.addWidget(self.value_label, stretch=2)

        self.caption = QLabel(label)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        layout.addWidget(self.caption)

        self.apply_theme("light")

    def apply_theme(self, theme: str) -> None:
        if theme == "dark":
            self.setStyleSheet(
                f"background-color: {self._color}; border-radius: 8px;"
            )
            self.value_label.setStyleSheet(
                "color: white; border: none; background: transparent;"
            )
            self.caption.setStyleSheet(
                "color: white; border: none; background: transparent;"
            )
        else:
            self.setStyleSheet(
                "background-color: #ffffff; "
                "border: 1px solid #cbd5e1; "
                f"border-top: 4px solid {self._color}; "
                "border-radius: 8px;"
            )
            self.value_label.setStyleSheet(
                "color: #0f172a; border: none; background: transparent;"
            )
            self.caption.setStyleSheet(
                "color: #475569; border: none; background: transparent; font-weight: 600;"
            )

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))

    def _get_value(self) -> int:
        return int(self.value_label.text())


class DashboardWidget(QWidget):
    """Widget that summarises current active task statistics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        header.addWidget(self.title_label)
        header.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        # Scrollable content so the page stays usable at 800x600
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.content = QWidget()
        self.content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(self.content)
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
        self.priority_header = self._make_section_header("Priority Breakdown")
        content_layout.addWidget(self.priority_header)

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
        self.category_header = self._make_section_header("Category Breakdown")
        content_layout.addWidget(self.category_header)

        self.category_container = QWidget()
        self.category_layout = QVBoxLayout(self.category_container)
        self.category_layout.setContentsMargins(0, 0, 0, 0)
        self.category_layout.setSpacing(6)
        content_layout.addWidget(self.category_container)

        content_layout.addStretch()
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, stretch=1)

        self.apply_theme(self._current_theme)

    def _make_section_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        return label

    def _make_breakdown_row(self) -> QLabel:
        label = QLabel("0")
        label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        return label

    def _make_category_row(self, name: str, count: int) -> QLabel:
        label = QLabel(f"{name}: {count}")
        label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        if self._current_theme == "dark":
            from task_manager.ui.theme import get_card_row_style
            label.setStyleSheet(get_card_row_style("dark"))
        else:
            label.setStyleSheet(
                "background-color: #ffffff; "
                "border: 1px solid #cbd5e1; "
                "border-left: 4px solid #8b5cf6; "
                "border-radius: 6px; "
                "padding: 10px 14px; "
                "color: #0f172a; "
                "font-weight: 600; "
                "font-size: 13px;"
            )
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
                w.hide()
                w.deleteLater()
        if not by_category:
            empty_label = QLabel("No categories in use yet.")
            if self._current_theme == "dark":
                empty_label.setStyleSheet("color: #7f8c8d; padding: 8px;")
            else:
                empty_label.setStyleSheet(
                    "background-color: #ffffff; border: 1px dashed #cbd5e1; "
                    "border-radius: 6px; padding: 12px; color: #64748b; font-style: italic;"
                )
            self.category_layout.addWidget(empty_label)
        else:
            for name, count in sorted(by_category.items()):
                self.category_layout.addWidget(self._make_category_row(name, count))

    def apply_theme(self, theme: str) -> None:
        """Update DashboardWidget styling to match the specified theme."""
        from task_manager.ui.theme import get_card_row_style, get_title_color
        self._current_theme = theme.lower()
        is_dark = self._current_theme == "dark"

        if is_dark:
            self.setStyleSheet("")
            if hasattr(self, "content"):
                self.content.setStyleSheet("background: transparent;")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet(f"color: {get_title_color(self._current_theme)};")
            if hasattr(self, "refresh_btn"):
                self.refresh_btn.setStyleSheet(
                    "QPushButton { background-color: #3498db; color: white;"
                    " padding: 8px 18px; border-radius: 4px; font-weight: bold; }"
                )
            if hasattr(self, "priority_header"):
                self.priority_header.setStyleSheet("color: #f5f6fa; padding-top: 8px;")
            if hasattr(self, "category_header"):
                self.category_header.setStyleSheet("color: #f5f6fa; padding-top: 8px;")
            row_style = get_card_row_style("dark")
            if hasattr(self, "low_label"):
                self.low_label.setStyleSheet(row_style)
            if hasattr(self, "medium_label"):
                self.medium_label.setStyleSheet(row_style)
            if hasattr(self, "high_label"):
                self.high_label.setStyleSheet(row_style)
        else:
            self.setStyleSheet("background-color: #f1f5f9;")
            if hasattr(self, "content"):
                self.content.setStyleSheet("background: transparent;")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("color: #0f172a; font-weight: bold;")
            if hasattr(self, "refresh_btn"):
                self.refresh_btn.setStyleSheet(
                    "QPushButton { background-color: #2563eb; color: white;"
                    " padding: 8px 18px; border: 1px solid #1d4ed8; border-radius: 6px;"
                    " font-weight: bold; font-size: 13px; }"
                    "QPushButton:hover { background-color: #1d4ed8; }"
                    "QPushButton:pressed { background-color: #1e40af; }"
                )
            if hasattr(self, "priority_header"):
                self.priority_header.setStyleSheet(
                    "color: #0f172a; font-weight: bold; font-size: 14px; padding-top: 14px; padding-bottom: 6px;"
                )
            if hasattr(self, "category_header"):
                self.category_header.setStyleSheet(
                    "color: #0f172a; font-weight: bold; font-size: 14px; padding-top: 14px; padding-bottom: 6px;"
                )
            if hasattr(self, "low_label"):
                self.low_label.setStyleSheet(
                    "background-color: #ffffff; border: 1px solid #cbd5e1; "
                    "border-left: 4px solid #3b82f6; border-radius: 6px; "
                    "padding: 10px 14px; color: #0f172a; font-weight: 600; font-size: 13px;"
                )
            if hasattr(self, "medium_label"):
                self.medium_label.setStyleSheet(
                    "background-color: #ffffff; border: 1px solid #cbd5e1; "
                    "border-left: 4px solid #f59e0b; border-radius: 6px; "
                    "padding: 10px 14px; color: #0f172a; font-weight: 600; font-size: 13px;"
                )
            if hasattr(self, "high_label"):
                self.high_label.setStyleSheet(
                    "background-color: #ffffff; border: 1px solid #cbd5e1; "
                    "border-left: 4px solid #ef4444; border-radius: 6px; "
                    "padding: 10px 14px; color: #0f172a; font-weight: 600; font-size: 13px;"
                )

        for card in (getattr(self, "total_card", None),
                     getattr(self, "pending_card", None),
                     getattr(self, "completed_card", None),
                     getattr(self, "overdue_card", None)):
            if card is not None and hasattr(card, "apply_theme"):
                card.apply_theme(self._current_theme)

        self.refresh()