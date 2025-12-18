"""
Client application layer for BigTime.
Abstracts the UI from data access to support both local and remote operations.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject

from shared import db_helpers
from shared.logging_config import get_client_logger
from shared.models import Employee, SyncState, TimeLog

logger = get_client_logger()
from shared.utils import format_datetime


class BigTimeClient(QObject):
    """
    Client abstraction layer that handles:
    - Local database operations
    - Remote sync coordination
    - Offline-first behavior
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Setup standardized logging
        self.logger = get_client_logger()

        # Initialize database
        db_helpers.init_database()



    # Employee operations
    def get_employee_by_badge(self, badge: str) -> Optional[Employee]:
        """Get employee by badge (local database)"""
        return db_helpers.get_employee_by_badge(badge)

    def get_all_employees(self) -> List[Employee]:
        """Get all employees (local database)"""
        return db_helpers.fetch_all_employees()

    def create_employee(self, employee: Employee) -> int:
        """Create new employee (local database with optional sync)"""
        emp_id = db_helpers.insert_employee(employee)

        # Note: Employee sync is handled by NetworkWorker

        return emp_id

    def add_employee(self, employee: Employee) -> bool:
        """Add new employee (alias for create_employee with boolean return)"""
        try:
            emp_id = self.create_employee(employee)
            return emp_id is not None and emp_id > 0
        except Exception:
            return False

    def update_employee(self, employee: Employee) -> bool:
        """Update employee (local database and sync to server) - takes Employee object"""
        success = db_helpers.update_employee_by_badge(employee.badge, employee.to_dict())

        # Sync to server if sync service is available and configured
        # Note: Employee sync is handled by NetworkWorker

        return success

    def update_employee_fields(self, badge: str, updates: Dict[str, Any]) -> bool:
        """Update specific employee fields (local database and sync to server) - takes dictionary"""
        # Check if badge is being updated and handle it specially
        if 'badge' in updates and updates['badge'] != badge:
            return self.update_employee_badge(badge, updates)
        else:
            success = db_helpers.update_employee_by_badge(badge, updates)
            if success:
                # Track the change for sync
                db_helpers.track_change('employee_update', badge)

            # Note: Employee sync is handled by NetworkWorker

            return success

    def update_employee_badge(self, old_badge: str, updates: Dict[str, Any]) -> bool:
        """Update employee badge and handle all related data migrations"""
        import os
        import shutil
        from pathlib import Path

        new_badge = updates['badge']

        # Update database (employee record + time logs)
        success = db_helpers.update_employee_badge(old_badge, new_badge)

        if success:
            # Handle file system updates
            self._migrate_employee_files(old_badge, new_badge)

            # Update remaining fields (except badge, which was already updated)
            remaining_updates = {k: v for k, v in updates.items() if k != 'badge'}
            if remaining_updates:
                db_helpers.update_employee_by_badge(new_badge, remaining_updates)

        return success

    def _migrate_employee_files(self, old_badge: str, new_badge: str):
        """Migrate employee-related files and folders when badge changes"""
        import os
        import shutil
        from pathlib import Path

        # Define potential file/folder paths that use badge numbers
        base_paths = [
            Path("Reports"),
            Path("Data") / "Reports",
            Path("Employee_Data"),
            Path("Timesheets"),
            Path("Exports")
        ]

        for base_path in base_paths:
            if base_path.exists():
                old_folder = base_path / old_badge
                new_folder = base_path / new_badge

                if old_folder.exists():
                    try:
                        # Create parent directories if needed
                        new_folder.parent.mkdir(parents=True, exist_ok=True)

                        # Move the folder
                        shutil.move(str(old_folder), str(new_folder))
                        self.logger.info(f"Moved {old_folder} to {new_folder}")
                    except Exception as e:
                        self.logger.warning(f"Could not move {old_folder} to {new_folder}: {e}")

                # Also check for individual files named with the badge
                for pattern in [f"{old_badge}.*", f"*_{old_badge}.*", f"{old_badge}_*"]:
                    for old_file in base_path.glob(pattern):
                        if old_file.is_file():
                            try:
                                # Generate new filename
                                new_name = old_file.name.replace(old_badge, new_badge)
                                new_file = base_path / new_name

                                # Move the file
                                shutil.move(str(old_file), str(new_file))
                                self.logger.info(f"Moved {old_file} to {new_file}")
                            except Exception as e:
                                self.logger.warning(f"Could not move {old_file}: {e}")

    def delete_employee(self, badge: str) -> bool:
        """Delete employee (local database and sync to server)"""
        success = db_helpers.delete_employee_by_badge(badge)

        # Note: Employee deletion sync is handled by NetworkWorker

        return success

    # Time log operations (with sync integration)
    def clock_in(self, badge: str) -> Dict[str, Any]:
        """
        Clock in an employee.
        Returns: {'success': bool, 'message': str, 'client_id': str}
        """
        try:
            # Check if employee exists
            employee = self.get_employee_by_badge(badge)
            if not employee:
                return {
                    'success': False,
                    'message': f'Employee with badge {badge} not found',
                    'client_id': None
                }

            # Check for existing open log (local database)
            open_log = db_helpers.get_open_log_for_badge(badge)
            if open_log:
                return {
                    'success': False,
                    'message': f'Employee {badge} is already clocked in (local)',
                    'client_id': None
                }

            # Create log entry (local database only - sync handled by NetworkWorker)
            now = format_datetime(datetime.now())
            client_id = str(uuid.uuid4())

            # Insert directly to local database with PENDING sync state
            db_helpers.insert_log(badge, now, client_id, sync_state=SyncState.PENDING.value)

            return {
                'success': True,
                'message': f'{employee.name} clocked in successfully',
                'client_id': client_id
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error clocking in: {str(e)}',
                'client_id': None
            }



    def clock_out(self, badge: str) -> Dict[str, Any]:
        """
        Clock out an employee.
        Returns: {'success': bool, 'message': str}
        """
        try:
            # Check if employee exists
            employee = self.get_employee_by_badge(badge)
            if not employee:
                return {
                    'success': False,
                    'message': f'Employee with badge {badge} not found'
                }

            now = format_datetime(datetime.now())

            # Update local database only - sync handled by NetworkWorker
            success = db_helpers.close_most_recent_log(badge, now)

            if success:
                return {
                    'success': True,
                    'message': f'{employee.name} clocked out successfully'
                }
            else:
                return {
                    'success': False,
                    'message': f'No open time entry found for {badge}'
                }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error clocking out: {str(e)}'
            }

    def get_open_log(self, badge: str) -> Optional[TimeLog]:
        """Get open log for employee"""
        return db_helpers.get_open_log_for_badge(badge)

    def get_logs_for_range(self, badge: str, start_date, end_date) -> List[TimeLog]:
        """Get logs for date range"""
        return db_helpers.fetch_logs_for_range(badge, start_date, end_date)

    # Settings operations
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get setting value"""
        return db_helpers.get_setting(key, default)

    def set_setting(self, key: str, value: str):
        """Set setting value"""
        db_helpers.set_setting(key, value)

    # Sync operations
    def get_pending_logs_count(self) -> int:
        """Get count of logs pending sync"""
        pending_logs = db_helpers.get_pending_logs()
        return len(pending_logs)

    def retry_failed_syncs(self):
        """Retry failed sync operations - handled by NetworkWorker"""
        pass  # NetworkWorker handles all sync operations

    def get_all_time_logs(self) -> List[TimeLog]:
        """Get all time logs"""
        return db_helpers.get_all_time_logs()

    def update_time_log(self, log_id: int, clock_in: str, clock_out: str):
        """Update time log with new times"""
        return db_helpers.update_time_log(log_id, clock_in, clock_out)

    def delete_time_log(self, log_id: int) -> bool:
        """Delete time log by ID"""
        # Get the remote_id before deleting locally (in case we need it for server sync)
        remote_id = db_helpers.get_log_remote_id(log_id)

        # First delete locally
        local_success = db_helpers.delete_log_by_id(log_id)

        # Note: Log deletion sync is handled by NetworkWorker

        return local_success
# Global client instance
_client = None


def get_client() -> BigTimeClient:
    """Get the singleton client instance"""
    global _client
    if _client is None:
        _client = BigTimeClient()
    return _client
