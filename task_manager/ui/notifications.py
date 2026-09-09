"""Overdue tasks notification banner for SQLite Task Manager PRO.

Implements Phase 12 requirements:
- Non-blocking banner indicating overdue tasks.
- Overdue definition: status = 'PENDING', due_date IS NOT NULL and < today, is_deleted = 0.
- Anti-spam protection: avoids repeatedly showing notifications for the same unchanged condition.
- Dismissable by the user.
- Consistent Light and Dark mode styling with readable text.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from task_manager.ui.theme import THEME_DARK, THEME_LIGHT, get_current_theme

_LIGHT_BANNER_STYLE = """
    QFrame#notification_banner {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        border-radius: 6px;
        margin: 10px 16px 4px 16px;
    }
    QLabel {
        color: #856404;
        background: transparent;
    }
    QPushButton#dismiss_btn {
        background: transparent;
        color: #856404;
        border: none;
        font-weight: bold;
        font-size: 14px;
        padding: 2px 6px;
    }
    QPushButton#dismiss_btn:hover {
        color: #533f03;
    }
    QPushButton#view_tasks_btn {
        background-color: #f0ad4e;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: bold;
        padding: 4px 10px;
        font-size: 12px;
    }
    QPushButton#view_tasks_btn:hover {
        background-color: #ec971f;
    }
"""

_DARK_BANNER_STYLE = """
    QFrame#notification_banner {
        background-color: #3a2a18;
        border: 1px solid #6b4d1b;
        border-radius: 6px;
        margin: 10px 16px 4px 16px;
    }
    QLabel {
        color: #ffe8a1;
        background: transparent;
    }
    QPushButton#dismiss_btn {
        background: transparent;
        color: #ffe8a1;
        border: none;
        font-weight: bold;
        font-size: 14px;
        padding: 2px 6px;
    }
    QPushButton#dismiss_btn:hover {
        color: #ffffff;
    }
    QPushButton#view_tasks_btn {
        background-color: #d58512;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: bold;
        padding: 4px 10px;
        font-size: 12px;
    }
    QPushButton#view_tasks_btn:hover {
        background-color: #e09b3d;
    }
"""


class NotificationBanner(QFrame):
    """Non-blocking notification banner for displaying overdue task warnings."""

    def __init__(
        self,
        parent: QWidget | None = None,
        on_view_tasks: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("notification_banner")
        self._on_view_tasks = on_view_tasks

        self._current_theme = get_current_theme()
        self._last_overdue_ids: set[int] = set()
        self._dismissed = False
        self._overdue_tasks: list[dict] = []

        self._build_ui()
        self.apply_theme(self._current_theme)
        self.hide()  # Hidden by default when no overdue tasks exist

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Warning icon badge
        self.icon_label = QLabel("⚠️")
        self.icon_label.setFont(QFont("Segoe UI", 12))
        layout.addWidget(self.icon_label)

        # Message text
        self.message_label = QLabel("")
        self.message_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, stretch=1)

        # Optional "View Tasks" button
        self.view_btn = QPushButton("View Tasks")
        self.view_btn.setObjectName("view_tasks_btn")
        self.view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_btn.clicked.connect(self._on_view_clicked)
        layout.addWidget(self.view_btn)

        # Dismiss button
        self.dismiss_btn = QPushButton("✕")
        self.dismiss_btn.setObjectName("dismiss_btn")
        self.dismiss_btn.setToolTip("Dismiss notification")
        self.dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dismiss_btn.clicked.connect(self.dismiss)
        layout.addWidget(self.dismiss_btn)

    def _on_view_clicked(self) -> None:
        if self._on_view_tasks:
            self._on_view_tasks()

    def dismiss(self) -> None:
        """Dismiss the current notification banner."""
        self._dismissed = True
        self.hide()

    def reset_dismissed(self) -> None:
        """Reset the dismissed state so notifications can be shown again if condition persists."""
        self._dismissed = False

    def is_dismissed(self) -> bool:
        """Return whether current notification set was dismissed."""
        return self._dismissed

    def get_overdue_count(self) -> int:
        """Return count of currently registered overdue tasks."""
        return len(self._overdue_tasks)

    def get_overdue_tasks(self) -> list[dict]:
        """Return list of currently registered overdue tasks."""
        return list(self._overdue_tasks)

    def check_and_notify(self, overdue_tasks: list[dict]) -> bool:
        """Evaluate overdue tasks and update notification banner.

        Prevents spam: if the exact same set of overdue task IDs is already
        known and was dismissed by the user, the banner is not redundantly re-opened.

        Parameters
        ----------
        overdue_tasks:
            List of overdue task dictionaries.

        Returns
        -------
        bool
            True if notification is actively displayed, False otherwise.
        """
        current_ids = {t["id"] for t in overdue_tasks if "id" in t}

        # If no overdue tasks exist, hide immediately and clear state
        if not current_ids:
            self._overdue_tasks = []
            self._last_overdue_ids.clear()
            self._dismissed = False
            self.hide()
            return False

        # If condition changed (different tasks), reset dismissed flag
        if current_ids != self._last_overdue_ids:
            self._dismissed = False
            self._last_overdue_ids = set(current_ids)

        self._overdue_tasks = list(overdue_tasks)

        # Do not spam if already dismissed for this exact set
        if self._dismissed:
            self.hide()
            return False

        # Construct informative, clean message
        count = len(overdue_tasks)
        if count == 1:
            title = overdue_tasks[0].get("title", "Untitled")
            msg = f"1 task is overdue: \"{title}\""
        elif count <= 3:
            titles = [f'"{t.get("title", "")}"' for t in overdue_tasks]
            msg = f"{count} tasks are overdue: {', '.join(titles)}"
        else:
            first_three = [f'"{t.get("title", "")}"' for t in overdue_tasks[:3]]
            remaining = count - 3
            msg = f"{count} tasks are overdue: {', '.join(first_three)} and {remaining} more"

        self.message_label.setText(msg)
        self.show()
        return True

    def apply_theme(self, theme: str) -> None:
        """Update banner styling to match Light or Dark theme."""
        self._current_theme = theme.lower()
        if self._current_theme == THEME_DARK:
            self.setStyleSheet(_DARK_BANNER_STYLE)
        else:
            self.setStyleSheet(_LIGHT_BANNER_STYLE)
