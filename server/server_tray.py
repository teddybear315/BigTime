"""
BigTime Server - Cross-Platform System Tray Application
Runs the BigTime server as a hidden background service with system tray integration.
Supports Windows, Linux, and macOS with appropriate fallbacks.
"""

import os
import platform
import sys

from PyQt6.QtCore import QThread, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QApplication, QDialog, QMenu, QMessageBox,
                             QSystemTrayIcon)

import shared
from shared.logging_config import get_server_logger
from ui.dialogs.shared import DatabaseSelectDialog
from ui.dialogs.server import *

# Setup standardized logging
logger = get_server_logger()

# Server configuration constants
DEFAULT_SERVER_PORT: int = 5000
STARTUP_DELAY_MS: int = 1000


def is_system_tray_available():
    """Check if system tray is available on current platform"""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return False

    # Additional platform-specific checks
    current_platform = platform.system()

    if current_platform == "Linux":
        # Check for desktop environment that supports system tray
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        if desktop in ['gnome', 'kde', 'xfce', 'mate', 'cinnamon']:
            return True
        # Check if running in X11 or Wayland with tray support
        if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
            return True
        return False

    elif current_platform == "Darwin":  # macOS
        return True  # macOS generally supports system tray

    elif current_platform == "Windows":
        return True  # Windows supports system tray

    return False


class ServerManager(QThread):
    """Manages the Flask server inside a QThread."""

    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    server_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.server_running = False
        self._host = '127.0.0.1'
        self._port = DEFAULT_SERVER_PORT

    def start_server(self, host='127.0.0.1', port=DEFAULT_SERVER_PORT):
        """Start the server thread. The actual server runs inside `run()`."""
        if self.server_running:
            return

        self._host = host
        self._port = port

        # Start QThread; run() will initialize and run the server
        self.start()
        self.server_running = True
        self.server_started.emit()

    def stop_server(self):
        """Stop the server by calling the local shutdown endpoint and wait for the thread to exit.

        Falls back to clearing the running flag if network shutdown fails.
        """
        if not self.server_running:
            return

        try:
            # Attempt graceful shutdown via local admin endpoint
            import requests
            url = f'http://{self._host}:{self._port}/admin/shutdown'
            try:
                requests.post(url, timeout=3)
            except requests.exceptions.ConnectionError:
                # Server already closed, that's fine
                logger.debug("Connection refused during shutdown (server may already be stopping)")
            except Exception as e:
                logger.warning(f"Shutdown request failed: {e}")
        except ImportError:
            # requests not available; continue to fallback
            logger.debug("requests module unavailable; falling back to thread stop.")
        except Exception as e:
            # Shutdown request failed; continue to fallback
            logger.debug(f"Graceful shutdown failed: {e}")

        # Wait briefly for the server thread to exit gracefully
        try:
            self.wait(3000)
        except Exception as e:
            logger.debug(f"Thread wait error: {e}")

        # Ensure running flag cleared and emit signal from main thread (safe here)
        self.server_running = False
        try:
            self.server_stopped.emit()
        except Exception as e:
            logger.debug(f"Failed to emit server_stopped signal: {e}")

    def run(self):
        """Thread entry point: initialize DB and run the server (blocking)."""
        try:
            from server.server import init_server_db
            from server.server import run_server as start_server

            # Initialize database and time service
            init_server_db()

            # Run server (uses Waitress) - blocking call
            start_server(host=self._host, port=self._port)

        except Exception as e:
            # Emit error from the thread
            try:
                self.server_error.emit(str(e))
            except Exception as signal_error:
                logger.error(f"Failed to emit server_error signal: {signal_error}")
        finally:
            # Ensure running flag is cleared when server exits
            self.server_running = False
            try:
                self.server_stopped.emit()
            except Exception as e:
                logger.debug(f"Failed to emit server_stopped signal in finally: {e}")





class BigTimeServerTray(QObject):
    """System tray application for BigTime Server"""

    def __init__(self, app:QApplication):

        super().__init__()

        self.app = app

        # Create system tray
        self.tray_icon = QSystemTrayIcon()

        # Set icon (you can replace with actual icon file)
        self.create_tray_icon()

        # Create context menu
        self.create_context_menu()

        # Server manager
        self.server_manager = ServerManager()
        self.server_manager.server_started.connect(self.on_server_started)
        self.server_manager.server_stopped.connect(self.on_server_stopped)
        self.server_manager.server_error.connect(self.on_server_error)

        # Initialize database before loading settings (fixes "no such table: settings" error)
        try:
            from server.server import init_server_db
            init_server_db()
        except Exception as e:
            logger.error(f"Failed to initialize server database: {e}")

        # Load settings
        self.load_settings()

        # Check if first-time setup is needed
        if not self.setup_completed:
            QTimer.singleShot(500, self.show_ootb_setup)

        # Show tray icon
        self.tray_icon.show()

        # Auto-start server if configured (and setup is completed)
        if getattr(self, 'autostart', True) and self.setup_completed:
            QTimer.singleShot(STARTUP_DELAY_MS, self.start_server)  # Delay to ensure tray is ready

    def create_tray_icon(self):
        """Create the system tray icon"""
        from shared.utils import create_app_icon

        icon = create_app_icon()
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("BigTime Server")

    def create_context_menu(self):
        """Create the right-click context menu"""
        menu = QMenu()

        # Status action (non-clickable info)
        self.status_action = QAction(f"Status: v{shared.__VERSION__} Stopped", self)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addSeparator()

        # Server control actions
        self.start_action = QAction("Start Server", self)
        self.start_action.triggered.connect(self.start_server)
        menu.addAction(self.start_action)

        self.stop_action = QAction("Stop Server", self)
        self.stop_action.triggered.connect(self.stop_server)
        self.stop_action.setEnabled(False)
        menu.addAction(self.stop_action)

        menu.addSeparator()

        # Configuration action
        self.config_action = QAction("Configure...", self)
        self.config_action.triggered.connect(self.show_config)
        menu.addAction(self.config_action)

        # Backup action (disabled by default)
        self.backup_action = QAction("Backup Database", self)
        self.backup_action.triggered.connect(self.backup_database)
        self.backup_action.setEnabled(False)
        menu.addAction(self.backup_action)

        # Restore action (disabled by default)
        self.restore_action = QAction("Restore Database...", self)
        self.restore_action.triggered.connect(self.restore_database)
        self.restore_action.setEnabled(False)
        menu.addAction(self.restore_action)

        # Migrate action (disabled by default)
        self.migrate_db_action = QAction('Migrate Database...', self)
        self.migrate_db_action.triggered.connect(self.migrate_database)
        self.migrate_db_action.setEnabled(False)
        menu.addAction(self.migrate_db_action)


        menu.addSeparator()

        # Separator and quit
        self.quit_action = QAction("Exit", self)
        self.quit_action.triggered.connect(self.quit_application)
        menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(menu)

    def load_settings(self):
        """Load server settings from database"""
        from server.server import get_server_config

        # Load settings from database
        try:
            config = get_server_config()

            # Set defaults
            self.host = config.get('host', '127.0.0.1')
            self.port = config.get('port', DEFAULT_SERVER_PORT)
            self.autostart = config.get('autostart', True)
            self.company_name = config.get('company_name', 'BigTime')
            self.setup_completed = config.get('setup_completed', False)

        except Exception as e:
            # If database is not available, use defaults
            logger.warning(f"Could not load server config from database: {e}")
            self.host = '127.0.0.1'
            self.port = DEFAULT_SERVER_PORT
            self.autostart = True
            self.company_name = 'BigTime'
            self.setup_completed = False

    def save_settings(self):
        """Save server settings to database"""
        from server.server import set_server_setting

        try:
            # Save each setting to database
            set_server_setting('host', str(self.host))
            set_server_setting('port', str(self.port))
            set_server_setting('autostart', str(self.autostart).lower())
            set_server_setting('company_name', str(self.company_name))
            set_server_setting('setup_completed', str(self.setup_completed).lower())

        except Exception as e:
            # If we can't save, show a warning but don't crash
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                None,
                "Settings Save Error",
                f"Could not save server settings: {e}\n\nSettings will be lost when application closes."
            )

    def start_server(self):
        """Start the server"""
        self.server_manager.start_server(self.host, self.port)

    def stop_server(self):
        """Stop the server"""
        self.server_manager.stop_server()

    def show_ootb_setup(self):
        """Show first-time server setup dialog"""
        from ui.dialogs.server import OOTBDialog

        dialog = OOTBDialog(
            company_name=self.company_name,
            host=self.host,
            port=self.port
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.get_values()
            self.company_name = values['company_name']
            self.host = values['host']
            self.port = values['port']
            self.autostart = values['autostart']
            self.setup_completed = True
            self.save_settings()

            # Auto-start server if configured
            if self.autostart:
                QTimer.singleShot(500, self.start_server)
        else:
            # User cancelled setup - show again next time
            self.setup_completed = False

    def show_config(self):
        """Show configuration dialog"""

        dialog = ConfigDialog(
            host=self.host,
            port=self.port,
            autostart=self.autostart
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.get_values()
            self.host = values['host']
            self.port = values['port']
            self.autostart = values['autostart']
            self.save_settings()

            # Restart server if it's running
            if self.server_manager.server_running:
                QMessageBox.information(None, "Server Configuration",
                                      "Settings saved. Please restart the server for changes to take effect.")

    def backup_database(self):
        """Backup the server database"""
        from shared.backup_utils import create_backup

        try:
            backup_path = create_backup('server_bigtime.db')
            QMessageBox.information(None, 'Backup', f'Database backed up as {backup_path}')
        except FileNotFoundError:
            QMessageBox.warning(None, 'Backup Failed', 'Server database not found.')
        except Exception as e:
            QMessageBox.warning(None, 'Backup Failed', f'Could not backup database: {e}')

    def restore_database(self):
        """Restore the server database from a backup file"""
        from shared.backup_utils import restore_from_backup
        from pathlib import Path

        # Show file picker dialog
        dlg = DatabaseSelectDialog(None, default_filename='server_bigtime.backup.db', restore=True)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        backup_path = dlg.get_file_path()
        if not backup_path or not Path(backup_path).exists():
            QMessageBox.warning(None, 'Restore Failed', 'Selected backup file does not exist.')
            return

        # Confirm with user
        reply = QMessageBox.question(
            None,
            'Restore Database',
            f'Restore database from {Path(backup_path).name}?\n\n'
            'Your current database will be backed up before restoring.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            restore_from_backup(Path(backup_path), 'server_bigtime.db')
            QMessageBox.information(
                None,
                'Restore Complete',
                'Database has been restored from backup.\n\nPlease restart the server for changes to take effect.'
            )
        except Exception as e:
            QMessageBox.critical(None, 'Restore Failed', f'Could not restore database: {e}')

    def migrate_database(self):
        """Migrate the server database to the current schema version"""
        from shared.backup_utils import create_backup_from_source
        from shared.db_helpers import perform_database_migration
        from pathlib import Path
        import shutil
        import tempfile
        import os

        # Show migration dialog
        dlg = DatabaseSelectDialog(None, default_filename='server_bigtime.db', migrate=True)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        db_path = dlg.get_file_path()
        if not db_path or not Path(db_path).exists():
            QMessageBox.warning(None, 'Migration Failed', 'Selected database file does not exist.')
            return

        try:
            # Create backup first (from original location)
            logger.info(f"Creating backup before migration of {db_path}")
            backup_path = create_backup_from_source(db_path)
            logger.info(f"Backup created: {backup_path}")

            # Check if the database is on a network mount (common issue on macOS)
            # If so, work with a temporary local copy
            working_db_path = db_path
            is_network_mount = os.path.ismount(str(Path(db_path).parent))

            if is_network_mount:
                logger.info(f"Database is on a network mount, creating temporary local copy for migration")
                # Create a temp copy in the system temp directory
                with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
                    temp_db_path = tmp.name

                try:
                    # Copy to temp location
                    shutil.copy2(db_path, temp_db_path)
                    working_db_path = temp_db_path
                    logger.info(f"Created temporary database copy at {temp_db_path}")
                except Exception as e:
                    logger.error(f"Failed to create temporary copy: {e}")
                    raise
            else:
                temp_db_path = None

            # Run migration on working copy
            logger.info(f"Starting migration of {working_db_path}")
            perform_database_migration(working_db_path)

            # If we used a temp copy, move it back to the original location
            if temp_db_path:
                logger.info(f"Copying migrated database back to {db_path}")
                shutil.copy2(working_db_path, db_path)
                # Clean up temp file
                try:
                    os.unlink(temp_db_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_db_path}: {e}")

            QMessageBox.information(
                None,
                'Migration Complete',
                f'Database has been successfully migrated.\n\n'
                f'Original DB Backup saved to: {backup_path.name}\n\n'
                'The database is now ready to use.\nNote: This does not import the migrated database. Please select \'Maintenance\' > \'Restore Database.\' to import the database.'
            )
            logger.info("Migration completed successfully")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            QMessageBox.critical(
                None,
                'Migration Failed',
                f'Could not migrate database: {e}\n\n'
                f'A backup was created if needed.'
            )


    def on_server_started(self):
        """Handle server started event"""
        self.status_action.setText(f"Status: Running v{shared.__VERSION__} on {self.host}:{self.port}")
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.tray_icon.setToolTip(f"BigTime Server v{shared.__VERSION__} - Running on {self.host}:{self.port}")

        # Show notification
        if QSystemTrayIcon.supportsMessages():
            self.tray_icon.showMessage(
                f"BigTime Server v{shared.__VERSION__}",
                f"Server started on {self.host}:{self.port}",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )

    def on_server_stopped(self):
        """Handle server stopped event"""
        self.status_action.setText(f"Status: v{shared.__VERSION__} Stopped")
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.tray_icon.setToolTip(f"BigTime Server v{shared.__VERSION__} - Stopped")

    def on_server_error(self, error):
        """Handle server error event"""
        self.status_action.setText(f"Status: v{shared.__VERSION__} Error")
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.tray_icon.setToolTip(f"BigTime Server v{shared.__VERSION__} - Error: {error}")

        QMessageBox.critical(None, "Server Error", f"Server error: {error}")

    def quit_application(self):
        """Quit the application"""
        if self.server_manager.server_running:
            reply = QMessageBox.question(
                None,
                "Quit BigTime Server",
                "Server is running. Are you sure you want to quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        self.server_manager.stop_server()
        self.app.quit()



def run_console_server():
    """Fallback console server when system tray is not available"""
    logger.info(f"BigTime Server v{shared.__VERSION__} - Console Mode")
    logger.info("System tray not available, running in console mode.")
    logger.info("Press Ctrl+C to stop the server.")

    try:
        from server.server import init_server_db, run_server

        # Initialize database
        init_server_db()

        # Default configuration
        host = '127.0.0.1'
        port = DEFAULT_SERVER_PORT

        logger.info(f"Starting server on {host}:{port}")
        logger.info(f"Server will be accessible at: http://{host}:{port}")
        logger.info("API endpoints available at: /api/v1/")

        # Run server (uses Waitress)
        run_server(host=host, port=port)

    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


def main():
    """Main entry point - tries system tray first, falls back to console"""
    # First check if we can use GUI mode
    try:
        app = QApplication(sys.argv)
    except Exception as e:
        logger.error(f"Could not initialize GUI: {e}")
        run_console_server()
        return

    # Check cross-platform system tray availability
    if not is_system_tray_available():
        current_platform = platform.system()

        # Show platform-specific message
        if current_platform == "Linux":
            logger.warning("System tray not available. This may be due to:")
            logger.warning("- No desktop environment running")
            logger.warning("- Desktop environment doesn't support system tray")
            logger.warning("- Running in headless mode")
        elif current_platform == "Darwin":
            logger.warning("System tray not available on current version of macOS.")
        else:
            logger.warning("System tray not available on this system.")

        logger.info("Falling back to console mode...")
        app.quit()
        run_console_server()
        return

    # System tray is available, run GUI mode
    logger.info(f"Starting BigTime Server v{shared.__VERSION__} on {platform.system()}")

    # Prevent quit on last window closed (we want to stay in tray)
    app.setQuitOnLastWindowClosed(False)

    # Create and show tray application
    tray_app = BigTimeServerTray(app)

    logger.info("Server running in system tray. Right-click tray icon for options.")

    # Run the application
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
