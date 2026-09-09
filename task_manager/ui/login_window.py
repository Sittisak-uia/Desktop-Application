"""Login window for SQLite Task Manager PRO.

Displays a centered login form with username, password, and a Login
button.  Authentication is delegated to ``task_manager.auth``; no SQL
runs inside this module.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from task_manager.auth import authenticate_user


class LoginWindow(QDialog):
    """Modal login dialog that blocks until the user logs in or cancels."""

    def showEvent(self, event) -> None:
        super().showEvent(event)
        app = QApplication.instance()
        if app:
            app.setActiveWindow(self)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Task Manager PRO - Login")
        self.setFixedSize(420, 340)
        self.setModal(True)

        self._authenticated = False

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(12)

        # ---- Title ----
        title = QLabel("Task Manager PRO")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; padding-bottom: 4px;")
        root.addWidget(title)

        subtitle = QLabel("Sign in to your account")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 12px; padding-bottom: 10px;")
        root.addWidget(subtitle)

        # ---- Username ----
        username_label = QLabel("Username")
        username_label.setStyleSheet("color: #34495e; font-size: 12px;")
        root.addWidget(username_label)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        self.username_input.setMinimumHeight(36)
        self.username_input.setStyleSheet(
            "QLineEdit {"
            "  background-color: white;"
            "  color: #2c3e50;"
            "  border: 1px solid #bdc3c7;"
            "  border-radius: 4px;"
            "  padding: 6px 10px;"
            "  font-size: 13px;"
            "}"
            "QLineEdit::placeholder {"
            "  color: #95a5a6;"
            "}"
            "QLineEdit:focus {"
            "  border: 1px solid #3498db;"
            "}"
        )
        root.addWidget(self.username_input)

        # ---- Password ----
        password_label = QLabel("Password")
        password_label.setStyleSheet("color: #34495e; font-size: 12px;")
        root.addWidget(password_label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setMinimumHeight(36)
        self.password_input.setStyleSheet(
            "QLineEdit {"
            "  background-color: white;"
            "  color: #2c3e50;"
            "  border: 1px solid #bdc3c7;"
            "  border-radius: 4px;"
            "  padding: 6px 10px;"
            "  font-size: 13px;"
            "}"
            "QLineEdit::placeholder {"
            "  color: #95a5a6;"
            "}"
            "QLineEdit:focus {"
            "  border: 1px solid #3498db;"
            "}"
        )
        root.addWidget(self.password_input)

        # ---- Error label (hidden by default) ----
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet(
            "color: #e74c3c; font-size: 12px; font-weight: bold; padding: 2px;"
        )
        self.error_label.setVisible(False)
        root.addWidget(self.error_label)

        # ---- Login button ----
        self.login_button = QPushButton("Login")
        self.login_button.setMinimumHeight(40)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.setStyleSheet(
            "QPushButton {"
            "  background-color: #3498db;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 4px;"
            "  font-size: 14px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "  background-color: #2980b9;"
            "}"
            "QPushButton:pressed {"
            "  background-color: #21618c;"
            "}"
        )
        root.addWidget(self.login_button)

        root.addStretch()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.login_button.clicked.connect(self._on_login_clicked)
        self.password_input.returnPressed.connect(self._on_login_clicked)
        self.username_input.returnPressed.connect(
            lambda: self.password_input.setFocus()
        )

    def _on_login_clicked(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        if authenticate_user(username, password):
            self._authenticated = True
            self.accept()
        else:
            self._show_error("Invalid username or password.")
            self.password_input.clear()
            self.password_input.setFocus()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def _clear_error(self) -> None:
        self.error_label.setText("")
        self.error_label.setVisible(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        """``True`` after a successful login."""
        return self._authenticated
