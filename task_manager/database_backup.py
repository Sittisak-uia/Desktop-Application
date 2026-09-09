"""Database Backup and Restore module for SQLite Task Manager PRO.

Implements Phase 14 requirements:
- Backup active tasks.db using SQLite's native backup API (sqlite3.Connection.backup).
- Automatic timestamped safety backup created before any restore operation.
- Comprehensive database validation (magic header, integrity check, required tables, required task columns).
- Atomic restore strategy ensuring current database is never corrupted or deleted on failure.
- Complete error handling (file not found, non-SQLite, missing tables/columns, corruption, permission errors).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from task_manager.database import get_db_path, initialize_database

REQUIRED_TABLES = {"users", "categories", "tasks"}
REQUIRED_TASK_COLUMNS = {
    "id",
    "title",
    "description",
    "priority",
    "category_id",
    "due_date",
    "status",
    "created_at",
    "completed_at",
    "is_deleted",
}


def generate_backup_filename() -> str:
    """Generate default timestamped backup filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"tasks_backup_{timestamp}.db"


def generate_safety_backup_filename() -> str:
    """Generate timestamped filename for pre-restore safety backup."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"tasks_safety_backup_{timestamp}.db"


def validate_backup_file(file_path: str) -> tuple[bool, str]:
    """Verify that *file_path* is a valid SQLite database with Task Manager schema.

    Returns
    -------
    tuple[bool, str]
        (True, "OK message") if valid; (False, "Error reason") if invalid.
    """
    if not file_path or not isinstance(file_path, str):
        return False, "Invalid file path."

    if not os.path.exists(file_path):
        return False, f"File does not exist: {file_path}"

    if not os.path.isfile(file_path):
        return False, f"Specified path is not a regular file: {file_path}"

    # Check minimum file size
    try:
        size = os.path.getsize(file_path)
    except OSError as exc:
        return False, f"Unable to read file size: {exc}"

    if size < 100:
        return False, "File is not a valid SQLite database (file too small)."

    # Check 16-byte SQLite magic header
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
        if header != b"SQLite format 3\x00":
            return False, "File is not a valid SQLite database (invalid header)."
    except PermissionError:
        return False, f"Permission denied accessing file: {file_path}"
    except OSError as exc:
        return False, f"I/O error reading file: {exc}"

    # Open connection and inspect schema
    conn = None
    try:
        conn = sqlite3.connect(file_path)
        conn.row_factory = sqlite3.Row

        # Integrity check
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if not row or str(row[0]).lower() != "ok":
            detail = row[0] if row else "unknown error"
            return False, f"Database integrity check failed: {detail}"

        # Verify required tables
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        existing_tables = {r["name"] for r in rows}
        missing_tables = REQUIRED_TABLES - existing_tables
        if missing_tables:
            return False, f"Missing required table(s): {', '.join(sorted(missing_tables))}."

        # Verify required task columns
        cols = conn.execute("PRAGMA table_info(tasks)").fetchall()
        existing_cols = {c["name"] for c in cols}
        missing_cols = REQUIRED_TASK_COLUMNS - existing_cols
        if missing_cols:
            return False, f"Tasks table missing required column(s): {', '.join(sorted(missing_cols))}."

        # Verify tables are queryable
        conn.execute("SELECT COUNT(*) FROM users").fetchone()
        conn.execute("SELECT COUNT(*) FROM categories").fetchone()
        conn.execute("SELECT COUNT(*) FROM tasks").fetchone()

        return True, "Database is valid."
    except sqlite3.DatabaseError as exc:
        return False, f"Database error or corrupted file: {exc}"
    except Exception as exc:
        return False, f"Validation failed: {exc}"
    finally:
        if conn is not None:
            conn.close()


def backup_database(destination_path: str, source_db_path: str | None = None) -> str:
    """Create a backup of the database to *destination_path* using SQLite backup API.

    Parameters
    ----------
    destination_path:
        Target .db path where the backup will be saved.
    source_db_path:
        Optional path to source database. Defaults to application tasks.db.

    Returns
    -------
    str
        Absolute path to the created backup file.
    """
    if not destination_path or not isinstance(destination_path, str):
        raise ValueError("Destination path must be a non-empty string.")

    src_path = get_db_path(source_db_path)
    if not os.path.exists(src_path):
        # If source DB does not exist on disk yet, initialize it
        init_conn = sqlite3.connect(src_path)
        init_conn.row_factory = sqlite3.Row
        init_conn.execute("PRAGMA foreign_keys = ON")
        initialize_database(init_conn)
        init_conn.close()

    dest_dir = os.path.dirname(os.path.abspath(destination_path))
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    src_conn = None
    dest_conn = None
    try:
        src_conn = sqlite3.connect(src_path)
        dest_conn = sqlite3.connect(destination_path)
        src_conn.backup(dest_conn)
    finally:
        if dest_conn is not None:
            dest_conn.close()
        if src_conn is not None:
            src_conn.close()

    # Verify that the created backup is a valid SQLite database
    valid, msg = validate_backup_file(destination_path)
    if not valid:
        raise RuntimeError(f"Backup file created but validation failed: {msg}")

    return os.path.abspath(destination_path)


def create_safety_backup(source_db_path: str | None = None, backup_dir: str | None = None) -> str:
    """Create an automatic pre-restore safety backup of the current database.

    Returns
    -------
    str
        Path to the created safety backup file.
    """
    src_path = get_db_path(source_db_path)
    target_dir = backup_dir if backup_dir else os.path.dirname(src_path)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    safety_filename = generate_safety_backup_filename()
    safety_path = os.path.join(target_dir, safety_filename)
    return backup_database(safety_path, source_db_path=src_path)


def restore_database(
    backup_path: str,
    target_db_path: str | None = None,
) -> tuple[bool, str, str | None]:
    """Safely restore database from *backup_path* into *target_db_path*.

    Process:
    1. Validates *backup_path* schema and integrity. Rejects invalid files before modifying anything.
    2. Creates an automatic pre-restore safety backup of the active database.
    3. Restores into a temporary file first and validates it.
    4. Applies the verified data to *target_db_path* using SQLite backup API.
    5. Leaves safety backup intact on disk so user can recover if desired.

    Returns
    -------
    tuple[bool, str, str | None]
        (success, status_message, safety_backup_path_or_None)
    """
    # Step 1: Validate candidate backup file
    valid, msg = validate_backup_file(backup_path)
    if not valid:
        return False, f"Restore rejected: {msg}", None

    target_path = get_db_path(target_db_path)
    target_dir = os.path.dirname(target_path)
    if target_dir and not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    # Step 2: Create pre-restore safety backup of the active database
    safety_path = None
    if os.path.exists(target_path):
        try:
            safety_path = create_safety_backup(source_db_path=target_path)
        except Exception as exc:
            return False, f"Failed to create pre-restore safety backup: {exc}. Restore aborted.", None

    # Step 3: Restore through verified staging
    temp_target = os.path.join(
        target_dir,
        f"tasks_restore_tmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
    )

    try:
        # Copy from backup_path into temp_target
        src_conn = sqlite3.connect(backup_path)
        tmp_conn = sqlite3.connect(temp_target)
        try:
            src_conn.backup(tmp_conn)
        finally:
            tmp_conn.close()
            src_conn.close()

        # Validate staged database
        valid_tmp, tmp_msg = validate_backup_file(temp_target)
        if not valid_tmp:
            if os.path.exists(temp_target):
                try:
                    os.unlink(temp_target)
                except OSError:
                    pass
            return False, f"Staged database validation failed: {tmp_msg}", safety_path

        # Copy from temp_target into target_path
        tmp_conn = sqlite3.connect(temp_target)
        target_conn = sqlite3.connect(target_path)
        try:
            tmp_conn.backup(target_conn)
        finally:
            target_conn.close()
            tmp_conn.close()

        # Clean up temporary file
        if os.path.exists(temp_target):
            try:
                os.unlink(temp_target)
            except OSError:
                pass

        # Verify target database
        test_conn = sqlite3.connect(target_path)
        test_conn.execute("PRAGMA foreign_keys = ON")
        test_conn.execute("PRAGMA integrity_check")
        test_conn.close()

        return True, "Database restored successfully.", safety_path

    except Exception as exc:
        if os.path.exists(temp_target):
            try:
                os.unlink(temp_target)
            except OSError:
                pass
        return False, f"Restore failed: {exc}", safety_path
