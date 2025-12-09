"""
BigTime Server - Cross-Platform System Tray Application
Runs the BigTime server as a hidden background service with system tray integration.
Supports Windows, Linux, and macOS with appropriate fallbacks.
"""

import os
import platform
import sys
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QThread, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (QApplication, QDialog, QMenu, QMessageBox,
                             QSystemTrayIcon)

from shared.logging_config import get_server_logger

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
            except Exception as e:
                logger.warning(f"Shutdown request failed: {e}")
        except ImportError:
            # requests not available; continue to fallback
            logger.debug("requests module unavailable; falling back to thread stop.")
        except Exception as e:
            # Shutdown request failed; continue to fallback
            logger.debug(f"Graceful shutdown failed: {e}")

        # Wait briefly for the server thread to exit
        try:
            self.wait(3000)
        except Exception as e:
            logger.debug(f"Thread wait error: {e}")

        # Ensure running flag cleared and emit stopped for UI update
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

    def __init__(self):
        super().__init__()

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

        # Server control actions
        self.start_action = QAction("Start Server", self)
        self.start_action.triggered.connect(self.start_server)

        self.stop_action = QAction("Stop Server", self)
        self.stop_action.triggered.connect(self.stop_server)
        self.stop_action.setEnabled(False)

        # Configuration action
        self.config_action = QAction("Configure...", self)
        self.config_action.triggered.connect(self.show_config)

        # Backup action
        self.backup_action = QAction("Backup Database", self)
        self.backup_action.triggered.connect(self.backup_database)

        # Restore action
        self.restore_action = QAction("Restore from Backup", self)
        self.restore_action.triggered.connect(self.restore_database)

        # Status action (non-clickable info)
        self.status_action = QAction("Status: Stopped", self)
        self.status_action.setEnabled(False)

        # Separator and quit
        self.quit_action = QAction("Exit", self)
        self.quit_action.triggered.connect(self.quit_application)

        # Add actions to menu
        menu.addAction(self.status_action)
        menu.addSeparator()
        menu.addAction(self.start_action)
        menu.addAction(self.stop_action)
        menu.addSeparator()
        menu.addAction(self.config_action)
        menu.addAction(self.backup_action)
        menu.addAction(self.restore_action)
        menu.addSeparator()
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
        from ui.dialogs import OOTBServerDialog

        dialog = OOTBServerDialog(
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
        from ui.dialogs import ServerConfigDialog

        dialog = ServerConfigDialog(
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
        """Restore the server database from the most recent backup"""
        from shared.backup_utils import get_latest_backup_info, restore_from_backup

        # Get the latest backup
        backup_info = get_latest_backup_info('server_bigtime.db')

        if not backup_info:
            QMessageBox.warning(None, 'Restore Failed', 'No backups available.')
            return

        backup_path, formatted_time = backup_info

        # Confirm with user
        reply = QMessageBox.question(
            None,
            'Restore Database',
            f'Restore database from backup created on {formatted_time}?\n\n'
            'Your current database will be backed up before restoring.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            restore_from_backup(backup_path, 'server_bigtime.db')
            QMessageBox.information(
                None,
                'Restore Complete',
                'Database has been restored from backup.\n\nPlease restart the server for changes to take effect.'
            )
        except Exception as e:
            QMessageBox.critical(None, 'Restore Failed', f'Could not restore database: {e}')

    def on_server_started(self):
        """Handle server started event"""
        self.status_action.setText(f"Status: Running on {self.host}:{self.port}")
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.tray_icon.setToolTip(f"BigTime Server - Running on {self.host}:{self.port}")

        # Show notification
        if QSystemTrayIcon.supportsMessages():
            self.tray_icon.showMessage(
                "BigTime Server",
                f"Server started on {self.host}:{self.port}",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )

    def on_server_stopped(self):
        """Handle server stopped event"""
        self.status_action.setText("Status: Stopped")
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.tray_icon.setToolTip("BigTime Server - Stopped")

    def on_server_error(self, error):
        """Handle server error event"""
        self.status_action.setText("Status: Error")
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.tray_icon.setToolTip(f"BigTime Server - Error: {error}")

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
        QCoreApplication.quit()


def run_console_server():
    """Fallback console server when system tray is not available"""
    logger.info("BigTime Server - Console Mode")
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
            logger.warning("System tray not available on macOS.")
        else:
            logger.warning("System tray not available on this system.")

        logger.info("Falling back to console mode...")
        app.quit()
        run_console_server()
        return

    # System tray is available, run GUI mode
    logger.info(f"Starting BigTime Server on {platform.system()}")

    # Prevent quit on last window closed (we want to stay in tray)
    app.setQuitOnLastWindowClosed(False)

    # Create and show tray application
    tray_app = BigTimeServerTray()

    logger.info("Server running in system tray. Right-click tray icon for options.")

    # Run the application
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
