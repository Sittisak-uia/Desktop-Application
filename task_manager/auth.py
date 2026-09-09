"""Authentication helpers for SQLite Task Manager PRO.

Password hashing uses PBKDF2-HMAC-SHA256 with a random 16-byte salt
and 100 000 iterations.  Passwords are never stored or compared as
plaintext.  Hash comparison uses ``hmac.compare_digest`` to prevent
timing attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from task_manager.database import get_user_by_username

_HASH_ITERATIONS = 100_000
_SALT_LENGTH = 16


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, str]:
    """Hash *password* with PBKDF2-HMAC-SHA256.

    Parameters
    ----------
    password:
        The plaintext password to hash.
    salt:
        An optional 16-byte salt.  When ``None`` a new random salt is
        generated.

    Returns
    -------
    tuple[bytes, str]
        ``(salt_bytes, hex_digest)`` — the salt used and the
        hex-encoded derived key.
    """
    if salt is None:
        salt = os.urandom(_SALT_LENGTH)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _HASH_ITERATIONS,
    )
    return salt, dk.hex()


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify *password* against a stored hash and hex-encoded salt.

    Parameters
    ----------
    password:
        The plaintext password supplied by the user.
    stored_hash:
        The hex-encoded hash stored in the database.
    salt:
        The hex-encoded salt stored in the database.

    Returns
    -------
    bool
        ``True`` when the password matches, ``False`` otherwise.
    """
    salt_bytes = bytes.fromhex(salt)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        _HASH_ITERATIONS,
    )
    return hmac.compare_digest(dk.hex(), stored_hash)


def authenticate_user(
    username: str,
    password: str,
    conn=None,
) -> bool:
    """Authenticate *username* / *password* against the database.

    Parameters
    ----------
    username:
        The username to look up.
    password:
        The plaintext password to verify.
    conn:
        An optional SQLite connection.  When ``None`` the default
        database is used.

    Returns
    -------
    bool
        ``True`` only when the user exists **and** the password is
        correct.  Returns ``False`` for unknown users or wrong
        passwords — no distinction is exposed to the caller.
    """
    user = get_user_by_username(username, conn=conn)
    if user is None:
        return False
    return verify_password(password, user["password_hash"], user["salt"])
