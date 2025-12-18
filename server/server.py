"""
BigTime REST API Server
Provides centralized server for multiple BigTime clients with time synchronization.
"""

import sqlite3
import uuid
from datetime import datetime

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from server.timeserver_service import get_time_service, initialize_time_service
import shared
from shared.logging_config import get_server_logger
from shared.models import (ApiResponse, Employee, PayPeriod, TimeLog)
from shared.utils import (format_date, format_datetime, get_data_path,
                          parse_date)

# Setup standardized logging
logger = get_server_logger()

# Server configuration constants
DB_BUSY_TIMEOUT_MS: int = 5000
DEFAULT_SERVER_PORT: int = 5000
WAITRESS_CHANNEL_TIMEOUT: int = 60
WAITRESS_CLEANUP_INTERVAL: int = 30
STARTUP_DELAY_MS: int = 1000

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global reference to Waitress server for graceful shutdown
_waitress_server = None
_waitress_lock = None

# Configuration
SERVER_DB = get_data_path('server_bigtime.db')
API_KEYS = {
    'default-api-key': 'default-device',  # In production, use proper key management
}


def get_db():
    """Get database connection (for Flask context).

    Uses traditional rollback journal (not WAL) for simpler concurrency model.
    Sets busy timeout for retry on locked database.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(str(SERVER_DB))
        try:
            g.db.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT_MS}")
            # Use traditional journal mode for simpler concurrency
            g.db.execute("PRAGMA journal_mode = DELETE")
        except Exception as e:
            logger.warning(f"Failed to set PRAGMA options: {e}")
        g.db.row_factory = sqlite3.Row
    return g.db


def get_standalone_db():
    """Get standalone database connection (outside Flask context).

    Uses traditional rollback journal (not WAL) for simpler concurrency model.
    Sets busy timeout for retry on locked database.
    """
    conn = sqlite3.connect(str(SERVER_DB))
    try:
        conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT_MS}")
        # Use traditional journal mode for simpler concurrency
        conn.execute("PRAGMA journal_mode = DELETE")
    except Exception as e:
        logger.warning(f"Failed to set PRAGMA options: {e}")
    conn.row_factory = sqlite3.Row
    return conn


def close_db(error):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.teardown_appcontext
def close_db_handler(error):
    close_db(error)


def init_server_db():
    """Initialize server database and time service"""
    conn = sqlite3.connect(str(SERVER_DB))
    try:
        conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode = DELETE")  # Use traditional rollback journal
    except Exception:
        pass
    conn.row_factory = sqlite3.Row

    # Check database integrity at startup
    try:
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        if result[0] != 'ok':
            logger.warning(f"Database integrity issue detected: {result[0]}")
            logger.info("Running REINDEX to repair...")
            conn.execute("REINDEX")
            conn.commit()
            logger.info("Database repair completed")
    except Exception as e:
        logger.warning(f"Failed to check database integrity: {e}")

    try:
        # Employees table
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
                rate REAL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Time logs table with sync fields
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT UNIQUE NOT NULL,
                badge TEXT NOT NULL,
                clock_in TEXT,
                clock_out TEXT,
                device_id TEXT,
                device_ts TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (badge) REFERENCES employees (badge)
            )
        """)

        # API keys table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_used TEXT DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT TRUE
            )
        """)

        # Settings table for server configuration
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default API key
        conn.execute("""
            INSERT OR IGNORE INTO api_keys (key, device_id, active)
            VALUES ('default-api-key', 'default-device', 1)
        """)

        # Insert default settings
        default_settings = [
            ('host', '127.0.0.1'),
            ('port', str(DEFAULT_SERVER_PORT)),
            ('autostart', 'true'),
            ('company_name', 'BigTime'),
            ('setup_completed', 'false')
        ]

        for key, value in default_settings:
            conn.execute("""
                INSERT OR IGNORE INTO settings (key, value)
                VALUES (?, ?)
            """, (key, value))

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize server database: {e}")
        raise
    finally:
        conn.close()

    # Initialize time service (but don't start it yet - that happens in run_server)
    try:
        initialize_time_service('UTC', start=False)  # Use default sync interval
        logger.info("Time service initialized with UTC")
    except Exception as e:
        logger.error(f"Failed to initialize time service: {e}")
        # Continue without time sync


def get_server_setting(key: str, default=None):
    """Get a server setting from the database"""
    try:
        # Check if we're in Flask context
        from flask import has_app_context
        if has_app_context():
            conn = get_db()
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default
        else:
            # Use standalone connection
            conn = get_standalone_db()
            try:
                cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row['value'] if row else default
            finally:
                conn.close()
    except Exception:
        return default


def _ensure_settings_table(conn: sqlite3.Connection) -> bool:
    """Ensure settings table exists in database.

    Args:
        conn: Database connection

    Returns:
        True if table exists or was created, False otherwise
    """
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to ensure settings table: {e}")
        return False


def set_server_setting(key: str, value: str):
    """Set a server setting in the database"""
    try:
        # Check if we're in Flask context
        from flask import has_app_context
        if has_app_context():
            conn = get_db()
            if not _ensure_settings_table(conn):
                return False
            cursor = conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            conn.commit()
            return True
        else:
            # Use standalone connection
            conn = get_standalone_db()
            try:
                if not _ensure_settings_table(conn):
                    return False
                cursor = conn.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to set server setting {key}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    except Exception as e:
        logger.error(f"Failed to set server setting {key}: {e}")
        return False


def get_server_config():
    """Get all server configuration from database"""
    config = {}
    settings_keys = ['host', 'port', 'autostart', 'company_name', 'setup_completed']

    for key in settings_keys:
        value = get_server_setting(key)
        if value is not None:
            # Convert string values to appropriate types
            if key == 'port':
                config[key] = int(value)
            elif key == 'autostart' or key == 'setup_completed':
                config[key] = value.lower() == 'true'
            else:
                config[key] = value

    return config


def authenticate_request():
    """Authenticate API request using Bearer token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.debug("Auth failed: No Bearer token in request")
        return None

    api_key = auth_header[7:]  # Remove 'Bearer '
    logger.debug(f"Authenticating with API key: {api_key[:8]}...")

    db = get_db()

    # First check if the key exists at all
    cursor = db.execute(
        "SELECT device_id, active FROM api_keys WHERE key = ?",
        (api_key,)
    )
    row = cursor.fetchone()

    if not row:
        # Debug: Check what keys ARE in the database
        all_keys = db.execute("SELECT COUNT(*) as count FROM api_keys").fetchone()
        logger.warning(f"Auth failed: API key not found in database (key: {api_key[:8]}...). Total keys in DB: {all_keys['count']}")

        # List first few keys for debugging (masked for security)
        sample_keys = db.execute("SELECT key FROM api_keys LIMIT 5").fetchall()
        logger.debug(f"Sample keys in database: {[k['key'][:8] + '...' for k in sample_keys]}")
        return None

    device_id = row['device_id']
    active = row['active']

    logger.debug(f"Found API key in database - device_id={device_id}, active={active} (type={type(active).__name__})")

    # Check if key is active (handle both int and boolean)
    is_active = active == 1 or active == True or active == '1'
    if not is_active:
        logger.warning(f"Auth failed: API key exists but is not active (active={active})")
        return None

    # Update last used timestamp
    try:
        db.execute(
            "UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE key = ?",
            (api_key,)
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to update last_used timestamp: {e}")

    return device_id


def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        device_id = authenticate_request()
        if not device_id:
            return jsonify(ApiResponse(False, error="Unauthorized").to_dict()), 401
        g.device_id = device_id
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@app.errorhandler(400)
def bad_request(error):
    return jsonify(ApiResponse(False, error="Bad request").to_dict()), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify(ApiResponse(False, error="Not found").to_dict()), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify(ApiResponse(False, error="Internal server error").to_dict()), 500


# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify(ApiResponse(True, data={"status": "healthy", "timestamp": format_datetime(datetime.now())}).to_dict())





@app.route('/api/v1/info', methods=['GET'])
def get_server_info():
    """Get server information including company name and configuration"""
    # Get settings from database
    company_name = get_server_setting('company_name', 'BigTime')

    time_service = get_time_service()

    return jsonify(ApiResponse(True, data={
        "company_name": company_name,
        "server_time": format_datetime(time_service.get_current_time()),
        "version": shared.__VERSION__,
        "api_version": shared.__API_VERSION__,
        "timezone": time_service.timezone_name,
    }).to_dict())


# Time service endpoints
@app.route('/api/v1/time', methods=['GET'])
def get_server_time():
    """Get current server time with NTP synchronization"""
    time_service = get_time_service()
    current_time = time_service.get_current_time()

    return jsonify(ApiResponse(True, data=time_service.get_sync_status()))


@app.route('/api/v1/time/sync', methods=['POST'])
@require_auth
def sync_time():
    """Force a time synchronization"""
    time_service = get_time_service()
    result = time_service.sync_time_once()

    if result and 'success' in result:
        return jsonify(ApiResponse(True, data=result).to_dict())
    else:
        return jsonify(ApiResponse(False, error=result.get('error', 'Sync failed')).to_dict())


# Employee endpoints
@app.route('/api/v1/employees', methods=['GET'])
@require_auth
def get_employees():
    """Get all employees"""
    try:
        db = get_db()
        cursor = db.execute("SELECT * FROM employees WHERE deactivated = FALSE ORDER BY name")
        employees = []

        for row in cursor.fetchall():
            emp = Employee(
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
                period=row['period'] or 'hourly',
                rate=row['rate'] or 0.0
            )
            employees.append(emp.to_dict())

        return jsonify(ApiResponse(True, data={"employees": employees}).to_dict())

    except Exception as e:
        logger.error(f"Error fetching employees: {e}")
        return jsonify(ApiResponse(False, error=str(e)).to_dict()), 500


@app.route('/api/v1/employees', methods=['POST'])
@require_auth
def create_employee():
    """Create new employee"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(ApiResponse(False, error="No data provided").to_dict()), 400

        emp = Employee.from_dict(data)

        db = get_db()
        cursor = db.execute("""
            INSERT INTO employees (
                name, badge, phone_number, pin, department,
                date_of_birth, hire_date, deactivated, ssn, period, rate,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            emp.name,
            emp.badge,
            emp.phone_number,
            emp.pin,
            emp.department,
            format_date(emp.date_of_birth) if emp.date_of_birth else None,
            format_date(emp.hire_date) if emp.hire_date else None,
            emp.deactivated,
            emp.ssn,
            emp.period,
            emp.rate,
            format_datetime(datetime.now()),
            format_datetime(datetime.now())
        ))

        db.commit()
        emp.id = cursor.lastrowid

        return jsonify(ApiResponse(True, data=emp.to_dict()).to_dict()), 201

    except sqlite3.IntegrityError as e:
        db.rollback()  # Ensure transaction is rolled back
        if "UNIQUE constraint failed: employees.badge" in str(e):
            return jsonify(ApiResponse(False, error=f"Employee with badge '{emp.badge}' already exists").to_dict()), 409
        else:
            logger.error(f"Database integrity error creating employee: {e}")
            return jsonify(ApiResponse(False, error="Employee data violates database constraints").to_dict()), 400
    except Exception as e:
        db.rollback()  # Ensure transaction is rolled back
        logger.error(f"Error creating employee: {e}")
        return jsonify(ApiResponse(False, error="Internal server error").to_dict()), 500


@app.route('/api/v1/employees/<badge>', methods=['PUT'])
@require_auth
def update_employee(badge):
    """Update existing employee by badge"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(ApiResponse(False, error="No data provided").to_dict()), 400

        db = get_db()

        # Use exclusive transaction to prevent conflicts
        db.execute("BEGIN EXCLUSIVE TRANSACTION")

        try:
            # Check if employee exists
            cursor = db.execute("SELECT id FROM employees WHERE badge = ?", (badge,))
            if not cursor.fetchone():
                db.rollback()
                return jsonify(ApiResponse(False, error=f"Employee with badge '{badge}' not found").to_dict()), 404

            # Build update query from provided fields
            allowed_fields = {
                'name', 'badge', 'phone_number', 'pin', 'department',
                'date_of_birth', 'hire_date', 'deactivated', 'ssn', 'period', 'rate'
            }

            # Filter to only allowed fields that are present in request
            updates = {k: v for k, v in data.items() if k in allowed_fields}

            if not updates:
                db.rollback()
                return jsonify(ApiResponse(False, error="No valid fields to update").to_dict()), 400

            # Handle date formatting
            if 'date_of_birth' in updates and updates['date_of_birth']:
                from shared.utils import format_date, parse_date
                parsed_date = parse_date(updates['date_of_birth']) if isinstance(updates['date_of_birth'], str) else updates['date_of_birth']
                updates['date_of_birth'] = format_date(parsed_date) if parsed_date else None

            if 'hire_date' in updates and updates['hire_date']:
                from shared.utils import format_date, parse_date
                parsed_date = parse_date(updates['hire_date']) if isinstance(updates['hire_date'], str) else updates['hire_date']
                updates['hire_date'] = format_date(parsed_date) if parsed_date else None

            # Add updated_at timestamp
            updates['updated_at'] = format_datetime(datetime.now())

            # Build and execute update query
            set_clause = ', '.join([f"{field} = ?" for field in updates.keys()])
            values = list(updates.values()) + [badge]

            cursor = db.execute(f"""
                UPDATE employees
                SET {set_clause}
                WHERE badge = ?
            """, values)

            if cursor.rowcount == 0:
                db.rollback()
                return jsonify(ApiResponse(False, error="Employee not found or no changes made").to_dict()), 404

            # If badge was changed, update all related logs
            if 'badge' in updates and updates['badge'] != badge:
                new_badge = updates['badge']
                db.execute("""
                    UPDATE logs
                    SET badge = ?, updated_at = ?
                    WHERE badge = ?
                """, (new_badge, updates['updated_at'], badge))
                logger.info(f"Updated {cursor.rowcount} logs from badge '{badge}' to '{new_badge}'")

            db.commit()

            # Return updated employee data
            cursor = db.execute("SELECT * FROM employees WHERE badge = ?", (updates.get('badge', badge),))
            row = cursor.fetchone()

            if row:
                emp = Employee(
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
                return jsonify(ApiResponse(True, data=emp.to_dict()).to_dict()), 200
            else:
                db.rollback()
                return jsonify(ApiResponse(False, error="Failed to retrieve updated employee").to_dict()), 500

        except sqlite3.IntegrityError as e:
            db.rollback()
            if "UNIQUE constraint failed: employees.badge" in str(e):
                return jsonify(ApiResponse(False, error=f"Badge '{updates.get('badge')}' already exists").to_dict()), 409
            else:
                logger.error(f"Database integrity error updating employee: {e}")
                return jsonify(ApiResponse(False, error="Employee data violates database constraints").to_dict()), 400
        except Exception as e:
            db.rollback()
            raise

    except Exception as e:
        logger.error(f"Error updating employee: {e}")
        return jsonify(ApiResponse(False, error="Internal server error").to_dict()), 500


@app.route('/api/v1/employees/<badge>', methods=['DELETE'])
@require_auth
def delete_employee(badge):
    """Delete employee by badge"""
    try:
        db = get_db()

        # Use exclusive transaction
        db.execute("BEGIN EXCLUSIVE TRANSACTION")

        try:
            # Check if employee exists
            cursor = db.execute("SELECT id FROM employees WHERE badge = ?", (badge,))
            if not cursor.fetchone():
                db.rollback()
                return jsonify(ApiResponse(False, error=f"Employee with badge '{badge}' not found").to_dict()), 404

            # Delete employee (logs will remain for historical purposes)
            cursor = db.execute("DELETE FROM employees WHERE badge = ?", (badge,))

            if cursor.rowcount == 0:
                db.rollback()
                return jsonify(ApiResponse(False, error="Failed to delete employee").to_dict()), 500

            db.commit()
            return jsonify(ApiResponse(True, data={"message": f"Employee '{badge}' deleted successfully"}).to_dict()), 200

        except Exception as e:
            db.rollback()
            raise

    except Exception as e:
        logger.error(f"Error deleting employee: {e}")
        return jsonify(ApiResponse(False, error="Internal server error").to_dict()), 500


# Time log endpoints
@app.route('/api/v1/logs', methods=['POST'])
@require_auth
def create_log():
    """Create new time log (clock in)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(ApiResponse(False, error="No data provided").to_dict()), 400

        # Validate required fields
        required_fields = ['client_id', 'badge', 'clock_in']
        for field in required_fields:
            if not data.get(field):
                return jsonify(ApiResponse(False, error=f"Missing required field: {field}").to_dict()), 400

        client_id = data['client_id']
        badge = data['badge']
        clock_in = data['clock_in']
        device_id = data.get('device_id', g.device_id)
        device_ts = data.get('device_ts')

        db = get_db()

        # Check for idempotency - if client_id already exists, return existing record
        cursor = db.execute("SELECT * FROM logs WHERE client_id = ?", (client_id,))
        existing = cursor.fetchone()

        if existing:
            return jsonify(ApiResponse(True, data={
                "id": existing['id'],
                "client_id": existing['client_id'],
                "created_at": existing['created_at']
            }).to_dict()), 200

        # Use transaction with explicit locking to prevent race conditions
        db.execute("BEGIN EXCLUSIVE TRANSACTION")

        try:
            # Verify employee exists
            cursor = db.execute("SELECT id FROM employees WHERE badge = ?", (badge,))
            if not cursor.fetchone():
                db.rollback()
                return jsonify(ApiResponse(False, error=f"Employee with badge {badge} not found").to_dict()), 404

            # Check for existing open log (within the same transaction)
            cursor = db.execute("""
                SELECT id FROM logs WHERE badge = ? AND clock_out IS NULL
            """, (badge,))
            if cursor.fetchone():
                db.rollback()
                return jsonify(ApiResponse(False, error=f"Employee {badge} already clocked in").to_dict()), 409

            # Create new log (atomically with the check above)
            now = format_datetime(datetime.now())
            cursor = db.execute("""
                INSERT INTO logs (client_id, badge, clock_in, device_id, device_ts, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (client_id, badge, clock_in, device_id, device_ts, now, now))

            db.commit()
            log_id = cursor.lastrowid

        except Exception as e:
            db.rollback()
            raise

        return jsonify(ApiResponse(True, data={
            "id": log_id,
            "client_id": client_id,
            "created_at": now
        }).to_dict()), 201

    except Exception as e:
        logger.error(f"Error creating log: {e}")
        return jsonify(ApiResponse(False, error=str(e)).to_dict()), 500


@app.route('/api/v1/logs/<int:log_id>', methods=['PUT'])
@require_auth
def update_log(log_id):
    """Update existing time log (clock out)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(ApiResponse(False, error="No data provided").to_dict()), 400

        db = get_db()

        # Find existing log
        cursor = db.execute("SELECT * FROM logs WHERE id = ?", (log_id,))
        existing = cursor.fetchone()

        if not existing:
            return jsonify(ApiResponse(False, error="Log not found").to_dict()), 404

        # Update fields
        update_fields = []
        values = []

        if 'clock_out' in data:
            update_fields.append("clock_out = ?")
            values.append(data['clock_out'])

        if 'device_id' in data:
            update_fields.append("device_id = ?")
            values.append(data['device_id'])

        if update_fields:
            update_fields.append("updated_at = ?")
            values.append(format_datetime(datetime.now()))
            values.append(log_id)

            db.execute(f"""
                UPDATE logs SET {', '.join(update_fields)} WHERE id = ?
            """, values)
            db.commit()

        return jsonify(ApiResponse(True, data={"id": log_id, "updated": True}).to_dict())

    except Exception as e:
        logger.error(f"Error updating log: {e}")
        return jsonify(ApiResponse(False, error=str(e)).to_dict()), 500


@app.route('/api/v1/logs/<int:log_id>', methods=['DELETE'])
@require_auth
def delete_log(log_id):
    """Delete a time log by ID"""
    try:
        # Get the log first to check if it exists
        db = get_db()
        cursor = db.execute("SELECT id, badge FROM logs WHERE id = ?", (log_id,))
        log = cursor.fetchone()

        if not log:
            return jsonify(ApiResponse(False, error="Log not found").to_dict()), 404

        # Delete the log
        cursor = db.execute("DELETE FROM logs WHERE id = ?", (log_id,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify(ApiResponse(False, error="Log not found").to_dict()), 404

        logger.info(f"Deleted log {log_id} for employee {log['badge']}")
        return jsonify(ApiResponse(True, data={"id": log_id, "deleted": True}).to_dict())

    except Exception as e:
        logger.error(f"Error deleting log: {e}")
        return jsonify(ApiResponse(False, error=str(e)).to_dict()), 500


@app.route('/api/v1/logs', methods=['GET'])
@require_auth
def get_logs():
    """Get time logs with optional filtering"""
    try:
        badge = request.args.get('badge')
        start_date = request.args.get('start')
        end_date = request.args.get('end')

        db = get_db()
        query = "SELECT * FROM logs"
        conditions = []
        params = []

        if badge:
            conditions.append("badge = ?")
            params.append(badge)

        if start_date:
            conditions.append("date(clock_in) >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("date(clock_in) <= ?")
            params.append(end_date)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY clock_in DESC"

        cursor = db.execute(query, params)
        logs = []

        for row in cursor.fetchall():
            log = TimeLog(
                id=row['id'],
                client_id=row['client_id'],
                badge=row['badge'],
                clock_in=row['clock_in'],
                clock_out=row['clock_out'],
                device_id=row['device_id'],
                device_ts=row['device_ts'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            logs.append(log.to_dict())

        return jsonify(ApiResponse(True, data={"logs": logs}).to_dict())

    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify(ApiResponse(False, error=str(e)).to_dict()), 500


# Device onboarding endpoint
@app.route('/api/v1/devices/onboard', methods=['POST'])
def onboard_device():
    """Onboard a new device and issue API key"""
    try:
        data = request.get_json()
        if not data or not data.get('device_id'):
            return jsonify(ApiResponse(False, error="device_id required").to_dict()), 400

        device_id = data['device_id']
        api_key = str(uuid.uuid4())

        db = get_db()
        db.execute("""
            INSERT INTO api_keys (key, device_id, created_at, last_used, active)
            VALUES (?, ?, ?, ?, 1)
        """, (api_key, device_id, format_datetime(datetime.now()), format_datetime(datetime.now())))
        db.commit()

        return jsonify(ApiResponse(True, data={
            "api_key": api_key,
            "device_id": device_id
        }).to_dict()), 201

    except Exception as e:
        logger.error(f"Error onboarding device: {e}")
        return jsonify(ApiResponse(False, error=str(e)).to_dict()), 500




def run_server(host='0.0.0.0', port=DEFAULT_SERVER_PORT):
    """Run server with Waitress WSGI server"""
    # Start time service now that server is running
    try:
        time_service = get_time_service()
        time_service.start_sync_service()
        logger.info("Time service started")
    except Exception as e:
        logger.warning(f"Failed to start time service: {e}")

    # Use create_server/run to allow a programmatic shutdown
    try:
        from waitress import create_server
    except Exception:
        # Fallback to serve if create_server isn't available
        from waitress import serve

        logger.info(f"Starting BigTime Server on {host}:{port}")
        logger.info("Using Waitress WSGI server (serve)")

        # Waitress configuration
        serve(
            app,
            host=host,
            port=port,
            threads=6,  # Handle multiple concurrent requests
            channel_timeout=WAITRESS_CHANNEL_TIMEOUT,
            cleanup_interval=WAITRESS_CLEANUP_INTERVAL,
            asyncore_use_poll=True  # Better performance on Windows
        )
        return

    global _waitress_server, _waitress_lock
    import threading

    logger.info(f"Starting BigTime Server on {host}:{port}")
    logger.info("Using Waitress WSGI server (create_server)")

    # Build the server instance
    server = create_server(
        app,
        host=host,
        port=port,
        threads=6,
        channel_timeout=WAITRESS_CHANNEL_TIMEOUT,
        cleanup_interval=WAITRESS_CLEANUP_INTERVAL,
        asyncore_use_poll=True
    )

    _waitress_lock = threading.Lock()
    with _waitress_lock:
        _waitress_server = server

        try:
            # This blocks until server stops
            server.run()
        except Exception as e:
            logger.error(f"Server error during run: {e}")
            raise
        finally:
            # Stop time service
            try:
                time_service = get_time_service()
                time_service.stop_sync_service()
                logger.info("Time service stopped")
            except Exception as e:
                logger.warning(f"Failed to stop time service: {e}")

            # Ensure proper cleanup on exit
            with _waitress_lock:
                try:
                    with _waitress_lock:
                        # Close all active channels/connections before closing server
                        if hasattr(server, 'asyncore') and hasattr(server.asyncore, 'socket_map'):
                            try:
                                for dispatcher in list(server.asyncore.socket_map.values()):
                                    try:
                                        dispatcher.close()
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                        # Close trigger sockets if they exist
                        if hasattr(server, 'trigger') and server.trigger:
                            try:
                                server.trigger.close()
                            except Exception:
                                pass

                        _waitress_server = None
                except Exception as e:
                    logger.error(f"Error during server cleanup: {e}")


@app.route('/admin/shutdown', methods=['POST'])
def admin_shutdown():
    """Shutdown the waitress server gracefully. Restricted to local requests only."""
    try:
        # Only allow local requests for shutdown
        remote_addr = request.remote_addr
        if remote_addr not in (None, '127.0.0.1', '::1', 'localhost'):
            return jsonify(ApiResponse(False, error="Forbidden").to_dict()), 403

        global _waitress_server, _waitress_lock
        if _waitress_server is None:
            return jsonify(ApiResponse(False, error="Server not running").to_dict()), 400

        # Use close() to stop the server loop with proper connection cleanup
        try:
            with _waitress_lock:
                # Close all active channels/connections first to prevent socket errors
                if hasattr(_waitress_server, 'asyncore') and hasattr(_waitress_server.asyncore, 'socket_map'):
                    try:
                        # Close all asyncore sockets gracefully
                        for dispatcher in list(_waitress_server.asyncore.socket_map.values()):
                            try:
                                dispatcher.close()
                            except Exception:
                                pass  # Ignore errors during dispatcher close
                    except Exception:
                        pass  # If socket_map doesn't exist, continue with normal close

                # Now close the server
                _waitress_server.close()
        except Exception as e:
            logger.error(f"Error shutting down server: {e}")
            return jsonify(ApiResponse(False, error=str(e)).to_dict()), 500

        return jsonify(ApiResponse(True, data={"message": "Shutdown initiated"}).to_dict())
    except Exception as e:
        logger.error(f"Shutdown request failed: {e}")
        return jsonify(ApiResponse(False, error=str(e)).to_dict()), 500


if __name__ == '__main__':
    # Initialize database with defaults
    init_server_db()

    # Get configuration from database
    config = get_server_config()
    host = config.get('host', '0.0.0.0')
    port = config.get('port', DEFAULT_SERVER_PORT)

    # Run server
    run_server(host, port)
