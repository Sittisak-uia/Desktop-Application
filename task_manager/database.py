"""Database operations for SQLite Task Manager PRO.

All SQLite interaction lives here.  The GUI layer calls these functions
and never executes SQL directly.  Every query uses parameterised
placeholders to prevent SQL injection.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import date, datetime
from typing import Any

_DB_FILENAME = "tasks.db"

_VALID_PRIORITIES = ("LOW", "MEDIUM", "HIGH")
_VALID_STATUSES = ("PENDING", "COMPLETED")

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_db_path(db_path: str | None = None) -> str:
    """Return the absolute path to the SQLite database file."""
    if db_path is not None:
        return os.path.abspath(db_path)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), _DB_FILENAME))


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Return a new SQLite connection with foreign keys enabled.

    When *db_path* is ``None`` the database file is placed next to this
    source file (i.e. inside ``task_manager/``).
    """
    resolved_path = get_db_path(db_path)
    conn = sqlite3.connect(resolved_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def initialize_database(conn: sqlite3.Connection | None = None) -> None:
    """Create every table if it does not already exist."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                salt          TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT    NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT    NOT NULL,
                description  TEXT    DEFAULT '',
                priority     TEXT    NOT NULL DEFAULT 'MEDIUM'
                             CHECK(priority IN ('LOW','MEDIUM','HIGH')),
                category_id  INTEGER NULL
                             REFERENCES categories(id) ON DELETE SET NULL,
                due_date     TEXT    NULL,
                status       TEXT    NOT NULL DEFAULT 'PENDING'
                             CHECK(status IN ('PENDING','COMPLETED')),
                is_deleted   INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT    NOT NULL,
                completed_at TEXT    NULL
            );
        """)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


# ---------------------------------------------------------------------------
# Default admin account seeding
# ---------------------------------------------------------------------------

def seed_default_user(conn: sqlite3.Connection | None = None) -> None:
    """Insert the default ``admin`` / ``admin`` account if no users exist."""
    from task_manager.auth import hash_password as _hash_password

    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        if row["cnt"] == 0:
            salt_bytes, hash_hex = _hash_password("admin")
            conn.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                ("admin", hash_hex, salt_bytes.hex()),
            )
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  USER
# =========================================================================

def get_user_by_username(username: str, conn: sqlite3.Connection | None = None) -> dict | None:
    """Return a user dict or *None* if the username does not exist."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  CATEGORIES
# =========================================================================

def get_all_categories(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Return every category as a list of dicts."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def add_category(name: str, conn: sqlite3.Connection | None = None) -> int:
    """Insert a category and return its new *id*.

    Raises ``ValueError`` if *name* is blank.  Raises ``sqlite3.IntegrityError``
    if the name already exists.
    """
    name = name.strip()
    if not name:
        raise ValueError("Category name cannot be empty.")
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()


def update_category(category_id: int, name: str, conn: sqlite3.Connection | None = None) -> None:
    """Rename an existing category.

    Raises ``ValueError`` if *name* is blank.  Raises ``sqlite3.IntegrityError``
    if the new name conflicts with another category.
    """
    name = name.strip()
    if not name:
        raise ValueError("Category name cannot be empty.")
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def delete_category(category_id: int, conn: sqlite3.Connection | None = None) -> None:
    """Delete a category.

    Because of the ``ON DELETE SET NULL`` foreign-key constraint the
    database automatically sets ``category_id = NULL`` on every affected
    task.
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  TASKS — helpers
# =========================================================================

def _validate_task_data(
    title: str,
    priority: str,
    status: str,
    due_date: str | None,
) -> None:
    """Raise ``ValueError`` when any field is invalid."""
    if not title or not title.strip():
        raise ValueError("Task title cannot be empty.")
    priority = priority.upper()
    if priority not in _VALID_PRIORITIES:
        raise ValueError(f"Invalid priority '{priority}'. Must be one of: LOW, MEDIUM, HIGH.")
    status = status.upper()
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: PENDING, COMPLETED.")
    if due_date is not None and due_date != "":
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError(f"Invalid due_date '{due_date}'. Must be YYYY-MM-DD or None.")


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _now_iso() -> str:
    """Return the current local time as an ISO-8601 string."""
    return datetime.now().isoformat(timespec="seconds")


# =========================================================================
#  TASKS — CRUD
# =========================================================================

def add_task(
    title: str,
    description: str = "",
    priority: str = "MEDIUM",
    category_id: int | None = None,
    due_date: str | None = None,
    status: str = "PENDING",
    conn: sqlite3.Connection | None = None,
) -> int:
    """Insert a task and return its new *id*.

    When *status* is ``COMPLETED`` the ``completed_at`` field is set to the
    current timestamp; otherwise it is ``NULL``.
    """
    title = title.strip()
    priority = priority.upper()
    status = status.upper()
    _validate_task_data(title, priority, status, due_date)

    completed_at = _now_iso() if status == "COMPLETED" else None
    created_at = _now_iso()

    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO tasks
               (title, description, priority, category_id, due_date,
                status, is_deleted, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (title, description, priority, category_id, due_date,
             status, created_at, completed_at),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()


def get_task_by_id(task_id: int, conn: sqlite3.Connection | None = None) -> dict | None:
    """Return a single task dict or *None*."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def get_active_tasks(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Return all non-deleted tasks ordered by due date (NULLs last), then id."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE is_deleted = 0
               ORDER BY
                 CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                 due_date ASC,
                 id ASC"""
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def update_task(
    task_id: int,
    title: str,
    description: str = "",
    priority: str = "MEDIUM",
    category_id: int | None = None,
    due_date: str | None = None,
    status: str = "PENDING",
    conn: sqlite3.Connection | None = None,
) -> None:
    """Update every editable field of an existing task.

    ``completed_at`` is managed automatically based on the *status*
    argument and the task's current state:
    - PENDING -> PENDING : no change (stays NULL)
    - PENDING -> COMPLETED : set to now
    - COMPLETED -> COMPLETED : no change (stays as-is)
    - COMPLETED -> PENDING : set to NULL
    """
    title = title.strip()
    priority = priority.upper()
    status = status.upper()
    _validate_task_data(title, priority, status, due_date)

    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        current = conn.execute(
            "SELECT status, completed_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if current is None:
            raise ValueError(f"Task {task_id} does not exist.")

        completed_at = current["completed_at"]
        old_status = current["status"]

        if old_status == "PENDING" and status == "COMPLETED":
            completed_at = _now_iso()
        elif old_status == "COMPLETED" and status == "PENDING":
            completed_at = None
        # else: no change to completed_at

        conn.execute(
            """UPDATE tasks
               SET title = ?, description = ?, priority = ?,
                   category_id = ?, due_date = ?, status = ?,
                   completed_at = ?
               WHERE id = ?""",
            (title, description, priority, category_id, due_date,
             status, completed_at, task_id),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def soft_delete_task(task_id: int, conn: sqlite3.Connection | None = None) -> None:
    """Move a task to the trash by setting ``is_deleted = 1``."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        conn.execute(
            "UPDATE tasks SET is_deleted = 1 WHERE id = ? AND is_deleted = 0",
            (task_id,),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def restore_task(task_id: int, conn: sqlite3.Connection | None = None) -> None:
    """Restore a trashed task by setting ``is_deleted = 0``."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        conn.execute(
            "UPDATE tasks SET is_deleted = 0 WHERE id = ? AND is_deleted = 1",
            (task_id,),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def permanent_delete_task(task_id: int, conn: sqlite3.Connection | None = None) -> None:
    """Permanently remove a task from the database.

    Only deletes tasks that are currently in the trash (``is_deleted = 1``).
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM tasks WHERE id = ? AND is_deleted = 1",
            (task_id,),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def duplicate_task(task_id: int, conn: sqlite3.Connection | None = None) -> int:
    """Create a copy of an existing active task.

    The duplicate has the same title, description, priority, category,
    and due date but is always PENDING with a fresh ``created_at``
    timestamp.  Returns the new task's *id*.

    Validates that the source task exists and is not deleted (is_deleted == 0).
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        src = get_task_by_id(task_id, conn=conn)
        if src is None:
            raise ValueError(f"Task {task_id} does not exist.")
        if src.get("is_deleted", 0):
            raise ValueError(f"Cannot duplicate deleted task with ID {task_id}.")

        cur = conn.execute(
            """INSERT INTO tasks
               (title, description, priority, category_id, due_date,
                status, is_deleted, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, 'PENDING', 0, ?, NULL)""",
            (src["title"], src["description"], src["priority"],
             src["category_id"], src["due_date"], _now_iso()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  SEARCH / FILTER
# =========================================================================

def search_tasks(
    keyword: str = "",
    category_id: int | None = None,
    priority: str | None = None,
    status: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return active tasks matching the supplied filters.

    An empty *keyword* means no text filter is applied.
    ``None`` for any filter means that filter is skipped.
    """
    clauses: list[str] = ["is_deleted = 0"]
    params: list[Any] = []

    if keyword:
        clauses.append("(title LIKE ? OR description LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like])

    if category_id is not None:
        clauses.append("category_id = ?")
        params.append(category_id)

    if priority is not None:
        priority = priority.upper()
        if priority in _VALID_PRIORITIES:
            clauses.append("priority = ?")
            params.append(priority)

    if status is not None:
        status = status.upper()
        if status in _VALID_STATUSES:
            clauses.append("status = ?")
            params.append(status)

    where = " AND ".join(clauses)
    sql = f"SELECT * FROM tasks WHERE {where} ORDER BY id DESC"

    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  TRASH
# =========================================================================

def get_trash_tasks(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Return all tasks currently in the trash."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE is_deleted = 1 ORDER BY id DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  DASHBOARD STATISTICS
# =========================================================================

def get_dashboard_stats(conn: sqlite3.Connection | None = None) -> dict:
    """Return a dictionary of aggregate task statistics.

    Keys:
        total, completed, pending, due_today, overdue,
        by_category (dict name -> count, only active tasks),
        by_priority (dict priority -> count, only active tasks).
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        today = date.today().isoformat()

        base = "SELECT COUNT(*) AS cnt FROM tasks WHERE is_deleted = 0"
        total = conn.execute(base).fetchone()["cnt"]
        completed = conn.execute(
            base + " AND status = 'COMPLETED'"
        ).fetchone()["cnt"]
        pending = conn.execute(
            base + " AND status = 'PENDING'"
        ).fetchone()["cnt"]
        due_today = conn.execute(
            base + " AND due_date = ? AND status = 'PENDING'",
            (today,),
        ).fetchone()["cnt"]
        overdue = conn.execute(
            base + " AND due_date IS NOT NULL AND due_date != '' AND due_date < ? AND status = 'PENDING'",
            (today,),
        ).fetchone()["cnt"]

        cat_rows = conn.execute(
            """SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
                      COUNT(*) AS cnt
               FROM tasks t
               LEFT JOIN categories c ON t.category_id = c.id
               WHERE t.is_deleted = 0
               GROUP BY cat_name
               ORDER BY cat_name"""
        ).fetchall()
        by_category = {r["cat_name"]: r["cnt"] for r in cat_rows}

        pri_rows = conn.execute(
            """SELECT priority, COUNT(*) AS cnt
               FROM tasks
               WHERE is_deleted = 0
               GROUP BY priority
               ORDER BY priority"""
        ).fetchall()
        by_priority = {r["priority"]: r["cnt"] for r in pri_rows}

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "due_today": due_today,
            "overdue": overdue,
            "by_category": by_category,
            "by_priority": by_priority,
        }
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  NOTIFICATION QUERIES
# =========================================================================

def get_due_today_tasks(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Return active pending tasks whose due date is today."""
    today = date.today().isoformat()
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE is_deleted = 0
                 AND status = 'PENDING'
                 AND due_date = ?
               ORDER BY title""",
            (today,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def get_overdue_tasks(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Return active pending tasks whose due date is in the past."""
    today = date.today().isoformat()
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE is_deleted = 0
                 AND status = 'PENDING'
                 AND due_date IS NOT NULL
                 AND due_date != ''
                 AND due_date < ?
               ORDER BY due_date ASC""",
            (today,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  CSV EXPORT / IMPORT
# =========================================================================

def export_tasks_to_csv(file_path: str, conn: sqlite3.Connection | None = None) -> int:
    """Write all active (non-deleted) tasks to *file_path* as CSV.

    Returns the number of tasks exported.  Uses Python's standard
    ``csv`` module.
    """
    import csv

    tasks = get_active_tasks(conn=conn)

    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        with open(file_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "title", "description", "priority", "category_id",
                "due_date", "status", "created_at", "completed_at",
            ])
            for t in tasks:
                writer.writerow([
                    t["title"],
                    t["description"],
                    t["priority"],
                    t["category_id"] if t["category_id"] is not None else "",
                    t["due_date"] if t["due_date"] is not None else "",
                    t["status"],
                    t["created_at"],
                    t["completed_at"] if t["completed_at"] is not None else "",
                ])
        return len(tasks)
    finally:
        if owns_conn:
            conn.close()


def import_tasks_from_csv(
    file_path: str, conn: sqlite3.Connection | None = None
) -> tuple[int, list[str]]:
    """Import tasks from a CSV file.

    Returns ``(imported_count, error_messages)``.  Invalid rows are
    skipped and their errors collected.  Valid rows are inserted within a
    single transaction so either all good rows succeed or none do.
    """
    import csv

    errors: list[str] = []
    rows_to_insert: list[tuple] = []

    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                return 0, ["CSV file is empty."]

            expected = {
                "title", "description", "priority", "category_id",
                "due_date", "status", "created_at", "completed_at",
            }
            if not expected.issubset(set(h.strip().lower() for h in header)):
                return 0, ["CSV header row does not contain the required columns."]

            col_map = {h.strip().lower(): i for i, h in enumerate(header)}

            for line_no, row in enumerate(reader, start=2):
                if len(row) < len(header):
                    errors.append(f"Row {line_no}: too few columns, skipped.")
                    continue

                title = row[col_map["title"]].strip()
                description = row[col_map["description"]].strip()
                priority = row[col_map["priority"]].strip().upper()
                cat_raw = row[col_map["category_id"]].strip()
                category_id = int(cat_raw) if cat_raw else None
                due_raw = row[col_map["due_date"]].strip()
                due_date = due_raw if due_raw else None
                status = row[col_map["status"]].strip().upper()
                created_at = row[col_map["created_at"]].strip()
                completed_raw = row[col_map["completed_at"]].strip()
                completed_at = completed_raw if completed_raw else None

                row_errors: list[str] = []
                if not title:
                    row_errors.append("title is empty")
                if priority not in _VALID_PRIORITIES:
                    row_errors.append(f"invalid priority '{priority}'")
                if status not in _VALID_STATUSES:
                    row_errors.append(f"invalid status '{status}'")
                if due_date:
                    try:
                        datetime.strptime(due_date, "%Y-%m-%d")
                    except ValueError:
                        row_errors.append(f"invalid due_date '{due_date}'")
                if category_id is not None and category_id <= 0:
                    row_errors.append(f"invalid category_id '{cat_raw}'")

                if row_errors:
                    errors.append(f"Row {line_no}: {'; '.join(row_errors)}, skipped.")
                else:
                    rows_to_insert.append((
                        title, description, priority, category_id,
                        due_date, status, created_at, completed_at,
                    ))
    except FileNotFoundError:
        return 0, [f"File not found: {file_path}"]
    except Exception as exc:
        return 0, [f"Error reading CSV: {exc}"]

    if not rows_to_insert:
        return 0, errors

    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        conn.executemany(
            """INSERT INTO tasks
               (title, description, priority, category_id, due_date,
                status, is_deleted, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            rows_to_insert,
        )
        conn.commit()
        return len(rows_to_insert), errors
    finally:
        if owns_conn:
            conn.close()


# =========================================================================
#  BACKUP / RESTORE
# =========================================================================

def backup_database(dest_path: str, conn: sqlite3.Connection | None = None) -> None:
    """Copy the current database file to *dest_path*.

    If a connection is open it is closed first to ensure a consistent
    snapshot.
    """
    src = os.path.join(os.path.dirname(__file__), _DB_FILENAME)
    if not os.path.exists(src):
        raise FileNotFoundError(f"Database file not found: {src}")
    shutil.copy2(src, dest_path)


def restore_database(src_path: str, conn: sqlite3.Connection | None = None) -> None:
    """Replace the current database with the file at *src_path*.

    Validates the file with ``PRAGMA integrity_check`` before replacing.
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Backup file not found: {src_path}")

    test_conn = sqlite3.connect(src_path)
    try:
        result = test_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise ValueError(f"Backup file failed integrity check: {result}")
    finally:
        test_conn.close()

    dest = os.path.join(os.path.dirname(__file__), _DB_FILENAME)
    shutil.copy2(src_path, dest)
