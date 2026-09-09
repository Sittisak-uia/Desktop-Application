"""Unit tests for task_manager.auth module.

Uses the standard library unittest only -- no pytest dependency.
Tests that require database interaction use a temporary SQLite database
so the production tasks.db is never touched.
"""

import os
import sqlite3
import tempfile
import unittest

from task_manager.auth import authenticate_user, hash_password, verify_password
from task_manager.database import (
    initialize_database,
    seed_default_user,
)


def _make_temp_db() -> tuple[str, sqlite3.Connection]:
    """Create a temporary file-based DB with schema and default admin.

    Returns ``(file_path, connection)``.  The caller is responsible for
    closing the connection and deleting the file.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    seed_default_user(conn)
    return path, conn


class TestHashPassword(unittest.TestCase):
    def test_hash_password_returns_salt_and_hash(self) -> None:
        salt, digest = hash_password("secret")
        self.assertIsInstance(salt, bytes)
        self.assertEqual(len(salt), 16)
        self.assertIsInstance(digest, str)
        self.assertTrue(len(digest) > 0)

    def test_hash_password_generates_random_salt(self) -> None:
        _, salt1 = hash_password("same_password")
        _, salt2 = hash_password("same_password")
        self.assertNotEqual(salt1, salt2)

    def test_hash_password_returns_different_hash_for_new_salt(self) -> None:
        # With different salts the hex digests must differ
        salt_a, hash_a = hash_password("pw")
        salt_b, hash_b = hash_password("pw")
        self.assertNotEqual(hash_a, hash_b)

    def test_hash_deterministic_with_same_salt(self) -> None:
        salt, hash1 = hash_password("pw")
        _, hash2 = hash_password("pw", salt=salt)
        self.assertEqual(hash1, hash2)

    def test_hash_with_explicit_salt(self) -> None:
        fixed_salt = b"\x00" * 16
        salt_out, digest = hash_password("pw", salt=fixed_salt)
        self.assertEqual(salt_out, fixed_salt)
        self.assertIsInstance(digest, str)

    def test_password_is_not_stored_as_plaintext(self) -> None:
        password = "my_secret_password"
        _, digest = hash_password(password)
        self.assertNotIn(password, digest)
        self.assertNotEqual(digest, password)


class TestVerifyPassword(unittest.TestCase):
    def test_verify_correct_password(self) -> None:
        salt_bytes, digest = hash_password("correct")
        self.assertTrue(
            verify_password("correct", digest, salt_bytes.hex())
        )

    def test_verify_wrong_password(self) -> None:
        salt_bytes, digest = hash_password("correct")
        self.assertFalse(
            verify_password("wrong", digest, salt_bytes.hex())
        )

    def test_verify_wrong_salt(self) -> None:
        salt_bytes, digest = hash_password("pw")
        wrong_salt = b"\xff" * 16
        self.assertFalse(
            verify_password("pw", digest, wrong_salt.hex())
        )

    def test_verify_empty_password(self) -> None:
        salt_bytes, digest = hash_password("")
        self.assertTrue(verify_password("", digest, salt_bytes.hex()))

    def test_verify_after_roundtrip(self) -> None:
        """Hash then verify — the full round-trip."""
        for pw in ("a", "hello world", "P@ssw0rd!123"):
            salt_bytes, digest = hash_password(pw)
            self.assertTrue(verify_password(pw, digest, salt_bytes.hex()))


class TestAuthenticateUser(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path, self.conn = _make_temp_db()

    def tearDown(self) -> None:
        self.conn.close()
        os.unlink(self.db_path)

    def test_authenticate_existing_user(self) -> None:
        self.assertTrue(authenticate_user("admin", "admin", conn=self.conn))

    def test_authenticate_wrong_password(self) -> None:
        self.assertFalse(authenticate_user("admin", "wrong_password", conn=self.conn))

    def test_authenticate_unknown_user(self) -> None:
        self.assertFalse(authenticate_user("nobody", "admin", conn=self.conn))

    def test_authenticate_empty_password(self) -> None:
        self.assertFalse(authenticate_user("admin", "", conn=self.conn))

    def test_authenticate_is_case_sensitive(self) -> None:
        self.assertFalse(authenticate_user("Admin", "admin", conn=self.conn))
        self.assertFalse(authenticate_user("admin", "Admin", conn=self.conn))


if __name__ == "__main__":
    unittest.main()
