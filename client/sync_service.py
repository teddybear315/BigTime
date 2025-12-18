"""
Remote sync service for BigTime client.
Handles background synchronization with the server in an offline-first manner.
"""

import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from shared import db_helpers
from shared.logging_config import get_sync_logger
from shared.models import (ApiResponse, CreateLogRequest, Employee,
                           ServerConfig, SyncState, SyncStatus, TimeLog,
                           UpdateLogRequest)
from shared.utils import format_datetime

logger = get_sync_logger()


class RemoteSyncService(QObject):
    """
    Background sync service that handles:
    - Pushing pending local changes to server
    - Pulling updates from server
    - Conflict resolution
    - Connection status monitoring
    """

    sync_status_changed = pyqtSignal(dict)  # Emits sync status updates
    employee_synced = pyqtSignal(dict)      # Emits when employees are synced

    def __init__(self, parent=None):
        super().__init__(parent)

        self.config = self._load_config()
        self.is_running = False
        self.is_syncing = False
        self.is_online = False
        self.last_sync = None
        self.last_error = None
        self.last_sync_attempt = None

        # Protect concurrent sync operations
        self._sync_lock = threading.Lock()

        # Backoff state for failures
        self._consecutive_failures = 0
        self._next_earliest_sync = None

        # Setup sync timer
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._trigger_background_sync)

        # Setup connection check timer
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self._trigger_background_connection_check)

        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'BigTime-Client/1.0'
        })

        # Set API key in session headers if available
        if self.config.api_key:
            self._session.headers['Authorization'] = f'Bearer {self.config.api_key}'
            logger.debug(f"Session initialized with API key: {self.config.api_key[:8]}... (length={len(self.config.api_key)})")
        else:
            logger.debug("No API key configured for session")

    def _trigger_background_sync(self) -> None:
        """Trigger inbound sync (pull updates) in background thread to avoid blocking UI.

        Called by timer periodically. Pulls server updates without pushing local changes.
        """
        def background_sync():
            try:
                self._pull_server_updates_only()
            except Exception as e:
                logger.error(f"Background inbound sync error: {e}")

        sync_thread = threading.Thread(target=background_sync, daemon=True)
        sync_thread.start()

    def _trigger_background_connection_check(self):
        """Trigger connection check in background thread to avoid blocking UI

        Checks connection every 500ms to keep status display current.
        """
        def background_check():
            try:
                self.check_connection()
            except Exception as e:
                logger.debug(f"Background connection check error: {e}")

        check_thread = threading.Thread(target=background_check, daemon=True)
        check_thread.start()

    def repair_pending_and_failed_logs(self) -> int:
        """Repair local logs that are missing critical fields (e.g., client_id/device_id).

        Public method: usable by other components if needed (e.g., tools or maintenance actions).
        Returns the number of repaired log rows.
        """
        repaired = 0
        try:
            # Collect pending logs using helper
            pending_logs = db_helpers.get_pending_logs()

            # Collect failed logs using single connection
            failed_logs: List[TimeLog] = []
            conn = db_helpers.get_connection()
            try:
                cursor = conn.execute(
                    """
                    SELECT id, client_id, remote_id, badge, clock_in, clock_out,
                           device_id, device_ts, sync_state, created_at, updated_at
                    FROM logs
                    WHERE sync_state = ?
                    ORDER BY created_at
                    """,
                    (SyncState.FAILED.value,)
                )
                for row in cursor.fetchall():
                    failed_logs.append(db_helpers._row_to_timelog(row))

                # Repair missing client_id/device_id in same transaction
                to_check = pending_logs + failed_logs
                if to_check:
                    now = format_datetime(datetime.now())
                    for log in to_check:
                        needs_update = False
                        new_client_id = log.client_id
                        new_device_id = log.device_id

                        if not new_client_id or not str(new_client_id).strip():
                            new_client_id = str(uuid.uuid4())
                            needs_update = True

                        if not new_device_id or not str(new_device_id).strip():
                            new_device_id = self.config.device_id
                            needs_update = True

                        if needs_update:
                            try:
                                conn.execute(
                                    """
                                    UPDATE logs
                                    SET client_id = ?, device_id = ?, sync_state = ?, updated_at = ?
                                    WHERE id = ?
                                    """,
                                    (new_client_id, new_device_id, SyncState.PENDING.value, now, log.id)
                                )
                                repaired += 1
                            except Exception as e:
                                logger.warning(f"Failed repairing log {log.id}: {e}")

                    conn.commit()

            finally:
                conn.close()

        except Exception as e:
            logger.warning(f"Error while repairing logs: {e}")

        return repaired

    def _load_config(self) -> ServerConfig:
        """Load server configuration from settings"""
        device_id = db_helpers.get_setting('device_id', '')

        # Auto-generate device ID if not set
        if not device_id:
            import platform
            hostname = platform.node() or 'unknown'
            device_id = f"bigtime-{hostname}-{uuid.uuid4().hex[:8]}"
            db_helpers.set_setting('device_id', device_id)
            logger.info(f"Generated new device ID: {device_id}")

        config = ServerConfig(
            server_url=db_helpers.get_setting('server_url', ''),
            device_id=device_id,
            api_key=db_helpers.get_setting('api_key', ''),
            sync_interval=int(db_helpers.get_setting('sync_interval', '30')),
            timeout=int(db_helpers.get_setting('timeout', '10'))
        )

        return config

    def update_config(self, config: ServerConfig):
        """Update server configuration"""
        old_running = self.is_running

        # Stop service if running
        if old_running:
            self.stop()

        # Update config in memory
        self.config = config

        # Save to database
        db_helpers.set_setting('server_url', config.server_url)
        db_helpers.set_setting('device_id', config.device_id)
        db_helpers.set_setting('api_key', config.api_key)
        db_helpers.set_setting('sync_interval', str(config.sync_interval))
        db_helpers.set_setting('timeout', str(config.timeout))

        logger.info(f"Server configuration updated: {config.server_url}")

        # Update session headers
        if config.api_key:
            self._session.headers['Authorization'] = f'Bearer {config.api_key}'
        else:
            # Remove auth header if no API key
            self._session.headers.pop('Authorization', None)

        # Restart if it was running and is now properly configured
        if old_running or (config.server_url and config.api_key):
            self.start()

    def start(self):
        """Start background sync service"""
        if not self.config.server_url or not self.config.api_key:
            logger.info("Server URL or API key not configured, sync service not started")
            return False

        self.is_running = True

        # Perform initial sync in background thread to avoid freezing UI
        def background_initial_sync():
            try:
                self.full_sync_now()
            except Exception as e:
                logger.warning(f"Initial sync failed (will retry on timer): {e}")

        initial_sync_thread = threading.Thread(target=background_initial_sync, daemon=True)
        initial_sync_thread.start()

        # Start sync timer
        self.sync_timer.start(self.config.sync_interval * 1000)

        # Start connection check timer (every 500ms for responsive status updates)
        self.connection_timer.start(500)

        logger.info("Remote sync service started")
        return True

    def stop(self):
        """Stop background sync service"""
        self.is_running = False
        self.sync_timer.stop()
        self.connection_timer.stop()
        logger.info("Remote sync service stopped")

    def is_configured(self) -> bool:
        """Check if sync service is properly configured"""
        return bool(self.config.server_url and self.config.api_key)

    def check_connection(self):
        """Check if server is reachable"""
        if not self.is_configured():
            return False

        try:
            response = self._session.get(
                f"{self.config.server_url}/health",
                timeout=3  # Short timeout to prevent UI freezing
            )
            is_online = response.status_code == 200

            if response.status_code == 401:
                logger.warning(f"Unauthorized (401) on /health - API key may be invalid: {self.config.api_key[:8]}...")
            elif response.status_code != 200:
                logger.debug(f"Health check returned {response.status_code}: {response.text[:200]}")

            # Store connection state for get_sync_status
            self.is_online = is_online

            # Emit status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

            return is_online

        except Exception as e:
            logger.debug(f"Connection check failed: {e}")
            self.is_online = False

            # Emit status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())
            return False

    def full_sync_now(self):
        """Perform immediate full database synchronization"""
        logger.info("full_sync_now called - forcing complete database sync")

        if not self.is_configured():
            logger.warning("full_sync_now: not configured")
            return False

        # Prevent concurrent syncs (thread-safe)
        if not self._sync_lock.acquire(blocking=False):
            logger.warning("full_sync_now: already syncing")
            return False

        try:
            self.is_syncing = True
            logger.info("full_sync_now: starting full sync process")

            # Emit syncing status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

            success = True

            # Ensure previously failed logs will be retried
            reset_count = 0
            try:
                reset_count = db_helpers.reset_failed_logs_to_pending()
            except Exception as e:
                logger.warning(f"Unable to reset failed logs to pending: {e}")
            if reset_count:
                logger.info(f"full_sync_now: reset {reset_count} failed logs to pending")

            # Repair missing fields (e.g., client_id) on pending/failed logs so they can sync
            repaired = self.repair_pending_and_failed_logs()
            if repaired:
                logger.info(f"full_sync_now: repaired {repaired} local logs before sync")

            # Push all local employees to server first
            logger.info("full_sync_now: pushing local employees to server")
            if not self.push_all_employees():
                logger.warning("Failed to push some employees to server")
                success = False

            # Push pending logs (now that employees should exist on server)
            logger.info("full_sync_now: pushing pending logs")
            if not self.push_pending_logs():
                success = False

            # Perform full database synchronization from server
            logger.info("full_sync_now: performing full database sync")
            if not self.pull_full_database():
                success = False

            if success:
                self.last_sync = format_datetime(datetime.now())
                self.last_error = None
                # Store last full sync time
                db_helpers.set_setting('last_full_sync', self.last_sync)
                # Clear any tracked changes since we've just reconciled everything
                try:
                    db_helpers.clear_all_changes()
                except Exception as e:
                    logger.debug(f"Failed to clear change tracking after sync: {e}")
                logger.info("Full database synchronization completed successfully")

            return success

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Full sync failed: {e}")
            return False

        finally:
            self.is_syncing = False
            try:
                self._sync_lock.release()
            except Exception as e:
                logger.debug(f"Failed to release sync lock (may not have been acquired): {e}")

            # Emit final status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

    def sync_now(self) -> bool:
        """Perform immediate outbound sync (push pending changes) only, no wait for responses.

        Outbound sync happens immediately on data changes without waiting for inbound updates.
        This is called when user makes local changes (clock in/out, employee edits, etc).
        """
        logger.info("sync_now (outbound) called")

        if not self.is_configured():
            logger.warning("sync_now: not configured")
            return False

        # For outbound sync, we only push pending changes, no throttling
        # Prevent concurrent syncs (thread-safe)
        if not self._sync_lock.acquire(blocking=False):
            logger.warning("sync_now: already syncing")
            return False

        try:
            self.is_syncing = True
            logger.info("sync_now: starting outbound sync (push changes)")

            # Emit syncing status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

            # Process tracked changes immediately (outbound sync)
            logger.info("sync_now: processing pending changes")
            success = self.process_pending_changes()

            if success:
                self.last_sync = format_datetime(datetime.now())
                self.last_error = None
                logger.debug("Outbound sync completed successfully")
                # Reset backoff on success
                self._consecutive_failures = 0
                self._next_earliest_sync = None
            else:
                logger.warning("Outbound sync encountered some failures")

            return success

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Outbound sync failed: {e}")
            return False

        finally:
            self.is_syncing = False
            try:
                self._sync_lock.release()
            except Exception as e:
                logger.debug(f"Failed to release sync lock: {e}")

            # Emit final status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

            # Set/update backoff based on result
            if self.last_error:
                self._consecutive_failures = min(self._consecutive_failures + 1, 6)
                # Backoff schedule: 2,4,8,16,32,64 seconds (capped)
                delay_seconds = 2 ** self._consecutive_failures
                # Keep some upper bound reasonable (e.g., 60s)
                delay_seconds = min(delay_seconds, 60)
                self._next_earliest_sync = datetime.now() + timedelta(seconds=delay_seconds)
            else:
                self._consecutive_failures = 0
                self._next_earliest_sync = None

    def full_sync_now(self) -> bool:
        """Perform full bidirectional sync (outbound + inbound).

        Used for initial sync and manual full sync requests. Applies throttling
        to avoid hammering the server with repeated requests.
        """
        logger.info("full_sync_now called")

        if not self.is_configured():
            logger.warning("full_sync_now: not configured")
            return False

        # Throttle full sync attempts (minimum 5 seconds between attempts)
        now = datetime.now()
        if (
            self.last_sync_attempt
            and (now - self.last_sync_attempt).total_seconds() < 5
        ):
            logger.debug("full_sync_now: throttled (last attempt too recent)")
            return False

        # Exponential backoff after failures
        if self._next_earliest_sync and now < self._next_earliest_sync:
            wait_ms = int((self._next_earliest_sync - now).total_seconds() * 1000)
            logger.debug(f"full_sync_now: backoff active, wait {wait_ms}ms")
            return False

        # Prevent concurrent syncs (thread-safe)
        if not self._sync_lock.acquire(blocking=False):
            logger.warning("full_sync_now: already syncing")
            return False

        # Record attempt time only after we successfully acquire the lock
        self.last_sync_attempt = now

        try:
            self.is_syncing = True
            logger.info("full_sync_now: starting full sync (push + pull)")

            # Emit syncing status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

            success = True

            # Process tracked changes (outbound)
            logger.info("full_sync_now: processing pending changes")
            if not self.process_pending_changes():
                logger.warning("Failed to process some pending changes")
                success = False

            # Pull updates from server (inbound)
            logger.info("full_sync_now: pulling updates from server")
            if not self.pull_server_updates():
                success = False

            if success:
                # Clear all tracked changes on successful sync
                db_helpers.clear_all_changes()
                self.last_sync = format_datetime(datetime.now())
                self.last_error = None
                logger.debug("Full sync completed successfully")
                # Reset backoff on success
                self._consecutive_failures = 0
                self._next_earliest_sync = None

            return success

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Full sync failed: {e}")
            return False

        finally:
            self.is_syncing = False
            try:
                self._sync_lock.release()
            except Exception as e:
                logger.debug(f"Failed to release sync lock: {e}")

            # Emit final status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

            # Set/update backoff based on result
            if self.last_error:
                self._consecutive_failures = min(self._consecutive_failures + 1, 6)
                # Backoff schedule: 2,4,8,16,32,64 seconds (capped)
                delay_seconds = 2 ** self._consecutive_failures
                delay_seconds = min(delay_seconds, 60)
                self._next_earliest_sync = datetime.now() + timedelta(seconds=delay_seconds)
            else:
                self._consecutive_failures = 0
                self._next_earliest_sync = None

    def _pull_server_updates_only(self) -> bool:
        """Pull updates from server (inbound sync only, no outbound push).

        Called by timer periodically to check for server updates. No throttling,
        runs on a regular schedule. Does not push local changes.
        """
        logger.info("_pull_server_updates_only called")

        if not self.is_configured():
            return False

        # Prevent concurrent syncs
        if not self._sync_lock.acquire(blocking=False):
            logger.debug("_pull_server_updates_only: already syncing, skipping inbound check")
            return False

        try:
            self.is_syncing = True
            logger.debug("_pull_server_updates_only: pulling updates from server")

            # Emit syncing status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

            # Pull updates from server only (no pushing)
            success = self.pull_server_updates()

            if success:
                self.last_sync = format_datetime(datetime.now())
                logger.debug("Inbound sync completed successfully")

            return success

        except Exception as e:
            logger.error(f"Inbound sync failed: {e}")
            return False

        finally:
            self.is_syncing = False
            try:
                self._sync_lock.release()
            except Exception as e:
                logger.debug(f"Failed to release sync lock: {e}")

            # Emit final status update
            status = self.get_sync_status()
            self.sync_status_changed.emit(status.to_dict())

    def process_pending_changes(self) -> bool:
        """Process all pending changes tracked in the database"""
        try:
            pending_changes = db_helpers.get_pending_changes()
            logger.info(f"Processing {len(pending_changes)} pending changes")

            if not pending_changes:
                logger.info("No pending changes to process")
                return True

            # Reorder to ensure log deletions are processed before employee deletion
            order = [
                'log_delete',
                'employee_delete',
                'employee_update',
                'employee_create',
                'log_update',
                'log_create',
            ]
            pending_changes.sort(key=lambda ch: order.index(ch['change_type']) if ch['change_type'] in order else len(order))

            success = True
            for change in pending_changes:
                change_type = change['change_type']
                entity_id = change['entity_id']
                change_data = change['change_data']

                logger.debug(f"Processing {change_type} for {entity_id}")

                if change_type == 'employee_create':
                    # Get employee data and push to server
                    employee = db_helpers.get_employee_by_badge(entity_id)
                    if employee and self.sync_employee_to_server(employee):
                        db_helpers.clear_change(change_type, entity_id)
                    else:
                        success = False

                elif change_type == 'employee_update':
                    # Get employee data and push to server using PUT (not POST)
                    employee = db_helpers.get_employee_by_badge(entity_id)
                    if employee and self.push_employee_update(employee):
                        db_helpers.clear_change(change_type, entity_id)
                    else:
                        success = False

                elif change_type == 'employee_delete':
                    # Push deletion to server (logs should already be handled by prior log_delete changes)
                    if self.push_employee_deletion(entity_id):
                        db_helpers.clear_change(change_type, entity_id)
                    else:
                        success = False

                elif change_type == 'log_create':
                    # Create new log on server (POST)
                    log_id = int(entity_id)
                    log = db_helpers.get_log_by_id(log_id)
                    if log and self.sync_log_to_server(log):
                        db_helpers.clear_change(change_type, entity_id)
                    else:
                        success = False

                elif change_type == 'log_update':
                    # Update existing log on server (PUT)
                    log_id = int(entity_id)
                    log_obj = db_helpers.get_log_by_id(log_id)
                    if log_obj:
                        # Convert dict to TimeLog object for _update_log_on_server
                        log = TimeLog.from_dict(log_obj)
                        if self._update_log_on_server(log):
                            db_helpers.clear_change(change_type, entity_id)
                        else:
                            success = False
                    else:
                        success = False

                elif change_type == 'log_delete':
                    # Push log deletion to server
                    log_id = int(entity_id)
                    if self.push_log_deletion(log_id):
                        db_helpers.clear_change(change_type, entity_id)
                    else:
                        success = False

            return success

        except Exception as e:
            logger.error(f"Error processing pending changes: {e}")
            return False

    def pull_server_updates(self) -> bool:
        """Pull updates from server (simplified version of full sync)"""
        try:
            # Pull employees from server
            if not self.pull_employees():
                return False

            # Pull logs from server
            if not self.pull_logs():
                return False

            return True

        except Exception as e:
            logger.error(f"Error pulling server updates: {e}")
            return False

    def _fetch_consolidated_sync_data(self) -> Dict[str, Any]:
        """Fetch all sync-related data in consolidated queries to reduce database round-trips.

        Returns a dictionary containing:
        - pending_changes: All pending changes to sync
        - pending_logs: All pending logs
        - employees: All employees (for batch operations)

        This consolidates multiple queries that are commonly used together.
        """
        try:
            return {
                'pending_changes': db_helpers.get_pending_changes(),
                'pending_logs': db_helpers.get_pending_logs(),
                'employees': db_helpers.fetch_all_employees(),
            }
        except Exception as e:
            logger.error(f"Error fetching consolidated sync data: {e}")
            return {
                'pending_changes': [],
                'pending_logs': [],
                'employees': [],
            }

    def push_pending_logs(self) -> bool:
        """Push all pending log entries to server"""
        logger.info("push_pending_logs called")

        try:
            pending_logs = db_helpers.get_pending_logs()
            logger.info(f"Found {len(pending_logs)} pending logs")

            if not pending_logs:
                logger.info("No pending logs to sync")
                return True  # Nothing to sync

            success_count = 0
            failed_logs = []

            for log in pending_logs:
                try:
                    # Validate log data before sync attempt
                    if not self._validate_log_for_sync(log):
                        logger.warning(f"Log {log.id} failed validation, marking as failed")
                        failed_logs.append((log.id, "Invalid log data"))
                        continue

                    if log.clock_out is None:
                        # Clock in - create new log
                        success = self._create_log_on_server(log)
                    else:
                        # Clock out - update existing log
                        success = self._update_log_on_server(log)

                    if success:
                        success_count += 1
                    else:
                        # Mark as failed with retry possibility
                        failed_logs.append((log.id, "Server rejected request"))

                except requests.exceptions.Timeout as e:
                    logger.warning(f"Timeout syncing log {log.id}: {e}")
                    # Don't mark as failed for timeouts - retry next time
                    continue
                except requests.exceptions.ConnectionError as e:
                    logger.warning(f"Connection error syncing log {log.id}: {e}")
                    # Don't mark as failed for connection errors - retry next time
                    continue
                except Exception as e:
                    logger.error(f"Failed to sync log {log.id}: {e}")
                    failed_logs.append((log.id, str(e)))

            # Batch update failed logs to avoid multiple database transactions
            if failed_logs:
                self._batch_mark_logs_failed(failed_logs)

            logger.info(f"Synced {success_count}/{len(pending_logs)} pending logs")
            return success_count == len(pending_logs)

        except Exception as e:
            logger.error(f"Failed to push pending logs: {e}")
            return False

    def _create_log_on_server(self, log: TimeLog) -> bool:
        """Create a log entry on the server with retry logic"""
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                payload = CreateLogRequest(
                    client_id=log.client_id,
                    badge=log.badge,
                    clock_in=log.clock_in,
                    device_id=log.device_id or self.config.device_id,
                    device_ts=log.device_ts
                ).to_dict()

                response = self._session.post(
                    f"{self.config.server_url}/api/v1/logs",
                    json=payload,
                    timeout=self.config.timeout
                )

                if response.status_code in (200, 201):
                    data = response.json()
                    if data.get('success'):
                        remote_id = data.get('data', {}).get('id')
                        db_helpers.set_log_synced(log.id, remote_id)
                        return True

                # Handle 409 conflict - employee already clocked in on server
                elif response.status_code == 409:
                    logger.warning(f"Conflict creating log for badge {log.badge}: {response.text}")
                    logger.debug(f"409 Conflict! Badge: {log.badge}, Client ID: {log.client_id}")
                    logger.debug(f"Server response: {response.text}")

                    # Try to resolve conflict by syncing server logs for this employee
                    if self._resolve_clock_in_conflict(log):
                        logger.debug("409 conflict resolved successfully")
                        return True
                    else:
                        logger.debug("409 conflict could not be resolved, marking as failed")
                        # Mark as failed for manual review
                        db_helpers.set_log_failed(log.id)
                        return False

                # For other HTTP errors, log and potentially retry
                elif response.status_code >= 500:
                    # Server error - might be temporary, retry
                    logger.warning(f"Server error on attempt {attempt + 1}: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Server error after {max_retries} attempts: {response.status_code}")
                        return False

                else:
                    # Client error (4xx) - don't retry
                    logger.error(f"Client error creating log: {response.status_code} - {response.text}")
                    return False

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"Network error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error(f"Network error after {max_retries} attempts: {e}")
                    # Don't mark as failed - network errors should allow retry later
                    raise

            except Exception as e:
                logger.error(f"Unexpected error creating log on server: {e}")
                return False

        # If we get here, all retries failed
        return False

    def _resolve_clock_in_conflict(self, local_log: TimeLog) -> bool:
        """Resolve a clock-in conflict by syncing server state"""
        try:
            logger.info(f"Resolving clock-in conflict for badge {local_log.badge}")
            logger.debug(f"Resolving 409 conflict for badge {local_log.badge}, client_id: {local_log.client_id}")

            # Fetch server logs for this employee to see the current state
            response = self._session.get(
                f"{self.config.server_url}/api/v1/logs",
                params={'badge': local_log.badge, 'limit': 10},
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    server_logs = data.get('data', {}).get('logs', [])
                    logger.debug(f"Found {len(server_logs)} server logs for badge {local_log.badge}")

                    # Find the open log on server
                    server_open_log = None
                    for server_log_data in server_logs:
                        logger.debug(f"Server log - ID: {server_log_data.get('id')}, client_id: {server_log_data.get('client_id')}, clock_out: {server_log_data.get('clock_out')}")
                        if not server_log_data.get('clock_out'):
                            server_open_log = server_log_data
                            break

                    if server_open_log:
                        logger.info(f"Found open log on server: ID {server_open_log.get('id')}")
                        logger.debug(f"Found open server log - ID: {server_open_log.get('id')}, client_id: {server_open_log.get('client_id')}")

                        # Check if this is the same log (by client_id) or a different one
                        server_client_id = server_open_log.get('client_id')
                        if server_client_id == local_log.client_id:
                            # Same log - server already has it, mark as synced
                            logger.info("Server already has this log, marking as synced")
                            logger.debug(f"Server already has our log (client_id: {server_client_id}) - sync worked!")
                            remote_id = server_open_log.get('id')
                            db_helpers.set_log_synced(local_log.id, remote_id)
                            return True
                        else:
                            # Different log - there's a real conflict
                            logger.warning(f"Real conflict: Server has different open log (client_id: {server_client_id})")
                            logger.debug(f"Real conflict - Server has different client_id: {server_client_id} vs ours: {local_log.client_id}")
                            # For now, mark local log as failed and let user handle it
                            return False
                    else:
                        logger.warning("Server said employee already clocked in, but no open log found")
                        return False

            logger.error(f"Failed to fetch server logs for conflict resolution: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"Error resolving clock-in conflict: {e}")
            return False

    def _validate_log_for_sync(self, log: TimeLog) -> bool:
        """Validate log data before attempting sync"""
        try:
            if not log.badge or not log.badge.strip():
                logger.error(f"Log {log.id} has invalid badge: '{log.badge}'")
                return False

            if not log.client_id:
                logger.error(f"Log {log.id} missing client_id")
                return False

            if not log.clock_in:
                logger.error(f"Log {log.id} missing clock_in time")
                return False

            # Validate datetime format
            from shared.utils import parse_datetime
            if not parse_datetime(log.clock_in):
                logger.error(f"Log {log.id} has invalid clock_in format: '{log.clock_in}'")
                return False

            if log.clock_out and not parse_datetime(log.clock_out):
                logger.error(f"Log {log.id} has invalid clock_out format: '{log.clock_out}'")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating log {log.id}: {e}")
            return False

    def _batch_mark_logs_failed(self, failed_logs: list):
        """Batch mark multiple logs as failed"""
        try:
            import sqlite3

            from shared.db_helpers import get_connection
            from shared.models import SyncState
            from shared.utils import format_datetime

            if not failed_logs:
                return

            conn = get_connection()
            try:
                conn.execute("BEGIN TRANSACTION")

                now = format_datetime(datetime.now())

                # Extract log IDs and build WHERE IN clause for single statement
                log_ids = [log_id for log_id, _ in failed_logs]
                placeholders = ','.join('?' * len(log_ids))

                # Single UPDATE statement for all logs
                conn.execute(f"""
                    UPDATE logs
                    SET sync_state = ?, updated_at = ?
                    WHERE id IN ({placeholders})
                """, [SyncState.FAILED.value, now] + log_ids)

                # Log individual failure reasons
                for log_id, error_msg in failed_logs:
                    logger.warning(f"Marked log {log_id} as failed: {error_msg}")

                conn.commit()

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to batch update log states: {e}")
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error in batch mark logs failed: {e}")

    def _update_log_on_server(self, log: TimeLog) -> bool:
        """Update a log entry on the server"""
        try:
            # Find the remote ID for this log
            remote_id = log.remote_id
            if not remote_id:
                # Try to find by client_id
                response = self._session.get(
                    f"{self.config.server_url}/api/v1/logs",
                    params={'badge': log.badge},
                    timeout=self.config.timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        logs = data.get('data', {}).get('logs', [])
                        for server_log in logs:
                            if server_log.get('client_id') == log.client_id:
                                remote_id = server_log.get('id')
                                break

                if not remote_id:
                    # Remote does not have this log. Fallback: create it first, then update if closed
                    logger.warning(f"No remote log found for local log {log.id}; creating on server then updating if needed")

                    # Create the log (open) on server
                    create_payload = CreateLogRequest(
                        client_id=log.client_id,
                        badge=log.badge,
                        clock_in=log.clock_in,
                        device_id=log.device_id or self.config.device_id,
                        device_ts=log.device_ts
                    ).to_dict()

                    create_resp = self._session.post(
                        f"{self.config.server_url}/api/v1/logs",
                        json=create_payload,
                        timeout=self.config.timeout
                    )

                    if create_resp.status_code in (200, 201):
                        create_data = create_resp.json()
                        if create_data.get('success'):
                            remote_id = create_data.get('data', {}).get('id')
                            if remote_id:
                                # Store remote_id locally but keep state pending for the close
                                try:
                                    db_helpers.update_log_remote_id(log.id, remote_id)
                                except Exception as e:
                                    logger.debug(f"Failed to update remote_id for log {log.id}: {e}")
                            else:
                                logger.error(f"Create response missing remote id for log {log.id}")
                                return False
                        else:
                            logger.error(f"Server create failed for log {log.id}: {create_data}")
                            return False
                    elif create_resp.status_code == 409:
                        # Conflict: server might already have the log but we couldn't find it; retry lookup by client_id
                        retry = self._session.get(
                            f"{self.config.server_url}/api/v1/logs",
                            params={'badge': log.badge},
                            timeout=self.config.timeout
                        )
                        if retry.status_code == 200:
                            rdata = retry.json()
                            if rdata.get('success'):
                                for s in rdata.get('data', {}).get('logs', []):
                                    if s.get('client_id') == log.client_id:
                                        remote_id = s.get('id')
                                        if remote_id:
                                            try:
                                                db_helpers.update_log_remote_id(log.id, remote_id)
                                            except Exception as e:
                                                logger.debug(f"Failed to update remote_id for log {log.id}: {e}")
                                        break
                        if not remote_id:
                            logger.error(f"Could not resolve remote id after 409 for log {log.id}")
                            return False
                    else:
                        logger.error(f"Failed to create log on server: {create_resp.status_code} - {create_resp.text}")
                        return False

            payload = UpdateLogRequest(
                client_id=log.client_id,
                clock_out=log.clock_out,
                device_id=log.device_id or self.config.device_id,
                device_ts=log.device_ts
            ).to_dict()

            response = self._session.put(
                f"{self.config.server_url}/api/v1/logs/{remote_id}",
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    db_helpers.set_log_synced(log.id, remote_id)
                    return True

            # If server doesn't have this remote id, try create-then-update path
            if response.status_code == 404:
                logger.info(f"Server returned 404 updating log {log.id} (remote_id={remote_id}); attempting create then update")
                # Attempt the same fallback used earlier: create first
                create_payload = CreateLogRequest(
                    client_id=log.client_id,
                    badge=log.badge,
                    clock_in=log.clock_in,
                    device_id=log.device_id or self.config.device_id,
                    device_ts=log.device_ts
                ).to_dict()

                create_resp = self._session.post(
                    f"{self.config.server_url}/api/v1/logs",
                    json=create_payload,
                    timeout=self.config.timeout
                )

                if create_resp.status_code in (200, 201):
                    cdata = create_resp.json()
                    if cdata.get('success'):
                        new_remote_id = cdata.get('data', {}).get('id')
                        if new_remote_id:
                            try:
                                db_helpers.update_log_remote_id(log.id, new_remote_id)
                            except Exception:
                                pass
                            # If this log is closed, send the update too
                            if log.clock_out:
                                upd = self._session.put(
                                    f"{self.config.server_url}/api/v1/logs/{new_remote_id}",
                                    json=payload,
                                    timeout=self.config.timeout
                                )
                                if upd.status_code == 200 and upd.json().get('success'):
                                    db_helpers.set_log_synced(log.id, new_remote_id)
                                    return True
                                else:
                                    logger.error(f"Failed to close newly created log {new_remote_id}: {upd.status_code} - {upd.text}")
                                    return False
                            else:
                                # Open log created; mark as synced
                                db_helpers.set_log_synced(log.id, new_remote_id)
                                return True
                elif create_resp.status_code == 409:
                    # Retry lookup by client_id in case of race
                    retry = self._session.get(
                        f"{self.config.server_url}/api/v1/logs",
                        params={'badge': log.badge},
                        timeout=self.config.timeout
                    )
                    if retry.status_code == 200:
                        rdata = retry.json()
                        if rdata.get('success'):
                            for s in rdata.get('data', {}).get('logs', []):
                                if s.get('client_id') == log.client_id:
                                    new_remote_id = s.get('id')
                                    if new_remote_id:
                                        try:
                                            db_helpers.update_log_remote_id(log.id, new_remote_id)
                                        except Exception:
                                            pass
                                        # If closed, update
                                        if log.clock_out:
                                            upd = self._session.put(
                                                f"{self.config.server_url}/api/v1/logs/{new_remote_id}",
                                                json=payload,
                                                timeout=self.config.timeout
                                            )
                                            if upd.status_code == 200 and upd.json().get('success'):
                                                db_helpers.set_log_synced(log.id, new_remote_id)
                                                return True
                                            else:
                                                return False
                                        else:
                                            db_helpers.set_log_synced(log.id, new_remote_id)
                                            return True
                    return False

            logger.error(f"Failed to update log on server: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Error updating log on server: {e}")
            return False

    def pull_employees(self) -> bool:
        """Pull employee updates from server"""
        try:
            response = self._session.get(
                f"{self.config.server_url}/api/v1/employees",
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    employees = data.get('data', {}).get('employees', [])

                    # Get pending deletions to avoid re-adding deleted employees
                    pending_changes = db_helpers.get_pending_changes()
                    pending_deletions = {change['entity_id'] for change in pending_changes
                                       if change['change_type'] == 'employee_delete'}

                    # Update local employee database
                    for emp_data in employees:
                        emp = Employee.from_dict(emp_data)

                        # Skip employees that are pending deletion
                        if emp.badge in pending_deletions:
                            logger.debug(f"Skipping server employee {emp.badge} - pending local deletion")
                            continue

                        # Check if employee exists locally
                        existing = db_helpers.get_employee_by_badge(emp.badge)

                        if existing:
                            # Update existing employee (but don't track as change since it's from server)
                            # Temporarily disable change tracking for server updates
                            db_helpers.update_employee_by_badge_no_tracking(emp.badge, emp.to_dict())
                        else:
                            # Insert new employee (but don't track as change since it's from server)
                            db_helpers.insert_employee_no_tracking(emp)

                    # Emit employee sync signal
                    self.employee_synced.emit({'count': len(employees)})

                    logger.info(f"Synced {len(employees)} employees from server")
                    return True

            logger.error(f"Failed to pull employees: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Error pulling employees: {e}")
            return False

    def push_all_employees(self) -> bool:
        """Push all local employees to server to ensure they exist before syncing logs"""
        try:
            logger.info("Pushing all local employees to server")

            # Get all local employees
            local_employees = db_helpers.fetch_all_employees()

            if not local_employees:
                logger.info("No local employees to push")
                return True

            success_count = 0
            total_count = len(local_employees)

            for employee in local_employees:
                try:
                    # Try to create employee first using the dedicated method
                    if self.push_employee_creation(employee):
                        success_count += 1
                        logger.debug(f"Successfully synced employee {employee.badge} to server")
                    else:
                        logger.warning(f"Failed to sync employee {employee.badge} to server")

                except Exception as e:
                    logger.warning(f"Error syncing employee {employee.badge}: {e}")
                    continue

            logger.info(f"Employee push completed: {success_count}/{total_count} employees synced")

            # Return success if we synced at least some employees, or if there were none to sync
            return success_count == total_count or total_count == 0

        except Exception as e:
            logger.error(f"Error pushing employees to server: {e}")
            return False

    def push_employee_update(self, employee: Employee) -> bool:
        """Push a single employee update to server"""
        try:
            payload = employee.to_dict()

            response = self._session.put(
                f"{self.config.server_url}/api/v1/employees/{employee.badge}",
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code in (200, 201):
                data = response.json()
                if data.get('success'):
                    logger.info(f"Successfully synced employee {employee.badge} to server")
                    return True

            logger.error(f"Failed to sync employee to server: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Error syncing employee to server: {e}")
            return False

    def push_employee_creation(self, employee: Employee) -> bool:
        """Push a new employee creation to server"""
        try:
            payload = employee.to_dict()

            response = self._session.post(
                f"{self.config.server_url}/api/v1/employees",
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code in (200, 201):
                data = response.json()
                if data.get('success'):
                    logger.info(f"Successfully created employee {employee.badge} on server")
                    return True
            elif response.status_code == 409:
                # Employee already exists, this is actually success for our purposes
                logger.debug(f"Employee {employee.badge} already exists on server")
                return True

            logger.error(f"Failed to create employee on server: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Error syncing employee to server: {e}")
            return False

    def pull_full_database(self) -> bool:
        """Perform full database synchronization from server"""
        logger.info("Starting full database synchronization from server")

        success = True

        # Pull employees first
        if not self.pull_employees():
            logger.warning("Failed to sync employees from server")
            success = False

        # Pull logs
        if not self.pull_logs():
            logger.warning("Failed to sync logs from server")
            success = False

        if not success:
            logger.error("Full database synchronization completed with errors")

        return success

    def pull_logs(self) -> bool:
        """Pull all logs from server and merge with local database"""
        try:
            logger.info("Pulling logs from server")

            # Get logs from server (without date filters to get everything)
            response = self._session.get(
                f"{self.config.server_url}/api/v1/logs",
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    server_logs = data.get('data', {}).get('logs', [])

                    # Build a set of remote IDs pending deletion to avoid re-adding them
                    try:
                        pending_changes = db_helpers.get_pending_changes()
                        pending_log_deletions = {int(ch['entity_id']) for ch in pending_changes
                                                  if ch['change_type'] == 'log_delete' and ch['entity_id'].isdigit()}
                    except Exception:
                        pending_log_deletions = set()

                    synced_count = 0
                    updated_count = 0

                    for log_data in server_logs:
                        # Skip logs that we are about to delete on the server
                        try:
                            sid = log_data.get('id')
                            if sid is not None and int(sid) in pending_log_deletions:
                                logger.debug(f"Skipping server log {sid} - pending local deletion")
                                continue
                        except Exception:
                            pass

                        try:
                            # Convert server log data to TimeLog object
                            server_log = TimeLog(
                                id=log_data.get('id'),
                                client_id=log_data.get('client_id'),
                                badge=log_data.get('badge'),
                                clock_in=log_data.get('clock_in'),
                                clock_out=log_data.get('clock_out'),
                                device_id=log_data.get('device_id'),
                                device_ts=log_data.get('device_ts'),
                                created_at=log_data.get('created_at'),
                                updated_at=log_data.get('updated_at')
                            )

                            # Check if we already have this log locally
                            existing_log = None
                            if server_log.client_id:
                                existing_log = db_helpers.get_log_by_client_id(server_log.client_id)

                            if existing_log:
                                # Update existing log if server version is newer
                                if (server_log.updated_at and existing_log.updated_at and
                                    server_log.updated_at > existing_log.updated_at):

                                    # Update the local log (no tracking since it's from server)
                                    db_helpers.update_log_no_tracking(existing_log.id, {
                                        'clock_out': server_log.clock_out,
                                        'updated_at': server_log.updated_at
                                    })
                                    # Mark as synced with server ID
                                    db_helpers.set_log_synced(existing_log.id, server_log.id)
                                    updated_count += 1
                                    logger.debug(f"Updated local log {existing_log.id} from server")

                            else:
                                # This is a new log from server, insert it locally
                                # But mark it as already synced to avoid pushing it back
                                new_log = TimeLog(
                                    client_id=server_log.client_id or str(uuid.uuid4()),
                                    badge=server_log.badge,
                                    clock_in=server_log.clock_in,
                                    clock_out=server_log.clock_out,
                                    device_id=server_log.device_id,
                                    device_ts=server_log.device_ts,
                                    sync_state=SyncState.SYNCED.value  # Already from server
                                )

                                local_id = db_helpers.insert_log_from_object(new_log)
                                if local_id:
                                    # Mark as synced immediately
                                    db_helpers.set_log_synced(local_id, server_log.id)
                                    synced_count += 1
                                    logger.debug(f"Added new log from server: {server_log.badge}")

                        except Exception as e:
                            logger.warning(f"Error processing server log: {e}")
                            continue

                    logger.info(f"Log sync completed: {synced_count} new logs, {updated_count} updated logs")
                    return True

            logger.error(f"Failed to pull logs: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Error pulling logs from server: {e}")
            return False

    def push_employee_deletion(self, badge: str) -> bool:
        """Push employee deletion to server"""
        try:
            response = self._session.delete(
                f"{self.config.server_url}/api/v1/employees/{badge}",
                timeout=self.config.timeout
            )

            if response.status_code in (200, 204):
                data = response.json() if response.text else {'success': True}
                if data.get('success', True):  # Some DELETE responses don't return JSON
                    logger.info(f"Successfully deleted employee {badge} from server")
                    return True
            elif response.status_code == 404:
                # Employee already doesn't exist on server - that's what we want
                logger.info(f"Employee {badge} already deleted from server (404)")
                return True

            logger.error(f"Failed to delete employee from server: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Error deleting employee from server: {e}")
            return False

    def push_log_deletion(self, log_id: int) -> bool:
        """Push log deletion to server"""
        try:
            response = self._session.delete(
                f"{self.config.server_url}/api/v1/logs/{log_id}",
                timeout=self.config.timeout
            )

            if response.status_code in (200, 204):
                data = response.json() if response.text else {'success': True}
                if data.get('success', True):
                    logger.info(f"Successfully deleted log {log_id} from server")
                    return True
            elif response.status_code == 404:
                # Log already doesn't exist on server - that's what we want
                logger.info(f"Log {log_id} already deleted from server (404)")
                return True

            logger.error(f"Failed to delete log from server: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Error deleting log from server: {e}")
            return False

    def create_log_locally(self, badge: str, clock_in_time: str, client_id: Optional[str] = None) -> str:
        """Create a log entry locally and mark for sync"""
        logger.info(f"create_log_locally called: badge={badge}, clock_in_time={clock_in_time}")

        if not client_id:
            client_id = str(uuid.uuid4())

        # Insert with pending sync state
        log_id = db_helpers.insert_log(
            badge=badge,
            clock_in_time=clock_in_time,
            client_id=client_id,
            device_id=self.config.device_id,
            sync_state=SyncState.PENDING.value
        )

        logger.info(f"Created log with ID: {log_id}, client_id: {client_id}")

        # Trigger immediate sync if online
        if self.is_running and self.check_connection():
            logger.info("Connection check passed, calling sync_now()")
            self.sync_now()
        else:
            logger.warning(f"Sync not triggered - is_running: {self.is_running}, connection: {self.is_online}")

        return client_id

    def update_log_locally(self, badge: str, clock_out_time: str) -> bool:
        """Update a log entry locally and mark for sync"""
        success = db_helpers.close_most_recent_log(badge, clock_out_time)

        if success:
            # Trigger immediate sync if online
            if self.is_running and self.check_connection():
                self.sync_now()

        return success

    def get_sync_status(self) -> SyncStatus:
        """Get current sync status"""
        pending_logs = db_helpers.get_pending_logs()
        pending_count = len([log for log in pending_logs if log.sync_state == SyncState.PENDING.value])
        failed_count = len([log for log in pending_logs if log.sync_state == SyncState.FAILED.value])

        return SyncStatus(
            is_online=self.is_online,
            is_syncing=self.is_syncing,
            last_sync=self.last_sync,
            pending_count=pending_count + failed_count,  # Total items needing attention
            pending_logs=pending_count,
            failed_logs=failed_count,
            server_url=self.config.server_url
        )

    def get_last_full_sync(self) -> Optional[str]:
        """Get the timestamp of the last full database synchronization"""
        return db_helpers.get_setting('last_full_sync', None)

    def sync_employee_to_server(self, employee: Employee) -> bool:
        """Sync a single employee to the server"""
        if not self.is_configured():
            return False

        try:
            headers = {'Authorization': f'Bearer {self.config.api_key}'}
            response = requests.post(
                f"{self.config.server_url}/api/v1/employees",
                headers=headers,
                json=employee.to_dict(),
                timeout=10
            )

            if response.status_code == 201:
                logger.info(f"Employee {employee.badge} synced to server")
                self.employee_synced.emit(employee.to_dict())
                return True
            elif response.status_code == 409:
                logger.info(f"Employee {employee.badge} already exists on server")
                return True
            else:
                logger.error(f"Failed to sync employee to server: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error syncing employee to server: {e}")
            return False

    def sync_log_to_server(self, log) -> bool:
        """Sync a single log entry to the server"""
        if not self.is_configured():
            return False

        try:
            headers = {'Authorization': f'Bearer {self.config.api_key}'}

            # Convert log to dict format expected by server
            log_data = {
                'badge': log['badge'],
                'clock_in': log['clock_in'],
                'clock_out': log['clock_out'],
                'client_id': log['client_id'],
                'device_id': log['device_id'],
                'device_ts': log['device_ts']
            }

            response = requests.post(
                f"{self.config.server_url}/api/v1/logs",
                headers=headers,
                json=log_data,
                timeout=10
            )

            if response.status_code == 201:
                # Update local log with remote_id if provided
                response_data = response.json()
                if 'id' in response_data:
                    db_helpers.update_log_remote_id(log['id'], response_data['id'])

                # Mark as synced
                db_helpers.update_log_sync_state(log['id'], SyncState.SYNCED.value)
                logger.info(f"Log {log['id']} synced to server")
                return True
            else:
                logger.error(f"Failed to sync log to server: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error syncing log to server: {e}")
            return False

    def pull_employees_from_server(self) -> List[Employee]:
        """Pull employee list from server and update local database"""
        if not self.is_configured():
            return []

        try:
            headers = {'Authorization': f'Bearer {self.config.api_key}'}
            response = requests.get(
                f"{self.config.server_url}/api/v1/employees",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'employees' in data.get('data', {}):
                    employees_data = data['data']['employees']
                    employees = []

                    for emp_data in employees_data:
                        employee = Employee.from_dict(emp_data)
                        employees.append(employee)

                        # Update local database (upsert)
                        existing = db_helpers.get_employee_by_badge(employee.badge)
                        if existing:
                            # Update existing
                            updates = {
                                'name': employee.name,
                                'phone_number': employee.phone_number,
                                'pin': employee.pin,
                                'department': employee.department,
                                'date_of_birth': employee.date_of_birth,
                                'hire_date': employee.hire_date,
                                'deactivated': employee.deactivated,
                                'ssn': employee.ssn,
                                'period': employee.period,
                                'rate': employee.rate
                            }
                            db_helpers.update_employee_by_badge(employee.badge, updates)
                        else:
                            # Insert new
                            db_helpers.insert_employee(employee)

                    logger.info(f"Pulled {len(employees)} employees from server")
                    return employees
                else:
                    logger.error("Invalid response format from employee endpoint")
                    return []
            else:
                logger.error(f"Failed to pull employees from server: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error pulling employees from server: {e}")
            return []

    def get_server_time(self) -> Optional[datetime]:
        """Get current server time with NTP synchronization"""
        if not self.is_configured():
            return None

        try:
            response = requests.get(
                f"{self.config.server_url}/api/v1/time",
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'server_time' in data.get('data', {}):
                    time_str = data['data']['server_time']
                    # Parse server time
                    return datetime.fromisoformat(time_str.replace('Z', '+00:00'))

        except Exception as e:
            logger.error(f"Error getting server time: {e}")

        return None

    def retry_failed_logs(self):
        """Retry syncing failed logs"""
        try:
            # Reset failed logs to pending via shared helper
            try:
                db_helpers.reset_failed_logs_to_pending()
            except Exception as e:
                logger.warning(f"retry_failed_logs: unable to reset failed logs: {e}")

            # Trigger sync
            return self.sync_now()

        except Exception as e:
            logger.error(f"Failed to retry failed logs: {e}")
            return False


# Global sync service instance
_sync_service = None


def get_sync_service() -> RemoteSyncService:
    """Get the global sync service instance"""
    global _sync_service
    if _sync_service is None:
        _sync_service = RemoteSyncService()
    return _sync_service
