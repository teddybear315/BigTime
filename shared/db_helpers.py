"""
Database helpers abstraction layer for BigTime application.
Supports both local SQLite database and remote API operations.
"""

import os
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from shared.models import Employee, PayPeriod, SyncState, TimeLog
from shared.utils import (format_date, format_datetime, get_data_path,
                          get_resource_path, parse_date, parse_datetime,
                          to_int_optional)


class DatabaseException(Exception):
    """Custom exception for database operations"""
    pass


def validate_badge(badge: str) -> str:
    """Validate and sanitize badge input"""
    if not badge or not isinstance(badge, str):
        raise DatabaseException("Badge must be a non-empty string")

    badge = badge.strip()
    if not badge:
        raise DatabaseException("Badge cannot be empty or whitespace")

    # Allow alphanumeric characters, dashes, underscores (reasonable badge format)
    if not re.match(r'^[a-zA-Z0-9_-]+$', badge):
        raise DatabaseException("Badge can only contain letters, numbers, dashes, and underscores")

    if len(badge) > 20:  # Reasonable limit
        raise DatabaseException("Badge must be 20 characters or less")

    return badge


def validate_datetime_string(dt_str: str, field_name: str) -> str:
    """Validate datetime string format"""
    if not dt_str or not isinstance(dt_str, str):
        raise DatabaseException(f"{field_name} must be a non-empty string")

    # Try to parse it to ensure it's valid
    parsed_dt = parse_datetime(dt_str)
    if parsed_dt is None:
        raise DatabaseException(f"{field_name} must be a valid datetime string")

    return dt_str


def get_db_path() -> Path:
    """Get the database file path - always in the executable/project directory"""
    return get_data_path('bigtime.db')


def init_database():
    """Initialize the database with required tables and migrations"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    # Improve concurrency: wait up to 5s on locks and use WAL mode
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row

    try:
        # Create employees table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                badge TEXT UNIQUE NOT NULL,
                phone_number INTEGER,
                pin TEXT,
                department TEXT,
                date_of_birth TEXT,
                hire_date TEXT,
                deactivated BOOLEAN DEFAULT FALSE,
                ssn INTEGER,
                period TEXT DEFAULT 'hourly',
                rate REAL DEFAULT 0.0
            )
        """)

        # Create logs table with all sync columns
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                badge TEXT NOT NULL,
                clock_in TEXT,
                clock_out TEXT,
                client_id TEXT,
                remote_id INTEGER,
                device_id TEXT,
                sync_state TEXT DEFAULT 'synced',
                device_ts TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create settings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Create sync_changes table to track what needs to be synced
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_type TEXT NOT NULL,  -- 'employee_create', 'employee_update', 'employee_delete', 'log_create', 'log_update', 'log_delete'
                entity_id TEXT NOT NULL,    -- badge for employees, log_id for logs
                change_data TEXT,           -- JSON data of the change (for updates)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(change_type, entity_id)
            )
        """)

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise DatabaseException(f"Failed to initialize database: {e}")
    finally:
        conn.close()

def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory"""
    conn = sqlite3.connect(str(get_db_path()))
    # Improve concurrency: wait up to 5s on locks
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn


# Settings functions
def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a setting value from the database"""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str):
    """Set a setting value in the database"""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
        """, (key, value))
        conn.commit()
    finally:
        conn.close()


# Employee functions
def insert_employee_no_tracking(employee: Employee) -> int:
    """Insert a new employee without change tracking (for server sync)"""
    # Validate critical fields
    if not employee.name or not employee.name.strip():
        raise DatabaseException("Employee name cannot be empty")

    validated_badge = validate_badge(employee.badge)

    if employee.name and len(employee.name) > 100:
        raise DatabaseException("Employee name must be 100 characters or less")

    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        try:
            cursor = conn.execute("""
                INSERT INTO employees (
                    name, badge, phone_number, pin, department,
                    date_of_birth, hire_date, deactivated, ssn, period, rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                employee.name.strip(),
                validated_badge,
                employee.phone_number,
                employee.pin,
                employee.department,
                format_date(employee.date_of_birth) if employee.date_of_birth else None,
                format_date(employee.hire_date) if employee.hire_date else None,
                employee.deactivated,
                employee.ssn,
                employee.period,
                employee.rate
            ))

            conn.commit()
            employee_id = cursor.lastrowid

            # No change tracking for server sync

            return employee_id

        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "UNIQUE constraint failed: employees.badge" in str(e):
                raise DatabaseException(f"Employee with badge '{validated_badge}' already exists")
            else:
                raise DatabaseException(f"Employee insert failed due to constraint violation: {e}")
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to insert employee: {e}")

    finally:
        conn.close()


def insert_employee(employee: Employee) -> int:
    """Insert a new employee and return the ID"""
    # Validate critical fields
    if not employee.name or not employee.name.strip():
        raise DatabaseException("Employee name cannot be empty")

    validated_badge = validate_badge(employee.badge)

    if employee.name and len(employee.name) > 100:
        raise DatabaseException("Employee name must be 100 characters or less")

    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        try:
            cursor = conn.execute("""
                INSERT INTO employees (
                    name, badge, phone_number, pin, department,
                    date_of_birth, hire_date, deactivated, ssn, period, rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                employee.name.strip(),
                validated_badge,
                employee.phone_number,
                employee.pin,
                employee.department,
                format_date(employee.date_of_birth) if employee.date_of_birth else None,
                format_date(employee.hire_date) if employee.hire_date else None,
                employee.deactivated,
                employee.ssn,
                employee.period,
                employee.rate
            ))

            conn.commit()
            employee_id = cursor.lastrowid

            # Track the change for sync
            track_change('employee_create', validated_badge)

            return employee_id

        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "UNIQUE constraint failed: employees.badge" in str(e):
                raise DatabaseException(f"Employee with badge '{validated_badge}' already exists")
            else:
                raise DatabaseException(f"Employee insert failed due to constraint violation: {e}")
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to insert employee: {e}")

    finally:
        conn.close()


def get_employee_by_badge(badge: str) -> Optional[Employee]:
    """Get employee by badge"""
    validated_badge = validate_badge(badge)

    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM employees WHERE badge = ?", (validated_badge,))
        row = cursor.fetchone()
        if row:
            return Employee(
                id=row['id'],
                name=row['name'],
                badge=row['badge'],
                phone_number=row['phone_number'],
                pin=row['pin'] or '',
                department=row['department'] or '',
                date_of_birth=parse_date(row['date_of_birth']) if row['date_of_birth'] else None,
                hire_date=parse_date(row['hire_date']) if row['hire_date'] else None,
                deactivated=bool(row['deactivated']),
                ssn=row['ssn'],
                period=row['period'] or PayPeriod.HOURLY.value,
                rate=row['rate'] or 0.0
            )
        return None
    finally:
        conn.close()


def fetch_all_employees() -> List[Employee]:
    """Fetch all employees"""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM employees ORDER BY name")
        employees = []
        for row in cursor.fetchall():
            employees.append(Employee(
                id=row['id'],
                name=row['name'],
                badge=row['badge'],
                phone_number=row['phone_number'],
                pin=row['pin'] or '',
                department=row['department'] or '',
                date_of_birth=parse_date(row['date_of_birth']) if row['date_of_birth'] else None,
                hire_date=parse_date(row['hire_date']) if row['hire_date'] else None,
                deactivated=bool(row['deactivated']),
                ssn=row['ssn'],
                period=row['period'] or PayPeriod.HOURLY.value,
                rate=row['rate'] or 0.0
            ))
        return employees
    finally:
        conn.close()


def update_employee_by_badge_no_tracking(badge: str, updates: Dict[str, Any]) -> bool:
    """Update employee by badge without change tracking (for server sync)"""
    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        try:
            # Remove any fields that shouldn't be directly updated
            safe_updates = {k: v for k, v in updates.items() if k in [
                'name', 'phone_number', 'pin', 'department', 'date_of_birth',
                'hire_date', 'deactivated', 'ssn', 'period', 'rate'
            ]}

            if not safe_updates:
                raise DatabaseException("No valid fields to update")

            # Format dates properly
            if 'date_of_birth' in safe_updates and safe_updates['date_of_birth']:
                safe_updates['date_of_birth'] = format_date(safe_updates['date_of_birth'])
            if 'hire_date' in safe_updates and safe_updates['hire_date']:
                safe_updates['hire_date'] = format_date(safe_updates['hire_date'])

            # Build safe SET clause using only validated field names
            set_clause = ', '.join([f"{key} = ?" for key in safe_updates.keys()])
            values = list(safe_updates.values()) + [badge]

            cursor = conn.execute(f"""
                UPDATE employees SET {set_clause} WHERE badge = ?
            """, values)

            conn.commit()
            updated = cursor.rowcount > 0

            # No change tracking for server sync

            return updated

        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to update employee: {e}")

    finally:
        conn.close()


def update_employee_by_badge(badge: str, updates: Dict[str, Any]) -> bool:
    """Update employee by badge"""
    if not updates:
        return False

    # Validate allowed fields to prevent SQL injection
    allowed_fields = {
        'name', 'badge', 'phone_number', 'pin', 'department',
        'date_of_birth', 'hire_date', 'deactivated', 'ssn', 'period', 'rate'
    }

    # Filter out any invalid fields
    safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
    if not safe_updates:
        raise DatabaseException(f"No valid fields to update. Allowed fields: {allowed_fields}")

    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        try:
            # Convert dates to strings
            if 'date_of_birth' in safe_updates and safe_updates['date_of_birth']:
                safe_updates['date_of_birth'] = format_date(safe_updates['date_of_birth'])
            if 'hire_date' in safe_updates and safe_updates['hire_date']:
                safe_updates['hire_date'] = format_date(safe_updates['hire_date'])

            # Build safe SET clause using only validated field names
            set_clause = ', '.join([f"{key} = ?" for key in safe_updates.keys()])
            values = list(safe_updates.values()) + [badge]

            cursor = conn.execute(f"""
                UPDATE employees SET {set_clause} WHERE badge = ?
            """, values)

            conn.commit()
            updated = cursor.rowcount > 0

            # Track the change for sync if update was successful
            if updated:
                import json
                track_change('employee_update', badge, json.dumps(safe_updates))

            return updated

        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to update employee: {e}")

    finally:
        conn.close()


def update_employee_badge(old_badge: str, new_badge: str) -> bool:
    """Update employee badge and all associated data"""
    conn = get_connection()
    try:
        # Start explicit transaction
        conn.execute("BEGIN TRANSACTION")

        try:
            # Update employee record
            cursor = conn.execute(
                "UPDATE employees SET badge = ? WHERE badge = ?",
                (new_badge, old_badge)
            )

            if cursor.rowcount == 0:
                conn.rollback()
                return False

            # Update all time logs with the old badge
            conn.execute(
                "UPDATE logs SET badge = ? WHERE badge = ?",
                (new_badge, old_badge)
            )

            conn.commit()

            # Track the badge change for sync
            track_change('employee_update', new_badge)

            return True

        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to update employee badge: {e}")

    finally:
        conn.close()


def delete_employee_by_badge(badge: str) -> bool:
    """Delete employee by badge"""
    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        # First, collect logs for this badge so we can track deletions using remote IDs
        cursor = conn.execute(
            """
            SELECT id, remote_id
            FROM logs
            WHERE badge = ?
            """,
            (badge,)
        )
        logs = cursor.fetchall()

        # Track each log deletion (prefer remote_id when available)
        for row in logs:
            local_id = row[0]
            remote_id = row[1]
            if remote_id:
                # Track deletion by remote ID so the server delete succeeds
                track_change_with_conn(conn, 'log_delete', str(remote_id))
            else:
                # Fallback to local ID (server delete will 404 which we treat as success)
                track_change_with_conn(conn, 'log_delete', str(local_id))

        # Delete logs for this badge locally
        conn.execute("DELETE FROM logs WHERE badge = ?", (badge,))

        # Delete the employee record
        cursor = conn.execute("DELETE FROM employees WHERE badge = ?", (badge,))
        deleted = cursor.rowcount > 0

        # Track the employee deletion after successful removal
        if deleted:
            track_change_with_conn(conn, 'employee_delete', badge)

        conn.commit()
        return deleted
    finally:
        conn.close()


def update_log_remote_id(log_id: int, remote_id: int) -> bool:
    """Update the remote_id for a log entry"""
    conn = get_connection()
    try:
        cursor = conn.execute("UPDATE logs SET remote_id = ? WHERE id = ?", (remote_id, log_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_log_sync_state(log_id: int, sync_state: str) -> bool:
    """Update the sync_state for a log entry"""
    conn = get_connection()
    try:
        cursor = conn.execute("UPDATE logs SET sync_state = ? WHERE id = ?", (sync_state, log_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_log_by_id(log_id: int) -> bool:
    """Delete time log by ID"""
    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        # Fetch remote_id first so we can track server deletion correctly
        cursor = conn.execute("SELECT remote_id FROM logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        remote_id = row[0] if row else None

        cursor = conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
        deleted = cursor.rowcount > 0

        if deleted:
            # Prefer remote id for deletion tracking; server endpoint expects remote id
            if remote_id:
                track_change_with_conn(conn, 'log_delete', str(remote_id))
            else:
                track_change_with_conn(conn, 'log_delete', str(log_id))

        conn.commit()
        return deleted
    finally:
        conn.close()


def get_logs_by_badge(badge: str) -> List[TimeLog]:
    """Fetch all logs for a given badge."""
    validated_badge = validate_badge(badge)
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM logs
            WHERE badge = ?
            ORDER BY clock_in DESC
            """,
            (validated_badge,)
        )
        logs: List[TimeLog] = []
        for row in cursor.fetchall():
            rd = dict(row)
            logs.append(TimeLog(
                id=rd['id'],
                client_id=rd.get('client_id'),
                remote_id=rd.get('remote_id'),
                badge=rd['badge'],
                clock_in=rd['clock_in'],
                clock_out=rd['clock_out'],
                device_id=rd.get('device_id'),
                device_ts=rd.get('device_ts'),
                sync_state=rd.get('sync_state', SyncState.SYNCED.value),
                created_at=rd.get('created_at'),
                updated_at=rd.get('updated_at')
            ))
        return logs
    finally:
        conn.close()


def get_pending_employee_deletions() -> List[str]:
    """Get list of employee badges that need to be deleted from server"""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT badge FROM deleted_employees ORDER BY deleted_at")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def clear_employee_deletion(badge: str) -> bool:
    """Remove employee deletion from tracking (after successful server deletion)"""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM deleted_employees WHERE badge = ?", (badge,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def track_change(change_type: str, entity_id: str, change_data: str = None) -> None:
    """Track a change that needs to be synced to server"""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO sync_changes (change_type, entity_id, change_data)
            VALUES (?, ?, ?)
        """, (change_type, entity_id, change_data))
        conn.commit()
    finally:
        conn.close()

def track_change_with_conn(conn, change_type: str, entity_id: str, change_data: str = None) -> None:
    """Track a change using an existing open connection (for use within a transaction)."""
    conn.execute(
        """
        INSERT OR REPLACE INTO sync_changes (change_type, entity_id, change_data)
        VALUES (?, ?, ?)
        """,
        (change_type, entity_id, change_data)
    )


def get_pending_changes() -> List[Dict[str, Any]]:
    """Get all pending changes that need to be synced"""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT change_type, entity_id, change_data, created_at
            FROM sync_changes
            ORDER BY created_at
        """)
        return [
            {
                'change_type': row[0],
                'entity_id': row[1],
                'change_data': row[2],
                'created_at': row[3]
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def clear_change(change_type: str, entity_id: str) -> None:
    """Clear a change after successful sync"""
    conn = get_connection()
    try:
        conn.execute("""
            DELETE FROM sync_changes
            WHERE change_type = ? AND entity_id = ?
        """, (change_type, entity_id))
        conn.commit()
    finally:
        conn.close()


def clear_all_changes() -> None:
    """Clear all pending changes (after successful full sync)"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM sync_changes")
        conn.commit()
    finally:
        conn.close()


def count_pending_nonlog_changes() -> int:
    """Count pending changes excluding log_* types (e.g., employee changes)."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM sync_changes
            WHERE change_type NOT LIKE 'log_%'
            """
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def get_log_by_id(log_id: int) -> Optional[Dict[str, Any]]:
    """Get a log entry by ID"""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_log_remote_id(log_id: int) -> Optional[int]:
    """Get the remote_id for a local log"""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT remote_id FROM logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        return row['remote_id'] if row else None
    finally:
        conn.close()


# Time log functions
def insert_log(badge: str, clock_in_time: str, client_id: Optional[str] = None,
               device_id: Optional[str] = None, sync_state: str = SyncState.SYNCED.value) -> int:
    """Insert a new time log entry"""
    # Validate inputs
    validated_badge = validate_badge(badge)
    validated_clock_in = validate_datetime_string(clock_in_time, "clock_in_time")

    if client_id and len(client_id) > 100:  # Reasonable limit
        raise DatabaseException("client_id must be 100 characters or less")

    if device_id and len(device_id) > 50:  # Reasonable limit
        raise DatabaseException("device_id must be 50 characters or less")

    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        try:
            now = format_datetime(datetime.now())

            cursor = conn.execute("""
                INSERT INTO logs (
                    badge, clock_in, client_id, device_id, sync_state,
                    device_ts, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (validated_badge, validated_clock_in, client_id, device_id, sync_state, now, now, now))

            conn.commit()
            log_id = cursor.lastrowid

            # Track the change for sync (only if it's not already synced)
            if sync_state != SyncState.SYNCED.value:
                track_change('log_create', str(log_id))

            return log_id

        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise DatabaseException(f"Log insert failed due to constraint violation: {e}")
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to insert log: {e}")

    finally:
        conn.close()


def close_most_recent_log(badge: str, clock_out_time: str) -> bool:
    """Close the most recent open log entry for a badge"""
    conn = get_connection()
    try:
        # Start explicit transaction to prevent race conditions
        conn.execute("BEGIN TRANSACTION")

        try:
            # Find most recent open log
            cursor = conn.execute("""
                SELECT id FROM logs
                WHERE badge = ? AND clock_out IS NULL
                ORDER BY clock_in DESC LIMIT 1
            """, (badge,))
            row = cursor.fetchone()

            if row:
                now = format_datetime(datetime.now())
                cursor = conn.execute("""
                    UPDATE logs
                    SET clock_out = ?, sync_state = ?, updated_at = ?
                    WHERE id = ? AND clock_out IS NULL
                """, (clock_out_time, SyncState.PENDING.value, now, row['id']))

                # Verify the update actually happened (no race condition)
                if cursor.rowcount > 0:
                    conn.commit()
                    # Track the change for sync
                    track_change('log_update', str(row['id']))
                    return True
                else:
                    conn.rollback()
                    return False
            else:
                conn.rollback()
                return False

        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to close log: {e}")

    finally:
        conn.close()


def get_open_log_for_badge(badge: str) -> Optional[TimeLog]:
    """Get open log entry for a badge"""
    validated_badge = validate_badge(badge)

    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT * FROM logs
            WHERE badge = ? AND clock_out IS NULL
            ORDER BY clock_in DESC LIMIT 1
        """, (validated_badge,))
        row = cursor.fetchone()

        if row:
            # Convert sqlite3.Row to dict to use .get() method
            row_dict = dict(row)
            return TimeLog(
                id=row_dict['id'],
                client_id=row_dict.get('client_id'),
                remote_id=row_dict.get('remote_id'),
                badge=row_dict['badge'],
                clock_in=row_dict['clock_in'],
                clock_out=row_dict['clock_out'],
                device_id=row_dict.get('device_id'),
                device_ts=row_dict.get('device_ts'),
                sync_state=row_dict.get('sync_state', SyncState.SYNCED.value),
                created_at=row_dict.get('created_at'),
                updated_at=row_dict.get('updated_at')
            )
        return None
    finally:
        conn.close()


def get_pending_logs() -> List[TimeLog]:
    """Get all logs that need to be synced"""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT * FROM logs
            WHERE sync_state = ?
            ORDER BY created_at
        """, (SyncState.PENDING.value,))

        logs = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            logs.append(TimeLog(
                id=row_dict['id'],
                client_id=row_dict.get('client_id'),
                remote_id=row_dict.get('remote_id'),
                badge=row_dict['badge'],
                clock_in=row_dict['clock_in'],
                clock_out=row_dict['clock_out'],
                device_id=row_dict.get('device_id'),
                device_ts=row_dict.get('device_ts'),
                sync_state=row_dict.get('sync_state', SyncState.PENDING.value),
                created_at=row_dict.get('created_at'),
                updated_at=row_dict.get('updated_at')
            ))
        return logs
    finally:
        conn.close()


def set_log_synced(log_id: int, remote_id: Optional[int] = None) -> bool:
    """Mark a log as synced"""
    conn = get_connection()
    try:
        # Validate state transition
        cursor = conn.execute("SELECT sync_state FROM logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        if row:
            current_state = row['sync_state']
            if not SyncState.is_valid_transition(current_state, SyncState.SYNCED.value):
                raise DatabaseException(f"Invalid sync state transition from {current_state} to {SyncState.SYNCED.value}")

        now = format_datetime(datetime.now())
        cursor = conn.execute("""
            UPDATE logs
            SET sync_state = ?, remote_id = ?, updated_at = ?
            WHERE id = ?
        """, (SyncState.SYNCED.value, remote_id, now, log_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def set_log_failed(log_id: int, error: str = "") -> bool:
    """Mark a log as failed to sync"""
    conn = get_connection()
    try:
        # Validate state transition
        cursor = conn.execute("SELECT sync_state FROM logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        if row:
            current_state = row['sync_state']
            if not SyncState.is_valid_transition(current_state, SyncState.FAILED.value):
                raise DatabaseException(f"Invalid sync state transition from {current_state} to {SyncState.FAILED.value}")

        now = format_datetime(datetime.now())
        cursor = conn.execute("""
            UPDATE logs
            SET sync_state = ?, updated_at = ?
            WHERE id = ?
        """, (SyncState.FAILED.value, now, log_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def reset_failed_logs_to_pending() -> int:
    """Reset all FAILED logs to PENDING so they can be retried by the sync service.

    Returns the number of rows updated.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE logs
            SET sync_state = ?
            WHERE sync_state = ?
            """,
            (SyncState.PENDING.value, SyncState.FAILED.value)
        )
        conn.commit()
        return cursor.rowcount or 0
    finally:
        conn.close()


def fetch_logs_for_range(badge: str, start_date: date, end_date: date) -> List[TimeLog]:
    """Fetch logs for a badge within date range"""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT * FROM logs
            WHERE badge = ? AND date(clock_in) BETWEEN ? AND ?
            ORDER BY clock_in
        """, (badge, format_date(start_date), format_date(end_date)))

        logs = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            logs.append(TimeLog(
                id=row_dict['id'],
                client_id=row_dict.get('client_id'),
                remote_id=row_dict.get('remote_id'),
                badge=row_dict['badge'],
                clock_in=row_dict['clock_in'],
                clock_out=row_dict['clock_out'],
                device_id=row_dict.get('device_id'),
                device_ts=row_dict.get('device_ts'),
                sync_state=row_dict.get('sync_state', SyncState.SYNCED.value),
                created_at=row_dict.get('created_at'),
                updated_at=row_dict.get('updated_at')
            ))
        return logs
    finally:
        conn.close()


def has_open_log(badge: str) -> bool:
    """Check if employee has an open log entry"""
    open_log = get_open_log_for_badge(badge)
    return open_log is not None


def get_all_time_logs() -> List[TimeLog]:
    """Get all time logs ordered by most recent first"""
    conn = get_connection()

    try:
        cursor = conn.execute("""
            SELECT id, badge, clock_in, clock_out, created_at, updated_at
            FROM logs
            ORDER BY created_at DESC
            LIMIT 100
        """)

        logs = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            logs.append(TimeLog(
                id=row_dict['id'],
                client_id=None,  # Not in basic logs table
                remote_id=None,  # Not in basic logs table
                badge=row_dict['badge'],
                clock_in=row_dict['clock_in'],
                clock_out=row_dict['clock_out'],
                device_id=None,  # Not in basic logs table
                device_ts=None,  # Not in basic logs table
                sync_state=SyncState.SYNCED.value,  # Default to synced for basic logs
                created_at=row_dict.get('created_at'),
                updated_at=row_dict.get('updated_at')
            ))
        return logs
    finally:
        conn.close()


def update_time_log(log_id: int, clock_in: str, clock_out: str) -> bool:
    """Update time log with new clock in/out times"""
    conn = get_connection()

    try:
        now = format_datetime(datetime.now())

        cursor = conn.execute("""
            UPDATE logs
            SET clock_in = ?, clock_out = ?, updated_at = ?,
                sync_state = ?
            WHERE id = ?
        """, (clock_in, clock_out, now, SyncState.PENDING.value, log_id))

        conn.commit()
        updated = cursor.rowcount > 0

        # Track the change for sync if update was successful
        if updated:
            track_change('log_update', str(log_id))

        return updated
    finally:
        conn.close()


def get_logs_by_badge_and_date_range(badge: str, start_date: str, end_date: str) -> list:
    """Get all logs for a specific employee badge within a date range"""
    conn = get_connection()

    try:
        # Check if sync_error column exists
        cursor = conn.execute("PRAGMA table_info(logs)")
        columns = [col[1] for col in cursor.fetchall()]
        has_sync_error = 'sync_error' in columns

        if has_sync_error:
            query = """
                SELECT id, badge, clock_in, clock_out, remote_id, sync_state, sync_error
                FROM logs
                WHERE badge = ?
                AND date(clock_in) >= date(?)
                AND date(clock_in) <= date(?)
                ORDER BY clock_in DESC
            """
        else:
            query = """
                SELECT id, badge, clock_in, clock_out, remote_id, sync_state
                FROM logs
                WHERE badge = ?
                AND date(clock_in) >= date(?)
                AND date(clock_in) <= date(?)
                ORDER BY clock_in DESC
            """

        cursor = conn.execute(query, (badge, start_date, end_date))
        rows = cursor.fetchall()
        logs = []

        for row in rows:
            log = TimeLog(
                id=row[0],
                badge=row[1],
                clock_in=row[2],
                clock_out=row[3],
                remote_id=row[4],
                sync_state=SyncState(row[5]) if row[5] else SyncState.PENDING,
                sync_error=row[6] if has_sync_error and len(row) > 6 else None
            )
            logs.append(log)

        return logs
    finally:
        conn.close()


def get_log_by_client_id(client_id: str) -> Optional[TimeLog]:
    """Get a time log by its client_id"""
    if not client_id:
        return None

    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT id, client_id, badge, clock_in, clock_out, device_id,
                   device_ts, sync_state, remote_id, created_at, updated_at
            FROM logs
            WHERE client_id = ?
        """, (client_id,))

        row = cursor.fetchone()
        if row:
            return TimeLog(
                id=row['id'],
                client_id=row['client_id'],
                badge=row['badge'],
                clock_in=row['clock_in'],
                clock_out=row['clock_out'],
                device_id=row['device_id'],
                device_ts=row['device_ts'],
                sync_state=SyncState(row['sync_state']),
                remote_id=row['remote_id'],
                sync_error=None,  # Column doesn't exist in current schema
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        return None
    finally:
        conn.close()


def update_log_no_tracking(log_id: int, updates: Dict[str, Any]) -> bool:
    """Update a time log with arbitrary fields without change tracking (for server sync)"""
    if not updates:
        return True

    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        # Build dynamic update query
        set_clauses = []
        params = []

        # Always update the updated_at timestamp
        updates['updated_at'] = format_datetime(datetime.now())

        for field, value in updates.items():
            if field in ['clock_out', 'updated_at', 'sync_state', 'remote_id', 'sync_error']:
                set_clauses.append(f"{field} = ?")
                params.append(value)

        if not set_clauses:
            return True  # Nothing to update

        params.append(log_id)  # For WHERE clause

        query = f"UPDATE logs SET {', '.join(set_clauses)} WHERE id = ?"
        cursor = conn.execute(query, params)

        conn.commit()
        updated = cursor.rowcount > 0

        # No change tracking for server sync

        return updated
    finally:
        conn.close()


def update_log(log_id: int, updates: Dict[str, Any]) -> bool:
    """Update a time log with arbitrary fields"""
    if not updates:
        return True

    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION")

        # Build dynamic update query
        set_clauses = []
        params = []

        # Always update the updated_at timestamp
        updates['updated_at'] = format_datetime(datetime.now())

        for field, value in updates.items():
            if field in ['clock_out', 'updated_at', 'sync_state', 'remote_id', 'sync_error']:
                set_clauses.append(f"{field} = ?")
                params.append(value)

        if not set_clauses:
            return True  # Nothing to update

        params.append(log_id)  # For WHERE clause

        query = f"UPDATE logs SET {', '.join(set_clauses)} WHERE id = ?"
        cursor = conn.execute(query, params)

        conn.commit()
        updated = cursor.rowcount > 0

        # Track the change for sync if update was successful
        if updated:
            track_change('log_update', str(log_id))

        return updated
    finally:
        conn.close()


def insert_log_from_object(log: TimeLog) -> Optional[int]:
    """Insert a TimeLog object into the database"""
    # Handle sync_state - it might be a string or SyncState enum
    if isinstance(log.sync_state, str):
        sync_state_value = log.sync_state
    elif hasattr(log.sync_state, 'value'):
        sync_state_value = log.sync_state.value
    else:
        sync_state_value = SyncState.PENDING.value

    return insert_log(
        badge=log.badge,
        clock_in_time=log.clock_in,
        client_id=log.client_id,
        device_id=log.device_id,
        sync_state=sync_state_value
    )


# Initialize database on import
if not get_db_path().exists():
    init_database()
