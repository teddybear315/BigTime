"""
BigTime Server - Cross-Platform System Tray Application
Runs the BigTime server as a hidden background service with system tray integration.
Supports Windows, Linux, and macOS with appropriate fallbacks.
"""

import os
import platform
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (QApplication, QDialog, QMenu, QMessageBox,
                             QSystemTrayIcon)

from shared.logging_config import get_server_logger

# Setup standardized logging
logger = get_server_logger()


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


class ServerManager(QObject):
    """Manages the Flask server in a separate thread"""

    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    server_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.server_running = False

    def start_server(self, host='127.0.0.1', port=5000):
        """Start the server in a separate thread using production WSGI server"""
        if self.server_running:
            return

        def run_server():
            try:
                from server.server import init_server_db
                from server.server import run_server as start_server

                # Initialize database and time service
                init_server_db()

                # Run server (uses Waitress)
                start_server(host=host, port=port)

            except Exception as e:
                self.server_error.emit(str(e))

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.server_running = True
        self.server_started.emit()

    def stop_server(self):
        """Stop the server (note: Flask doesn't have built-in graceful shutdown)"""
        self.server_running = False
        self.server_stopped.emit()





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

        # Load settings
        self.load_settings()

        # Check if first-time setup is needed
        if not self.setup_completed:
            QTimer.singleShot(500, self.show_ootb_setup)

        # Show tray icon
        self.tray_icon.show()

        # Auto-start server if configured (and setup is completed)
        if getattr(self, 'autostart', True) and self.setup_completed:
            QTimer.singleShot(1000, self.start_server)  # Delay to ensure tray is ready

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
            self.port = config.get('port', 5000)
            self.autostart = config.get('autostart', True)
            self.company_name = config.get('company_name', 'BigTime')
            self.setup_completed = config.get('setup_completed', False)

        except Exception as e:
            # If database is not available, use defaults
            logger.warning(f"Could not load server config from database: {e}")
            self.host = '127.0.0.1'
            self.port = 5000
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
        port = 5000

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
