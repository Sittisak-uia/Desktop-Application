"""Data models for SQLite Task Manager PRO.

Plain dataclasses representing the core entities: User, Category, and Task.
No database logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class User:
    """Represents a login user."""

    id: int = 0
    username: str = ""
    password_hash: str = ""
    salt: str = ""


@dataclass
class Category:
    """Represents a task category."""

    id: int = 0
    name: str = ""


@dataclass
class Task:
    """Represents a single task."""

    id: int = 0
    title: str = ""
    description: str = ""
    priority: str = "MEDIUM"
    category_id: int | None = None
    due_date: str | None = None
    status: str = "PENDING"
    is_deleted: bool = False
    created_at: str = ""
    completed_at: str | None = None
