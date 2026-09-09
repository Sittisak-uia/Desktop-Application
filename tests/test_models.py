"""Unit tests for task_manager.models module.

Uses the standard library unittest only -- no pytest dependency.
"""

import unittest

from task_manager.models import Category, Task, User


class TestUser(unittest.TestCase):
    def test_defaults(self) -> None:
        user = User()
        self.assertEqual(user.id, 0)
        self.assertEqual(user.username, "")
        self.assertEqual(user.password_hash, "")
        self.assertEqual(user.salt, "")

    def test_custom_values(self) -> None:
        user = User(id=1, username="alice", password_hash="abc123", salt="ff")
        self.assertEqual(user.id, 1)
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.password_hash, "abc123")
        self.assertEqual(user.salt, "ff")

    def test_equality(self) -> None:
        a = User(id=1, username="a")
        b = User(id=1, username="a")
        self.assertEqual(a, b)

    def test_inequality(self) -> None:
        a = User(id=1, username="a")
        b = User(id=2, username="b")
        self.assertNotEqual(a, b)


class TestCategory(unittest.TestCase):
    def test_defaults(self) -> None:
        cat = Category()
        self.assertEqual(cat.id, 0)
        self.assertEqual(cat.name, "")

    def test_custom_values(self) -> None:
        cat = Category(id=5, name="Work")
        self.assertEqual(cat.id, 5)
        self.assertEqual(cat.name, "Work")

    def test_equality(self) -> None:
        a = Category(id=1, name="X")
        b = Category(id=1, name="X")
        self.assertEqual(a, b)


class TestTask(unittest.TestCase):
    def test_defaults(self) -> None:
        task = Task()
        self.assertEqual(task.id, 0)
        self.assertEqual(task.title, "")
        self.assertEqual(task.description, "")
        self.assertEqual(task.priority, "MEDIUM")
        self.assertIsNone(task.category_id)
        self.assertIsNone(task.due_date)
        self.assertEqual(task.status, "PENDING")
        self.assertFalse(task.is_deleted)
        self.assertEqual(task.created_at, "")
        self.assertIsNone(task.completed_at)

    def test_custom_values(self) -> None:
        task = Task(
            id=10,
            title="Buy milk",
            description="2% preferred",
            priority="LOW",
            category_id=3,
            due_date="2026-09-15",
            status="COMPLETED",
            is_deleted=True,
            created_at="2026-01-01T10:00:00",
            completed_at="2026-01-02T12:00:00",
        )
        self.assertEqual(task.id, 10)
        self.assertEqual(task.title, "Buy milk")
        self.assertEqual(task.description, "2% preferred")
        self.assertEqual(task.priority, "LOW")
        self.assertEqual(task.category_id, 3)
        self.assertEqual(task.due_date, "2026-09-15")
        self.assertEqual(task.status, "COMPLETED")
        self.assertTrue(task.is_deleted)
        self.assertEqual(task.created_at, "2026-01-01T10:00:00")
        self.assertEqual(task.completed_at, "2026-01-02T12:00:00")

    def test_equality(self) -> None:
        a = Task(id=1, title="X")
        b = Task(id=1, title="X")
        self.assertEqual(a, b)

    def test_inequality(self) -> None:
        a = Task(id=1, title="X")
        b = Task(id=2, title="X")
        self.assertNotEqual(a, b)

    def test_is_deleted_default_false(self) -> None:
        task = Task()
        self.assertFalse(task.is_deleted)

    def test_category_id_can_be_none(self) -> None:
        task = Task(category_id=None)
        self.assertIsNone(task.category_id)

    def test_due_date_can_be_none(self) -> None:
        task = Task(due_date=None)
        self.assertIsNone(task.due_date)

    def test_completed_at_can_be_none(self) -> None:
        task = Task(completed_at=None)
        self.assertIsNone(task.completed_at)


if __name__ == "__main__":
    unittest.main()
