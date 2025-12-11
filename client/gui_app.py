"""
BigTime Client GUI Application
This module contains the main GUI application logic, separated from the UI widgets.
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QDate, QObject, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QFont
from PyQt6.QtWidgets import (QApplication, QDateEdit, QDialog, QFileDialog,
                             QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                             QMainWindow, QMessageBox, QPushButton,
                             QSizePolicy, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from client.background_worker import NetworkWorker
from client.dialog_managers import (EmployeeListManager, ReportManager,
                                    TimeLogsManager)
from client.timeclock_client import get_client
import shared
from shared.logging_config import get_client_logger
from shared.models import Employee
from shared.utils import get_data_path, get_resource_path
from ui.dialogs import (AddEmployeeDialog, ClientSyncConfigDialog,
                        DateRangeDialog, EditEmployeeDialog, EditLogsDialog,
                        OOTBClientDialog, SettingsDialog, EditTimeSelectorDialog)
from ui.fonts import fonts


class BigTimeClientApp(QMainWindow):
    """Main BigTime client application window"""

    def __init__(self) -> None:
        """Initialize BigTime client application.

        Sets up minimal UI immediately, then schedules async initialization
        to prevent blocking and allow window to appear quickly.
        """
        super().__init__()

        # Setup standardized logging
        self.logger = get_client_logger()
        self.logger.info("Starting BigTime Client GUI...")

        # Initialize minimal state for UI
        self.client = None
        self.company_name = 'BigTime'
        self.manager_pin = ''
        self.report_save_path = ''
        self.manager_password = None
        self.manager_ootb = False
        self.is_moderator = False
        self.is_in_ootb_setup = False  # Flag to prevent auto-sync during OOTB

        # Setup minimal UI immediately (fast operations only)
        self.setup_minimal_ui()

        # Show the window immediately with loading state
        self.show_loading_state()

        # Schedule heavy initialization after UI is shown
        QTimer.singleShot(10, self.initialize_application_async)

    def setup_minimal_ui(self) -> None:
        """Setup minimal UI for quick initial display.

        Creates basic window layout with loading message before performing
        heavy initialization. Allows window to appear immediately.
        """
        from shared.utils import create_app_icon

        self.setWindowTitle('BigTime - Loading...')
        self.setWindowIcon(create_app_icon())
        self.setMinimumSize(400, 400)

        # Create central widget with loading message
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Loading label
        self.loading_label = QLabel('Loading BigTime...')
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet('font-size: 18px; color: #333; margin: 20px;')
        layout.addWidget(self.loading_label)

        # Progress indicator (simple animated text)
        self.progress_label = QLabel('Initializing...')
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet('font-size: 12px; color: #666; margin: 10px;')
        layout.addWidget(self.progress_label)

    def show_loading_state(self) -> None:
        """Display loading state UI immediately.

        Shows window with loading message and forces UI update to ensure
        window appears before heavy initialization begins.
        """
        self.show()
        QApplication.processEvents()  # Force UI update

    def update_loading_progress(self, message: str) -> None:
        """Update loading progress message.

        Args:
            message: Status message to display during initialization
        """
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(message)
            QApplication.processEvents()  # Force UI update

    def initialize_application_async(self) -> None:
        """Initialize application components asynchronously.

        Performs all initialization after minimal UI is shown:
        - Create and configure client instance
        - Setup full UI layout
        - Load persistent settings
        - Start background network worker
        - Handle manager PIN setup if needed

        This deferred initialization allows UI to appear immediately,
        then load data in background without blocking.
        """
        try:
            # Initialize client (no network operations)
            self.update_loading_progress('Initializing client...')
            self.client = get_client()

            # Load configuration and settings (no network operations)
            self.update_loading_progress('Loading settings...')
            self.load_settings()

            # Setup network worker and background services
            self.update_loading_progress('Starting network services...')
            self.setup_network_worker()

            # Setup full UI
            self.update_loading_progress('Setting up interface...')
            QTimer.singleShot(10, self.setup_full_ui_async)

        except Exception as e:
            if hasattr(self, 'progress_label'):
                self.progress_label.setText(f'Error: {str(e)}')

    def setup_network_worker(self) -> None:
        """Setup network worker in background thread"""
        try:
            # Create network worker
            # NetworkWorker is implemented as a QThread subclass; start it directly
            self.network_worker = NetworkWorker(client=self.client)

            # Connect signals from network worker to GUI
            self.network_worker.sync_status_changed.connect(self.on_sync_status_changed)
            self.network_worker.employee_synced.connect(self.on_employee_synced)
            self.network_worker.server_info_updated.connect(self.on_server_info_updated)
            self.network_worker.connection_status_changed.connect(self.on_connection_status_changed)
            self.network_worker.tick.connect(self.update_clock)
            self.network_worker.clear_status.connect(self.clear_status_message)

            # Start the worker thread
            self.network_worker.start()

            # Delay sync service start to allow OOTB setup to complete first
            # Only auto-start if not in OOTB setup (OOTB will manually start after config)
            def start_sync_if_ready():
                if not self.is_in_ootb_setup:
                    self.network_worker.start_sync_service.emit()

            QTimer.singleShot(500, start_sync_if_ready)

        except Exception as e:
            pass  # Network worker is optional

    def setup_full_ui_async(self):
        """Setup the full UI asynchronously"""
        try:
            # Replace minimal UI with full UI
            self.setup_ui()

            # Setup menu
            self.setup_menu()

            # Check settings and ensure manager PIN exists
            self.check_manager_settings()

            # Setup authentication state
            self.is_moderator = False
            self.update_menu_state()

            # Request network operations (non-blocking)
            if hasattr(self, 'network_worker'):
                self.network_worker.check_server_connection.emit()
                # Delay fetch_server_info to allow worker thread to fully initialize
                QTimer.singleShot(500, lambda: self.network_worker.fetch_server_info.emit())

        except Exception as e:
            if hasattr(self, 'progress_label'):
                self.progress_label.setText(f'UI Error: {str(e)}')



    def load_settings(self) -> None:
        """Load application settings from client.

        Loads configuration including company name, manager PIN, report save path,
        and other persistent settings from the local client database.
        Sets UI state based on loaded settings.
        """
        # Load core settings first (these should always work from local DB)
        try:
            self.manager_pin = self.client.get_setting('manager_pin', '')
            self.report_save_path = self.client.get_setting('report_save_path', str(get_data_path("reports")))
            self.manager_password = self.client.get_setting('manager_password', None)
            self.manager_ootb = (self.client.get_setting('manager_password_ootb', '0') == '1')
        except Exception as e:
            # Database issue - use safe defaults
            self.logger.error(f"Error loading core settings: {e}")
            self.manager_pin = ''
            self.report_save_path = str(get_data_path("reports"))
            self.manager_password = None  # This will trigger OOTB, which is correct if DB is broken
            self.manager_ootb = False

        # Set default company name from local settings (non-blocking)
        try:
            company_name = self.client.get_setting('company_name', 'BigTime')
            self.company_name = str(company_name).strip() if company_name else 'BigTime'
        except Exception:
            self.company_name = 'BigTime'

        # Request server info fetch in background (will update company_name when complete)
        if hasattr(self, 'network_worker') and self.network_worker:
            self.network_worker.fetch_server_info.emit()

        # Fallback validation
        if self.manager_pin is None:
            self.manager_pin = ''
        if self.report_save_path is None:
            self.report_save_path = str(get_data_path("reports"))
        # Note: manager_password and manager_ootb can legitimately be None/False

    def setup_ui(self):
        """Setup the main user interface"""
        from shared.utils import create_app_icon

        # Set window title: only prepend company name if it's not the default 'BigTime'
        if self.company_name and self.company_name != 'BigTime':
            self.setWindowTitle(f'{self.company_name} - BigTime')
        else:
            self.setWindowTitle('BigTime')
        self.setWindowIcon(create_app_icon())
        # self.setMinimumSize(420, 420)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 30, 20, 20)
        main_layout.setSpacing(12)

        # Clock group (stays at top)
        clock_group = QVBoxLayout()
        self.clock = QLabel(f'{self.company_name}')
        self.clock.setFont(fonts["monospace_large"])
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)

        clock_group.addWidget(self.clock)
        main_layout.addLayout(clock_group)

        # Initial update
        self.update_clock()

        # Middle row: employee group (left) and controls group (right)
        middle_row = QVBoxLayout()

        # Employee input section
        emp_widget = QWidget()
        emp_layout = QVBoxLayout(emp_widget)
        emp_layout.setContentsMargins(0, 0, 0, 0)
        emp_layout.setSpacing(6)

        employee_label = QLabel('Employee ID:')
        employee_label.setFont(fonts["large"])
        employee_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        emp_layout.addWidget(employee_label)

        self.employee_input = QLineEdit()
        self.employee_input.setFont(fonts["large"])
        self.employee_input.setMinimumHeight(50)
        self.employee_input.returnPressed.connect(self.smart_clock_action)
        emp_layout.addWidget(self.employee_input)

        middle_row.addWidget(emp_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # Controls group: buttons stacked and status underneath; keep compact width
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        btns_row = QHBoxLayout()

        self.clock_in_btn = QPushButton('Clock In')
        self.clock_in_btn.setMinimumHeight(60)
        self.clock_in_btn.setFont(fonts["large"])
        self.clock_in_btn.clicked.connect(self.clock_in)
        btns_row.addWidget(self.clock_in_btn)

        self.clock_out_btn = QPushButton('Clock Out')
        self.clock_out_btn.setMinimumHeight(60)
        self.clock_out_btn.setFont(fonts["large"])
        self.clock_out_btn.clicked.connect(self.clock_out)
        btns_row.addWidget(self.clock_out_btn)

        self.status_label = QLabel('Ready')
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(fonts["small_bold"])

        controls_layout.addLayout(btns_row)
        controls_layout.addWidget(self.status_label)
        middle_row.addWidget(controls_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(middle_row, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addStretch(1)

        # Footer: small Fetch button at left and compact Sync status anchored to bottom-right
        footer_layout = QHBoxLayout()
        # fetch_btn = QPushButton('Sync')
        # fetch_btn.setToolTip('Sync DB from BigTime server now')
        # # fonts imported as `fonts` at module level
        # fetch_btn.setFont(fonts['small'])
        # fetch_btn.setFixedSize(QSize(56, 18))
        # fetch_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # fetch_btn.clicked.connect(self.sync_now)
        # self.fetch_btn = fetch_btn
        # footer_layout.addWidget(fetch_btn, 0, Qt.AlignmentFlag.AlignLeft)

        # Sync status: show online/offline/syncing indicator and last sync time
        self.status_container = QWidget()
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)

        # Small label indicating sync state (emoji + text)
        self.sync_status_label = QLabel('')
        self.sync_status_label.setFont(fonts['small_bold'])
        status_layout.addWidget(self.sync_status_label, 0, Qt.AlignmentFlag.AlignLeft)

        # Spacer
        # status_layout.addSpacing(8)
        status_layout.addStretch()

        # Last sync time label
        self.last_sync_label = QLabel('')
        self.last_sync_label.setFont(fonts['small'])
        status_layout.addWidget(self.last_sync_label, 0, Qt.AlignmentFlag.AlignRight)

        footer_layout.addWidget(self.status_container, 0, Qt.AlignmentFlag.AlignBottom)
        main_layout.addLayout(footer_layout)

        # Focus on input
        self.employee_input.setFocus()
        # Initialize footer sync status display
        try:
            self.update_footer_sync_status()
        except Exception as e:
            # If sync service not available yet, log and continue
            self.logger.debug(f"Sync status not available during init: {e}")

    def update_clock(self):
        """Update the clock display in the title label"""
        if hasattr(self, 'clock') and self.clock:
            self.clock.setText(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def smart_clock_action(self):
        """Smart clock in/out based on employee's current status"""
        badge = self.employee_input.text().strip()
        if not badge:
            self.employee_input.setStyleSheet('background-color: #ffcccc')
            return

        self.employee_input.setStyleSheet('')

        # Check if employee exists
        employee = self.client.get_employee_by_badge(badge)
        if not employee or employee.deactivated:
            self.set_status_with_autoclear(
                f'❌ Employee with badge {badge} not found',
                'color: red; font-weight: bold;'
            )
            return

        # Check if employee has an open log (is currently clocked in)
        open_log = self.client.get_open_log(badge)

        if open_log:
            # Employee is clocked in, so clock them out
            self.clock_out()
        else:
            # Employee is not clocked in, so clock them in
            self.clock_in()

    def setup_menu(self):
        """Setup application menu"""
        menubar = self.menuBar()

        app_menu = menubar.addMenu('BigTime')
        settings_action = QAction('Settings...', self)
        settings_action.triggered.connect(self.edit_settings)
        app_menu.addAction(settings_action)

        # Exit action
        exit_action = QAction("Quit...", self)
        exit_action.triggered.connect(self.close)
        app_menu.addAction(exit_action)

        manager_menu = menubar.addMenu('Manager')
        # Moderator menu
        self.manager_login = QAction('Login...', self)
        self.manager_login.triggered.connect(self.validate_manager_access)
        manager_menu.addAction(self.manager_login)

        # Maintenance menu
        self.maintenance_menu = menubar.addMenu('Maintenance')

        view_emp_action = QAction('View Employees', self)
        view_emp_action.triggered.connect(self.view_employees)
        self.maintenance_menu.addAction(view_emp_action)

        add_emp_action = QAction('Add Employee...', self)
        add_emp_action.triggered.connect(self.add_employee)
        self.maintenance_menu.addAction(add_emp_action)

        self.maintenance_menu.addSeparator()

        view_logs_action = QAction('View Time Logs', self)
        view_logs_action.triggered.connect(self.view_time_logs)
        self.maintenance_menu.addAction(view_logs_action)

        edit_times_action = QAction('Edit Time Logs...', self)
        edit_times_action.triggered.connect(self.edit_times)
        self.maintenance_menu.addAction(edit_times_action)

        # Tools menu
        self.tools_menu = menubar.addMenu('Tools')

        server_config_action = QAction('Server Configuration...', self)
        server_config_action.triggered.connect(self.configure_server)
        self.tools_menu.addAction(server_config_action)

        sync_now_action = QAction('Sync Now', self)
        sync_now_action.triggered.connect(self.sync_now)
        self.tools_menu.addAction(sync_now_action)

        retry_failed_action = QAction('Retry Failed Syncs', self)
        retry_failed_action.triggered.connect(self.retry_failed_syncs)
        self.tools_menu.addAction(retry_failed_action)

        # Reporting menu
        self.reporting_menu = menubar.addMenu('Reporting')

        gen_report_action = QAction('Generate Report...', self)
        gen_report_action.triggered.connect(self.generate_report)
        self.reporting_menu.addAction(gen_report_action)

        backup_db_action = QAction('Backup Database', self)
        backup_db_action.triggered.connect(self.backup_database)
        self.reporting_menu.addAction(backup_db_action)

        restore_db_action = QAction('Restore from Backup', self)
        restore_db_action.triggered.connect(self.restore_database)
        self.reporting_menu.addAction(restore_db_action)

    def check_manager_settings(self):
        """Check settings using client; ensure manager_pin exists"""
        # OOTB should show if:
        # 1. No manager password is set (first run), OR
        # 2. The OOTB flag is explicitly set to '1' (forced setup)
        should_show_ootb = (
            (self.manager_password is None or self.manager_password == '') or
            self.manager_ootb
        )

        if should_show_ootb:
            self.logger.info(f"Showing OOTB setup - manager_password: {self.manager_password}, manager_ootb: {self.manager_ootb}")
            self.is_in_ootb_setup = True  # Prevent auto-sync during OOTB
            self.prompt_manager_OOTB()
        else:
            self.logger.debug(f"Skipping OOTB - manager_password exists: {self.manager_password is not None and self.manager_password != ''}")

    def prompt_manager_OOTB(self):
        """Show OOTB dialog for setting up the system"""
        current_path = self.client.get_setting('report_save_path', str(get_data_path("reports")))
        manager_pin = self.client.get_setting('manager_pin', '')

        while True:
            dlg = OOTBClientDialog(self, manager_pin=manager_pin, report_save_path=current_path)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                QMessageBox.critical(self, 'Setup Required',
                                   'Manager password setup is required to continue.')
                continue

            values = dlg.get_values()

            # Save settings using client
            self.client.set_setting('manager_pin', values['manager_pin'])
            self.client.set_setting('report_save_path', values['report_save_path'])
            self.client.set_setting('manager_password', values['manager_pin'])
            self.client.set_setting('manager_password_ootb', '0')
            # Initialize company_name setting if not already set
            if not self.client.get_setting('company_name'):
                self.client.set_setting('company_name', 'BigTime')

            self.logger.info("OOTB setup completed - saved manager_password_ootb=0")

            # Configure sync if enabled
            if values['enable_sync']:
                from shared.models import ServerConfig

                sync_config = ServerConfig(
                    server_url=values['server_url'],
                    device_id=values['device_id'],
                    api_key=values['api_key'],
                    sync_interval=values['sync_interval'],
                    timeout=10
                )

                # Update configuration via NetworkWorker (if available)
                if hasattr(self, 'network_worker') and self.network_worker:
                    self.network_worker.update_sync_config.emit(sync_config)
                    self.set_status_with_autoclear('✅ Sync configured successfully')
                else:
                    # Fallback: save directly to database (will be loaded on next start)
                    from shared import db_helpers
                    db_helpers.set_setting('server_url', sync_config.server_url)
                    db_helpers.set_setting('device_id', sync_config.device_id)
                    db_helpers.set_setting('api_key', sync_config.api_key)
                    db_helpers.set_setting('sync_interval', str(sync_config.sync_interval))
                    db_helpers.set_setting('timeout', str(sync_config.timeout))
                    self.set_status_with_autoclear('✅ Sync will start on next launch')
            else:
                self.set_status_with_autoclear('📴 Working offline mode')

            # Update instance variables
            self.manager_pin = values['manager_pin']
            self.report_save_path = values['report_save_path']
            self.manager_password = values['manager_pin']
            self.manager_ootb = False
            self.is_in_ootb_setup = False  # OOTB complete, allow sync to start

            # Start sync service now if it was configured during OOTB
            if values['enable_sync'] and hasattr(self, 'network_worker') and self.network_worker:
                self.logger.info("OOTB complete - starting sync service")
                QTimer.singleShot(100, lambda: self.network_worker.start_sync_service.emit())
                # Fetch server info to get company name and other config
                QTimer.singleShot(1000, lambda: self.network_worker.fetch_server_info.emit())

            break

    def validate_manager_access(self):
        """Handle moderator menu authentication"""
        if not self.is_moderator:
            from ui.dialogs import PinDialog
            pin_dialog = PinDialog(self, set_flag=False)
            pin_dialog.setWindowTitle("Manager Authentication")

            if pin_dialog.exec() == QDialog.DialogCode.Accepted:
                entered_pin = pin_dialog.get_pin()
                if entered_pin == self.manager_password:
                    self.is_moderator = True
                    self.update_menu_state()
                else:
                    QMessageBox.warning(self, 'Authentication Failed', 'Incorrect manager PIN.')
                    return
        else:
            reply = QMessageBox.question(
                None, 'Confirm Logout',
                f'Are you sure you want to logout?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.is_moderator = False
                self.update_menu_state()

    def update_menu_state(self):
        """Update menu state based on authentication"""
        if not self.is_moderator:
            for menu in [self.maintenance_menu, self.tools_menu]:
                menu.setEnabled(False)
        else:
            for menu in [self.maintenance_menu, self.tools_menu]:
                menu.setEnabled(True)

    def clock_in(self):
        """Handle clock in with PIN authentication"""
        badge = self.employee_input.text().strip()
        if not badge:
            self.employee_input.setStyleSheet('background-color: #ffcccc')
            QMessageBox.warning(self, 'Input Error', 'Please enter your badge number.')
            return
        else:
            self.employee_input.setStyleSheet('')

        # Check if employee exists
        employee = self.client.get_employee_by_badge(badge)
        if not employee or employee.deactivated:
            self.set_status_with_autoclear(
                f'❌ Employee with badge {badge} not found',
                'color: red; font-weight: bold;'
            )
            return

        # PIN Authentication
        if not employee.pin or employee.pin.strip() == '':
            # Employee has no PIN set - prompt to set one
            from ui.dialogs import PinDialog
            pin_dialog = PinDialog(self, set_flag=True)
            if pin_dialog.exec() == QDialog.DialogCode.Accepted:
                new_pin = pin_dialog.get_pin()
                # Update employee PIN only
                success = self.client.update_employee_fields(employee.badge, {'pin': new_pin})
                if not success:
                    self.set_status_with_autoclear(
                        '❌ Failed to save PIN',
                        'color: red; font-weight: bold;'
                    )
                    return
                # Trigger immediate sync for employee update
                if hasattr(self, 'network_worker') and self.network_worker:
                    self.network_worker.employee_data_changed.emit()
            else:
                # User cancelled PIN setup
                return
        else:
            # Employee has PIN - prompt to enter it
            from ui.dialogs import PinDialog
            pin_dialog = PinDialog(self, set_flag=False)
            if pin_dialog.exec() == QDialog.DialogCode.Accepted:
                entered_pin = pin_dialog.get_pin()
                if entered_pin != employee.pin:
                    self.set_status_with_autoclear(
                        '❌ Incorrect PIN',
                        'color: red; font-weight: bold;'
                    )
                    return
            else:
                # User cancelled PIN entry
                return

        # PIN authentication successful - proceed with clock in
        result = self.client.clock_in(badge)

        if result['success']:
            self.set_status_with_autoclear(f'✅ {result["message"]}')
            # Trigger immediate sync for new time log
            if hasattr(self, 'network_worker') and self.network_worker:
                self.network_worker.time_log_data_changed.emit()
        else:
            self.set_status_with_autoclear(
                f'❌ failed: {result["message"]}',
                'color: red; font-weight: bold;'
            )

        self.employee_input.clear()

    def clock_out(self):
        """Handle clock out with PIN authentication"""
        badge = self.employee_input.text().strip()
        if not badge:
            self.employee_input.setStyleSheet('background-color: #ff8888')
            QMessageBox.warning(self, 'Input Error', 'Please enter your badge number.')
            return
        else:
            self.employee_input.setStyleSheet('')

        # Check if employee exists
        employee = self.client.get_employee_by_badge(badge)
        if not employee or employee.deactivated:
            self.set_status_with_autoclear(
                f'❌ Employee with badge {badge} not found',
                'color: red; font-weight: bold;'
            )
            return

        # PIN Authentication (same as clock_in)
        if not employee.pin or employee.pin.strip() == '':
            # Employee has no PIN set - prompt to set one
            from ui.dialogs import PinDialog
            pin_dialog = PinDialog(self, set_flag=True)
            if pin_dialog.exec() == QDialog.DialogCode.Accepted:
                new_pin = pin_dialog.get_pin()
                # Update employee PIN only
                success = self.client.update_employee_fields(employee.badge, {'pin': new_pin})
                if not success:
                    self.set_status_with_autoclear(
                        '❌ Failed to save PIN',
                        'color: red; font-weight: bold;'
                    )
                    return
                # Trigger immediate sync for employee update
                if hasattr(self, 'network_worker') and self.network_worker:
                    self.network_worker.employee_data_changed.emit()
            else:
                # User cancelled PIN setup
                return
        else:
            # Employee has PIN - prompt to enter it
            from ui.dialogs import PinDialog
            pin_dialog = PinDialog(self, set_flag=False)
            if pin_dialog.exec() == QDialog.DialogCode.Accepted:
                entered_pin = pin_dialog.get_pin()
                if entered_pin != employee.pin:
                    self.set_status_with_autoclear(
                        '❌ Incorrect PIN',
                        'color: red; font-weight: bold;'
                    )
                    return
            else:
                # User cancelled PIN entry
                return

        # PIN authentication successful - proceed with clock out
        result = self.client.clock_out(badge)

        if result['success']:
            self.set_status_with_autoclear(f'✅ {result["message"]}')
            # Trigger immediate sync for updated time log
            if hasattr(self, 'network_worker') and self.network_worker:
                self.network_worker.time_log_data_changed.emit()
        else:
            self.set_status_with_autoclear(
                f'❌ Clock out failed: {result["message"]}',
                'color: red; font-weight: bold;'
            )

        self.employee_input.clear()

    def sync_now(self):
        """Trigger immediate sync"""
        if hasattr(self, 'network_worker'):
            self.status_label.setText('🔄 Sync triggered...')
            self.network_worker.trigger_manual_sync.emit()
            self.set_status_with_autoclear('✅ Sync requested...')
        else:
            QMessageBox.information(self, 'Sync Disabled', 'Network worker not available.')

    def retry_failed_syncs(self):
        """Retry failed sync operations"""
        if hasattr(self, 'network_worker'):
            self.status_label.setText('🔄 Retrying failed syncs...')
            self.network_worker.trigger_manual_sync.emit()
            self.set_status_with_autoclear('✅ Retry requested...')
        else:
            QMessageBox.information(self, 'Sync Disabled', 'Network worker not available.')

    def add_employee(self):
        """Show add employee dialog"""
        dlg = AddEmployeeDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            employee = dlg.get_employee()
            try:
                emp_id = self.client.create_employee(employee)
                QMessageBox.information(self, 'Success', f'Employee {employee.name} added successfully.')

                # Trigger immediate sync for new employee
                if hasattr(self, 'network_worker'):
                    self.network_worker.employee_data_changed.emit()

            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to add employee: {str(e)}')

    def view_employees(self):
        """Show employee list"""
        # Callback to trigger sync when employee data changes
        def on_employee_data_changed():
            if hasattr(self, 'network_worker') and self.network_worker:
                self.network_worker.employee_data_changed.emit()

        EmployeeListManager.show_employee_list(self, self.client, on_employee_data_changed)

    def view_time_logs(self):
        """Show time logs"""
        TimeLogsManager.show_time_logs(self, self.client)

    def edit_times(self):
        """Show time editing interface"""
        dlg = EditTimeSelectorDialog(self.client, self)
        dlg.exec()

    def edit_settings(self):
        """Show settings dialog"""
        current_path = self.client.get_setting('report_save_path', str(get_data_path("reports")))
        manager_pin = self.client.get_setting('manager_pin', '')

        dlg = SettingsDialog(self, manager_pin=manager_pin, report_save_path=current_path)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            values = dlg.get_values()

            # Save settings using client
            self.client.set_setting('manager_pin', values['manager_pin'])
            self.client.set_setting('report_save_path', values['report_save_path'])

            # Update local values
            self.manager_pin = values['manager_pin']
            self.report_save_path = values['report_save_path']

    def configure_server(self):
        """Show server configuration dialog"""
        from shared.models import ServerConfig

        # Load current config from sync service or database
        current_config = ServerConfig()
        if hasattr(self, 'network_worker') and self.network_worker.sync_service:
            current_config = self.network_worker.sync_service.config
        else:
            # Fallback: load from DB directly
            from shared import db_helpers
            current_config = ServerConfig(
                server_url=db_helpers.get_setting('server_url', ''),
                device_id=db_helpers.get_setting('device_id', ''),
                api_key=db_helpers.get_setting('api_key', ''),
                sync_interval=int(db_helpers.get_setting('sync_interval', '30')),
                timeout=int(db_helpers.get_setting('timeout', '10'))
            )

        dlg = ClientSyncConfigDialog(
            self,
            server_url=current_config.server_url,
            device_id=current_config.device_id,
            api_key=current_config.api_key,
            sync_interval=current_config.sync_interval
        )

        if dlg.exec() == QDialog.DialogCode.Accepted:
            values = dlg.get_values()

            # Create new config
            new_config = ServerConfig(
                server_url=values['server_url'],
                device_id=values['device_id'],
                api_key=values['api_key'],
                sync_interval=values['sync_interval'],
                timeout=current_config.timeout  # Keep current timeout
            )

            # Update configuration via NetworkWorker
            if hasattr(self, 'network_worker'):
                self.network_worker.update_sync_config.emit(new_config)
                self.set_status_with_autoclear('✅ Server configuration updated')
                # Test connection in background
                self.network_worker.check_server_connection.emit()
                # Fetch server info to get updated company name
                QTimer.singleShot(500, lambda: self.network_worker.fetch_server_info.emit())
            else:
                self.set_status_with_autoclear('📴 Server synchronization disabled')

    def on_sync_status_changed(self, status_dict):
        """Handle sync status updates"""
        try:
            # Update the clock display to refresh sync indicator (only if UI is fully loaded)
            if hasattr(self, 'clock'):
                self.update_clock()
            # Update footer sync status
            try:
                if hasattr(self, 'update_footer_sync_status'):
                    self.update_footer_sync_status(status_dict)
            except Exception as e:
                self.logger.debug(f"Failed to update footer sync status: {e}")

        except Exception as e:
            self.logger.error(f"Error handling sync status update: {e}")

    def on_employee_synced(self, sync_data):
        """Handle employee sync updates"""
        try:
            # Handle different types of employee sync data
            if isinstance(sync_data, dict):
                if 'count' in sync_data:
                    # Bulk employee sync from server
                    count = sync_data.get('count', 0)
                    self.logger.info(f"Employee sync: {count} employees synced from server")
                elif 'name' in sync_data:
                    # Individual employee sync
                    employee_name = sync_data.get('name', 'Unknown')
                    self.logger.info(f"Employee synced: {employee_name}")
                else:
                    self.logger.debug(f"Employee sync: {sync_data}")
            else:
                self.logger.debug(f"Employee sync update: {sync_data}")
        except Exception as e:
            self.logger.error(f"Error handling employee sync update: {e}")

    def on_server_info_updated(self, server_info):
        """Handle server info updates from network worker"""
        try:
            if 'company_name' in server_info:
                self.company_name = str(server_info['company_name']).strip()
                # Save company name to local database for persistence
                self.client.set_setting('company_name', self.company_name)
                # Update title: only prepend company name if it's not the default 'BigTime'
                if self.company_name and self.company_name != 'BigTime':
                    self.setWindowTitle(f'{self.company_name} - BigTime')
                else:
                    self.setWindowTitle('BigTime')
        except Exception as e:
            pass  # Non-critical

    def on_connection_status_changed(self, is_connected):
        """Handle connection status changes from network worker"""
        # Currently no UI updates needed for connection status changes
        pass

    def clear_status_message(self):
        """Clear status message - called from network worker"""
        try:
            if hasattr(self, 'status_label'):
                self.status_label.setText('Ready')
                self.status_label.setStyleSheet('')
        except Exception:
            pass

    def update_footer_sync_status(self, status_dict: dict = None):
        """Update footer labels with sync status and last sync time

        status_dict is expected to be the dict emitted by sync_status_changed
        If not provided, query the client for current status.
        """
        try:
            if status_dict is None:
                # Default status when no sync data available
                status_dict = {
                    'is_online': False,
                    'is_syncing': False,
                    'last_sync': None,
                    'pending_count': 0
                }

            # Determine status emoji/text
            if status_dict.get('is_syncing'):
                state_text = '🔄 Syncing'
            elif status_dict.get('is_online'):
                pending = status_dict.get('pending_count', 0)
                if pending and int(pending) > 0:
                    state_text = f'📤 Out: {pending}'
                else:
                    state_text = '✅ Online'
            else:
                state_text = '📴 Offline'

            # Only update labels if they exist (full UI loaded)
            if hasattr(self, 'sync_status_label') and self.sync_status_label:
                self.sync_status_label.setText(state_text)

            last_sync = status_dict.get('last_sync')
            if hasattr(self, 'last_sync_label') and self.last_sync_label:
                if last_sync:
                    # last_sync may be a string or datetime
                    if isinstance(last_sync, str):
                        last_text = last_sync
                    else:
                        last_text = last_sync.strftime('%H:%M:%S')
                    self.last_sync_label.setText(f'Last sync: {last_text}')
                else:
                    self.last_sync_label.setText('Last sync: N/A')
                self.last_sync_label.setStyleSheet('color: #666;')

        except Exception as e:
            self.logger.error(f"Error updating footer sync status: {e}")



    def set_status_with_autoclear(self, message, style='', delay_seconds=5):
        """Set status message with automatic clear after delay"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(style)

        # Schedule automatic clear via background worker
        if hasattr(self, 'network_worker') and self.network_worker:
            self.network_worker.schedule_status_clear(delay_seconds)

    def generate_report(self):
        """Generate and display employee paystub report"""
        ReportManager.generate_report(self, self.client)

    def _show_pdf_preview(self, pdf_path: str, receipt_size: tuple):
        """Show PDF preview dialog with print and open options"""
        try:
            from PyQt6.QtPdf import QPdfDocument
            from PyQt6.QtPdfWidgets import QPdfView

            class PdfDialog(QDialog):
                def __init__(self, pdf_path, pdf_height, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle('Paystub Preview')
                    h = max(400, min(pdf_height, 800))
                    self.resize(350, h)

                    layout = QVBoxLayout(self)

                    # PDF viewer
                    self.pdf_view = QPdfView(self)
                    self.pdf_doc = QPdfDocument(self)
                    self.pdf_doc.load(pdf_path)
                    self.pdf_view.setDocument(self.pdf_doc)
                    layout.addWidget(self.pdf_view)

                    # Button row
                    btn_row = QHBoxLayout()
                    print_btn = QPushButton('Print')
                    open_btn = QPushButton('Open File')
                    close_btn = QPushButton('Close')

                    btn_row.addWidget(print_btn)
                    btn_row.addWidget(open_btn)
                    btn_row.addStretch()
                    btn_row.addWidget(close_btn)
                    layout.addLayout(btn_row)

                    # Event handlers
                    def _do_print():
                        try:
                            from PyQt6.QtGui import QPainter
                            from PyQt6.QtPrintSupport import (QPrintDialog,
                                                              QPrinter)

                            printer = QPrinter()
                            dlg = QPrintDialog(printer, self)
                            if dlg.exec() == QDialog.DialogCode.Accepted:
                                painter = QPainter()
                                if not painter.begin(printer):
                                    raise RuntimeError('Could not begin QPainter on printer')
                                try:
                                    self.pdf_view.render(painter)
                                finally:
                                    painter.end()
                        except Exception as e:
                            QMessageBox.warning(self, 'Print Error', f'Could not print file: {e}')

                    def _open_file():
                        try:
                            import os
                            import subprocess

                            if sys.platform.startswith('win'):
                                subprocess.run(['explorer', '/select,', pdf_path])
                            elif sys.platform == 'darwin':
                                subprocess.run(['open', '-R', pdf_path])
                            else:
                                subprocess.run(['xdg-open', os.path.dirname(pdf_path)])
                        except Exception as e:
                            QMessageBox.warning(self, 'Open Error', f'Could not reveal file: {e}')

                    print_btn.clicked.connect(_do_print)
                    open_btn.clicked.connect(_open_file)
                    close_btn.clicked.connect(self.accept)

            dlg = PdfDialog(pdf_path, round(receipt_size[1] * 1.5), self)
            dlg.exec()

        except Exception as e:
            # Fallback to system default PDF viewer
            import os
            import traceback
            import webbrowser

            self.logger.error(f"PDF viewer error: {e}")
            self.logger.debug(f"PDF viewer stack trace: {traceback.format_exc()}")

            try:
                webbrowser.open_new(pdf_path)
            except Exception as e2:
                self.logger.error(f"Browser error: {e2}")
                try:
                    import subprocess
                    if sys.platform.startswith('win'):
                        os.startfile(pdf_path)
                    else:
                        subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', pdf_path])
                except Exception as e3:
                    self.logger.error(f"Startfile error: {e3}")
                    QMessageBox.warning(
                        self, 'Open PDF',
                        f'Could not open PDF automatically. Please open manually: {pdf_path}\nError: {e}'
                    )

    def backup_database(self):
        """Backup the local database"""
        from shared.backup_utils import create_backup

        try:
            backup_path = create_backup('bigtime.db')
            QMessageBox.information(self, 'Backup', f'Database backed up as {backup_path}')
        except Exception as e:
            QMessageBox.warning(self, 'Backup Failed', f'Could not backup database: {e}')

    def restore_database(self):
        """Restore the local database from the most recent backup"""
        from shared.backup_utils import get_latest_backup_info, restore_from_backup

        # Get the latest backup
        backup_info = get_latest_backup_info('bigtime.db')

        if not backup_info:
            QMessageBox.warning(self, 'Restore Failed', 'No backups available.')
            return

        backup_path, formatted_time = backup_info

        # Confirm with user
        reply = QMessageBox.question(
            self,
            'Restore Database',
            f'Restore database from backup created on {formatted_time}?\n\n'
            'Your current database will be backed up before restoring.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            restore_from_backup(backup_path, 'bigtime.db')
            QMessageBox.information(
                self,
                'Restore Complete',
                'Database has been restored from backup.\n\nPlease restart the application for changes to take effect.'
            )
        except Exception as e:
            QMessageBox.critical(self, 'Restore Failed', f'Could not restore database: {e}')

    def closeEvent(self, event):
        """Handle application close"""
        # Stop network worker and sync service
        try:
            if hasattr(self, 'network_worker'):
                self.network_worker.stop_sync_service.emit()
                self.network_worker.stop()
                # Wait for the thread to finish cleanly
                try:
                    self.network_worker.wait(2000)
                except Exception:
                    pass
        except Exception:
            pass

        super().closeEvent(event)


def main():
    """Main entry point for the BigTime client application"""
    app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName("BigTime Client")
    app.setApplicationVersion(shared.__VERSION__)
    app.setOrganizationName("SCR LLC")

    # Create and show main window
    window = BigTimeClientApp()
    window.show()

    # Run the application
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
