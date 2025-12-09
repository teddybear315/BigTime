"""
Network Worker for BigTime Client
This module provides a QObject worker that runs in a separate thread to handle
all network operations and sync services without blocking the UI.
"""

import requests
import time

from PyQt6.QtCore import QThread, pyqtSignal
from shared import db_helpers


class NetworkWorker(QThread):
    """
    Network worker that handles all sync operations and network calls in background thread.

    This worker manages the sync service and prevents any network operations from
    blocking the main UI thread.
    """

    # UI Update Signals - emitted to main thread
    sync_status_changed = pyqtSignal(dict)  # Sync status updates
    employee_synced = pyqtSignal(dict)      # Employee sync updates
    server_info_updated = pyqtSignal(dict)  # Server info updates
    connection_status_changed = pyqtSignal(bool)  # Connection status

    # Clock and UI signals
    tick = pyqtSignal()  # Regular clock ticks
    clear_status = pyqtSignal()  # Clear status messages

    # Request signals (from main thread to worker)
    start_sync_service = pyqtSignal()
    stop_sync_service = pyqtSignal()
    trigger_manual_sync = pyqtSignal()
    check_server_connection = pyqtSignal()
    fetch_server_info = pyqtSignal()
    get_sync_config = pyqtSignal()
    update_sync_config = pyqtSignal(object)  # Pass ServerConfig object

    # Data change notification signals (trigger immediate sync)
    employee_data_changed = pyqtSignal()  # Employee created/updated/deleted
    time_log_data_changed = pyqtSignal()  # Time log created/updated/deleted

    # Config response signals
    sync_config_retrieved = pyqtSignal(object)  # Return ServerConfig object

    def __init__(self, client=None, tick_interval_ms=1000):
        """Initialize the network worker (runs in its own QThread)."""
        super().__init__()
        self._running = True
        self.tick_interval_ms = tick_interval_ms
        self._status_clear_time = None
        self.client = client
        self.sync_service = None

        # Connect request handlers (these are signals emitted from the GUI/main thread)
        self.start_sync_service.connect(self._start_sync_service)
        self.stop_sync_service.connect(self._stop_sync_service)
        self.trigger_manual_sync.connect(self._trigger_manual_sync)
        self.check_server_connection.connect(self._check_server_connection)
        self.fetch_server_info.connect(self._fetch_server_info)
        self.get_sync_config.connect(self._get_sync_config)
        self.update_sync_config.connect(self._update_sync_config)

        # Connect data change handlers (trigger immediate sync)
        self.employee_data_changed.connect(self._trigger_manual_sync)
        self.time_log_data_changed.connect(self._trigger_manual_sync)

    def run(self):
        """
        Main worker loop for clock ticks and status clearing.

        This method should be connected to the QThread.started signal.
        """
        # QThread.run executes in a new thread
        while self._running:
            try:
                # Emit clock tick signal
                self.tick.emit()

                # Check if it's time to clear status
                now = time.time()
                if self._status_clear_time is not None and now >= self._status_clear_time:
                    self.clear_status.emit()
                    self._status_clear_time = None

                # Sleep for the tick interval
                time.sleep(self.tick_interval_ms / 1000.0)
            except Exception:
                # Protect thread loop from unexpected errors
                time.sleep(1)

    def stop(self) -> None:
        """
        Stop the worker loop gracefully.

        This will cause the run() method to exit on the next iteration.
        Emits tick(False) signal on completion.
        """
        self._running = False

    def update_tick_interval(self, tick_interval_ms: int) -> None:
        """Update timing interval while running.

        Args:
            tick_interval_ms: New interval in milliseconds (minimum 500ms enforced)
        """
        self.tick_interval_ms = max(500, tick_interval_ms)  # Minimum 500ms

    def schedule_status_clear(self, delay_seconds: int = 5) -> None:
        """
        Schedule the status to be cleared after a delay.

        Args:
            delay_seconds: Number of seconds to wait before clearing status (default: 5)

        Note:
            Sets _status_clear_time for status clearing on next tick.
        """
        self._status_clear_time = time.time() + delay_seconds

    def _start_sync_service(self) -> None:
        """Initialize and start sync service in background thread.

        Creates sync service instance, connects signals to emit to main thread,
        and starts service if properly configured. Handles startup errors gracefully.
        """
        try:
            if self.client and not self.sync_service:
                from client.sync_service import get_sync_service

                # Create sync service in this worker thread
                self.sync_service = get_sync_service()

                # Connect sync service signals to forward to main thread
                self.sync_service.sync_status_changed.connect(self.sync_status_changed.emit)
                self.sync_service.employee_synced.connect(self.employee_synced.emit)

                # Start the sync service if configured
                if self.sync_service.is_configured():
                    success = self.sync_service.start()
                    if not success:
                        # Service not configured properly, don't start
                        pass
                else:
                    # Not configured - emit status showing offline
                    from shared.models import SyncStatus
                    status = SyncStatus(is_online=False, is_syncing=False)
                    self.sync_status_changed.emit(status.to_dict())

        except Exception as e:
            # Fail silently - sync service is optional
            import logging
            logger = logging.getLogger('SYNC')
            logger.debug(f"Sync service failed to start: {e}")

    def _stop_sync_service(self) -> None:
        """Stop sync service in background thread.

        Cleanly shuts down sync service and clears reference.
        Handles errors gracefully to ensure thread can exit.
        """
        try:
            if self.sync_service:
                self.sync_service.stop()
                self.sync_service = None
        except Exception:
            pass

    def _trigger_manual_sync(self) -> None:
        """Trigger manual sync in background thread.

        Calls sync_now() on sync service if available.
        Fails silently if service not initialized.
        """
        try:
            if self.sync_service:
                self.sync_service.full_sync_now()
        except Exception:
            pass

    def _check_server_connection(self) -> None:
        """Check server connection in background thread.

        Emits connection_status_changed signal with current connection state.
        Reports False if sync service not initialized.
        """
        try:
            if self.sync_service:
                is_connected = self.sync_service.check_connection()
                self.connection_status_changed.emit(is_connected)
            else:
                self.connection_status_changed.emit(False)
        except Exception:
            self.connection_status_changed.emit(False)

    def _fetch_server_info(self) -> None:
        """Fetch server info in background thread.

        Retrieves server information from configured sync service or emits
        fallback company name from local settings.
        """
        fallback_info = {'company_name': 'BigTime'}

        try:
            if self.sync_service and self.sync_service.is_configured():
                config = self.sync_service.config
                response = requests.get(
                    f"{config.server_url}/api/v1/info",
                    headers={'Authorization': f'Bearer {config.api_key}'},
                    timeout=2
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('success', False):
                        server_info = data.get('data', fallback_info)
                        self.server_info_updated.emit(server_info)
                        return

            self.server_info_updated.emit(fallback_info)

        except Exception:
            self.server_info_updated.emit(fallback_info)

    def _get_sync_config(self) -> None:
        """Get current sync configuration in background thread.

        Emits sync_config_retrieved signal with current or default config.
        """
        try:
            if self.sync_service:
                config = self.sync_service.config
                self.sync_config_retrieved.emit(config)
            else:
                # Return default config if sync service not available
                from shared.models import ServerConfig
                default_config = ServerConfig()
                self.sync_config_retrieved.emit(default_config)
        except Exception:
            # Return default config on error
            from shared.models import ServerConfig
            default_config = ServerConfig()
            self.sync_config_retrieved.emit(default_config)

    def _update_sync_config(self, new_config) -> None:
        """Update sync configuration in background thread.

        Persists config to DB atomically before updating sync service, preventing
        race conditions during OOBE setup when sync_service may not be initialized.

        Args:
            new_config: ServerConfig object with updated settings
        """
        try:
            # Persist all config to DB atomically (visible immediately to all threads)
            db_helpers.set_setting('server_url', new_config.server_url or '')
            db_helpers.set_setting('api_key', new_config.api_key or '')
            db_helpers.set_setting('device_id', new_config.device_id or '')
            db_helpers.set_setting('sync_interval', str(new_config.sync_interval))
            db_helpers.set_setting('timeout', str(new_config.timeout))

            # Update in-memory sync service if it exists
            if self.sync_service:
                self.sync_service.update_config(new_config)
                if new_config.server_url and new_config.api_key and not self.sync_service.is_running:
                    self.sync_service.start()
        except Exception as e:
            import logging
            logger = logging.getLogger('SYNC')
            logger.warning(f"Failed to update sync config: {e}", exc_info=True)
