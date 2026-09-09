"""CSV Export and Import services for SQLite Task Manager PRO.

Implements Phase 11 requirements:
- Exports active tasks to standard CSV with columns:
  id, title, description, priority, category, due_date, status, created_at, completed_at.
- Excludes soft-deleted tasks (is_deleted = 1).
- Resolves category IDs to category names on export and resolves names back to IDs on import.
- Validates required columns, priority values, status values, and date formats.
- Performs atomic, transactional imports: if validation fails on any row, no rows are inserted.
- Safe duplicate handling: imported tasks always receive new auto-incremented primary keys,
  never overwriting or corrupting existing tasks.
"""

from __future__ import annotations

import csv
import os
import sqlite3
from datetime import datetime

from task_manager.database import (
    add_category,
    get_active_tasks,
    get_all_categories,
    get_connection,
)

CSV_COLUMNS = [
    "id",
    "title",
    "description",
    "priority",
    "category",
    "due_date",
    "status",
    "created_at",
    "completed_at",
]

_VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH"}
_VALID_STATUSES = {"PENDING", "COMPLETED"}


def export_tasks_to_csv(file_path: str, conn: sqlite3.Connection | None = None) -> int:
    """Export all active (non-deleted) tasks to *file_path* in standard CSV format.

    Parameters
    ----------
    file_path:
        Destination CSV file path.
    conn:
        Optional SQLite connection. If None, the default database is used.

    Returns
    -------
    int
        Number of tasks exported.
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        tasks = get_active_tasks(conn=conn)
        categories = get_all_categories(conn=conn)
        cat_map = {c["id"]: c["name"] for c in categories}

        with open(file_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(CSV_COLUMNS)

            for task in tasks:
                cat_id = task.get("category_id")
                cat_name = cat_map.get(cat_id, "Uncategorized") if cat_id else "Uncategorized"
                writer.writerow([
                    task.get("id", ""),
                    task.get("title", ""),
                    task.get("description", "") or "",
                    (task.get("priority") or "MEDIUM").upper(),
                    cat_name,
                    task.get("due_date") or "",
                    (task.get("status") or "PENDING").upper(),
                    task.get("created_at") or "",
                    task.get("completed_at") or "",
                ])

        return len(tasks)
    finally:
        if owns_conn:
            conn.close()


def import_tasks_from_csv(
    file_path: str,
    conn: sqlite3.Connection | None = None,
) -> tuple[int, list[str]]:
    """Import tasks from a CSV file with validation and category resolution.

    Validates all rows prior to insertion. If any row contains validation errors,
    the operation is aborted and 0 rows are inserted, preserving full transactional
    integrity.

    Duplicate tasks are handled non-destructively: every imported task is assigned
    a new auto-incremented task ID, guaranteeing that existing tasks are never
    overwritten.

    Parameters
    ----------
    file_path:
        Path to the CSV file to import.
    conn:
        Optional SQLite connection. If None, the default database is used.

    Returns
    -------
    tuple[int, list[str]]
        (imported_count, list_of_error_messages)
    """
    if not os.path.exists(file_path):
        return 0, [f"File not found: {file_path}"]

    errors: list[str] = []
    parsed_rows: list[dict] = []

    try:
        with open(file_path, "r", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                return 0, ["CSV file is empty."]

            col_map = {col.strip().lower(): i for i, col in enumerate(header)}

            required_cols = {"title", "priority", "status"}
            missing_cols = required_cols - set(col_map.keys())
            if missing_cols:
                return 0, [f"Missing required CSV column(s): {', '.join(sorted(missing_cols))}"]

            for line_no, row in enumerate(reader, start=2):
                # Skip completely blank lines
                if not row or all(c.strip() == "" for c in row):
                    continue

                if len(row) < len(header):
                    errors.append(f"Row {line_no}: too few columns (expected {len(header)}, got {len(row)}).")
                    continue

                title = row[col_map["title"]].strip()
                description = (
                    row[col_map["description"]].strip() if "description" in col_map else ""
                )
                priority_raw = row[col_map["priority"]].strip().upper()
                status_raw = row[col_map["status"]].strip().upper()

                due_raw = (
                    row[col_map["due_date"]].strip() if "due_date" in col_map else ""
                )
                created_raw = (
                    row[col_map["created_at"]].strip() if "created_at" in col_map else ""
                )
                completed_raw = (
                    row[col_map["completed_at"]].strip() if "completed_at" in col_map else ""
                )

                # Category may be provided under 'category' or 'category_id'
                category_raw = ""
                if "category" in col_map:
                    category_raw = row[col_map["category"]].strip()
                elif "category_id" in col_map:
                    category_raw = row[col_map["category_id"]].strip()

                row_errors: list[str] = []

                if not title:
                    row_errors.append("title is required and cannot be empty")

                if priority_raw not in _VALID_PRIORITIES:
                    row_errors.append(f"invalid priority '{priority_raw}' (must be Low, Medium, or High)")

                if status_raw not in _VALID_STATUSES:
                    row_errors.append(f"invalid status '{status_raw}' (must be Pending or Completed)")

                due_date: str | None = None
                if due_raw:
                    try:
                        datetime.strptime(due_raw, "%Y-%m-%d")
                        due_date = due_raw
                    except ValueError:
                        row_errors.append(f"invalid due_date format '{due_raw}' (expected YYYY-MM-DD)")

                if row_errors:
                    errors.append(f"Row {line_no}: {'; '.join(row_errors)}.")
                else:
                    parsed_rows.append({
                        "title": title,
                        "description": description,
                        "priority": priority_raw,
                        "status": status_raw,
                        "category_name": category_raw,
                        "due_date": due_date,
                        "created_at": created_raw or datetime.now().isoformat(),
                        "completed_at": completed_raw or None,
                    })

    except Exception as exc:
        return 0, [f"Error reading CSV file: {exc}"]

    # If any row had errors, reject the entire import to prevent partial data corruption
    if errors:
        return 0, errors

    if not parsed_rows:
        return 0, ["No valid data rows found in CSV."]

    owns_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        # Resolve categories against SQLite database
        existing_categories = get_all_categories(conn=conn)
        cat_name_to_id = {c["name"].lower(): c["id"] for c in existing_categories}

        rows_to_insert: list[tuple] = []
        for r in parsed_rows:
            cat_name = r["category_name"]
            cat_id: int | None = None
            if cat_name and cat_name.lower() not in ("uncategorized", "none", ""):
                lower_name = cat_name.lower()
                if lower_name in cat_name_to_id:
                    cat_id = cat_name_to_id[lower_name]
                else:
                    # Dynamically register newly encountered category
                    try:
                        cat_id = add_category(cat_name, conn=conn)
                        cat_name_to_id[lower_name] = cat_id
                    except Exception:
                        cat_id = None

            rows_to_insert.append((
                r["title"],
                r["description"],
                r["priority"],
                cat_id,
                r["due_date"],
                r["status"],
                r["created_at"],
                r["completed_at"],
            ))

        # Perform atomic database transaction
        with conn:
            conn.executemany(
                """INSERT INTO tasks
                   (title, description, priority, category_id, due_date,
                    status, is_deleted, created_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                rows_to_insert,
            )

        return len(rows_to_insert), []

    except Exception as exc:
        return 0, [f"Database transaction failed: {exc}"]
    finally:
        if owns_conn:
            conn.close()
