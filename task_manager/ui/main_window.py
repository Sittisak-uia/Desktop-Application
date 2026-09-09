"""Main application window for SQLite Task Manager PRO.

Provides the sidebar navigation shell and a QStackedWidget content
area.  Each page is a placeholder that will be replaced with real
widgets in later phases.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QLabel,
)

from task_manager.database import get_overdue_tasks
from task_manager.ui.categories import CategoriesWidget
from task_manager.ui.dashboard import DashboardWidget
from task_manager.ui.notifications import NotificationBanner
from task_manager.ui.settings import SettingsWidget
from task_manager.ui.task_list import TaskListWidget
from task_manager.ui.theme import (
    get_content_stack_style,
    get_current_theme,
    get_sidebar_style,
)
from task_manager.ui.trash import TrashWidget

_SIDEBAR_WIDTH = 200

_NAV_ITEMS: list[tuple[str, str]] = [
    ("Dashboard", "Dashboard"),
    ("Tasks", "Tasks"),
    ("Categories", "Categories"),
    ("Trash", "Trash"),
    ("Settings", "Settings"),
]

_SIDEBAR_STYLE = """
    QWidget#sidebar {
        background-color: #2c3e50;
    }
"""

_BTN_NORMAL = """
    QPushButton {
        background-color: transparent;
        color: #bdc3c7;
        border: none;
        text-align: left;
        padding: 12px 18px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #34495e;
        color: white;
    }
"""

_BTN_ACTIVE = """
    QPushButton {
        background-color: #3498db;
        color: white;
        border: none;
        text-align: left;
        padding: 12px 18px;
        font-size: 13px;
        font-weight: bold;
    }
"""


class MainWindow(QMainWindow):
    """Top-level window with a sidebar and stacked content area."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Task Manager PRO")
        self.setMinimumSize(800, 600)
        self.resize(1024, 700)

        self._current_theme: str = get_current_theme()
        self._nav_buttons: list[QPushButton] = []

        self._build_ui()
        self._connect_signals()
        self._set_active_button(0)
        self.apply_theme(self._current_theme)
        self.check_overdue_notifications()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Sidebar ----
        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(_SIDEBAR_WIDTH)
        self._sidebar.setStyleSheet(_SIDEBAR_STYLE)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # App title in sidebar
        sidebar_title = QLabel("Task Manager")
        sidebar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        sidebar_title.setStyleSheet("color: white; padding: 18px 0 14px 0;")
        sidebar_title.setFixedHeight(56)
        sidebar_layout.addWidget(sidebar_title)

        # Separator line
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #34495e;")
        sidebar_layout.addWidget(sep)

        # Navigation buttons
        for label, _page_name in _NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName(f"nav_{_page_name.lower()}")
            btn.setStyleSheet(_BTN_NORMAL)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(False)
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addStretch()

        root.addWidget(self._sidebar)

        # ---- Content area ----
        self._content_container = QWidget()
        self._content_container.setObjectName("content_container")
        content_layout = QVBoxLayout(self._content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Notification banner for overdue tasks
        self.notification_banner = NotificationBanner(
            parent=self,
            on_view_tasks=self._go_to_tasks,
        )
        content_layout.addWidget(self.notification_banner)

        # Scoped selector (not a bare rule) so the background is NOT
        # inherited into every page descendant -- that would force light
        # backgrounds onto unstyled controls while leaving light text.
        self._stack = QStackedWidget()
        self._stack.setObjectName("content_stack")
        self._stack.setStyleSheet(
            "QStackedWidget#content_stack { background-color: #ecf0f1; }"
        )

        for _label, page_name in _NAV_ITEMS:
            if page_name == "Dashboard":
                page = DashboardWidget()
                page.refresh_btn.clicked.connect(self.check_overdue_notifications)
            elif page_name == "Tasks":
                page = TaskListWidget()
                page.tasks_changed.connect(self.check_overdue_notifications)
            elif page_name == "Categories":
                page = CategoriesWidget()
            elif page_name == "Trash":
                page = TrashWidget()
                page.tasks_changed.connect(self.check_overdue_notifications)
            elif page_name == "Settings":
                page = SettingsWidget()
            else:
                page = QLabel(f"{page_name} will be implemented in a later phase")
                page.setAlignment(Qt.AlignmentFlag.AlignCenter)
                page.setFont(QFont("Segoe UI", 14))
                page.setStyleSheet("color: #7f8c8d;")
            page.setObjectName(f"page_{page_name.lower()}")
            self._stack.addWidget(page)

        content_layout.addWidget(self._stack, stretch=1)
        root.addWidget(self._content_container, stretch=1)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        for idx, btn in enumerate(self._nav_buttons):
            btn.clicked.connect(lambda _checked, i=idx: self._navigate_to(i))

    def _navigate_to(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._set_active_button(index)
        widget = self._stack.widget(index)
        # Reload the destination page so its data is never stale (e.g. a
        # category deleted on another page must instantly show as
        # "Uncategorized" in the Tasks list).
        if widget is not None and hasattr(widget, "refresh") and callable(widget.refresh):
            widget.refresh()
        self.check_overdue_notifications()

    def _go_to_tasks(self) -> None:
        """Switch to Tasks page when user clicks 'View Tasks' on notification."""
        self._navigate_to(1)

    def check_overdue_notifications(self) -> list[dict]:
        """Fetch overdue tasks from the database and update the notification banner."""
        try:
            overdue_tasks = get_overdue_tasks()
        except Exception:
            overdue_tasks = []
        if hasattr(self, "notification_banner"):
            self.notification_banner.check_and_notify(overdue_tasks)
        return overdue_tasks

    def refresh_all_pages(self) -> None:
        """Reload all page widgets and update overdue notifications."""
        if hasattr(self, "_stack"):
            for i in range(self._stack.count()):
                page = self._stack.widget(i)
                if page is not None and hasattr(page, "refresh") and callable(page.refresh):
                    page.refresh()
        self.check_overdue_notifications()

    def _set_active_button(self, active: int) -> None:
        for idx, btn in enumerate(self._nav_buttons):
            if idx == active:
                btn.setStyleSheet(_BTN_ACTIVE)
            else:
                btn.setStyleSheet(_BTN_NORMAL)

    # ------------------------------------------------------------------
    # Theme management
    # ------------------------------------------------------------------

    def apply_theme(self, theme_name: str) -> None:
        """Apply theme (light/dark) to MainWindow shell and all page widgets."""
        self._current_theme = theme_name.lower()
        if hasattr(self, "_sidebar"):
            self._sidebar.setStyleSheet(get_sidebar_style(self._current_theme))
        if hasattr(self, "_content_container"):
            bg = "#1e272e" if self._current_theme == "dark" else "#ecf0f1"
            self._content_container.setStyleSheet(
                f"QWidget#content_container {{ background-color: {bg}; }}"
            )
        if hasattr(self, "_stack"):
            self._stack.setStyleSheet(get_content_stack_style(self._current_theme))
            for i in range(self._stack.count()):
                page = self._stack.widget(i)
                if page is not None and hasattr(page, "apply_theme") and callable(page.apply_theme):
                    page.apply_theme(self._current_theme)
        if hasattr(self, "notification_banner"):
            self.notification_banner.apply_theme(self._current_theme)

    # ------------------------------------------------------------------
    # Public helpers for future phases
    # ------------------------------------------------------------------

    def set_page_widget(self, index: int, widget: QWidget) -> None:
        """Replace the placeholder at *index* with a real widget."""
        old = self._stack.widget(index)
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.insertWidget(index, widget)
