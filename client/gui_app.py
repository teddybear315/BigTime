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
from shared.logging_config import get_client_logger
from shared.models import Employee
from shared.utils import get_data_path, get_resource_path
from ui.dialogs import (AddEmployeeDialog, ClientSyncConfigDialog,
                        DateRangeDialog, EditEmployeeDialog, EditLogsDialog,
                        OOTBClientDialog, SettingsDialog)
from ui.fonts import fonts


class BigTimeClientApp(QMainWindow):
    """Main BigTime client application window"""

    def __init__(self):
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

    def setup_minimal_ui(self):
        """Setup minimal UI that shows immediately"""
        from shared.utils import create_app_icon

        self.setWindowTitle('BigTime - Loading...')
        self.setWindowIcon(create_app_icon())
        self.setMinimumSize(420, 420)

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

    def show_loading_state(self):
        """Show loading state immediately"""
        self.show()
        QApplication.processEvents()  # Force UI update

    def update_loading_progress(self, message):
        """Update loading progress message"""
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(message)
            QApplication.processEvents()  # Force UI update

    def initialize_application_async(self):
        """Initialize application components asynchronously"""
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

    def setup_network_worker(self):
        """Setup network worker in background thread"""
        try:
            # Create network worker
            self.network_worker = NetworkWorker(client=self.client)
            self.network_thread = QThread()
            self.network_worker.moveToThread(self.network_thread)

            # Connect signals from network worker to GUI
            self.network_worker.sync_status_changed.connect(self.on_sync_status_changed)
            self.network_worker.employee_synced.connect(self.on_employee_synced)
            self.network_worker.server_info_updated.connect(self.on_server_info_updated)
            self.network_worker.connection_status_changed.connect(self.on_connection_status_changed)
            self.network_worker.tick.connect(self.update_clock)
            self.network_worker.clear_status.connect(self.clear_status_message)

            # Connect thread lifecycle
            self.network_thread.started.connect(self.network_worker.run)
            self.network_thread.finished.connect(self.network_worker.deleteLater)

            # Start the network thread
            self.network_thread.start()

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
                self.network_worker.fetch_server_info.emit()

        except Exception as e:
            if hasattr(self, 'progress_label'):
                self.progress_label.setText(f'UI Error: {str(e)}')



    def load_settings(self):
        """Load application settings from client"""
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
            self.company_name = self.client.get_setting('company_name', 'BigTime')
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

        self.setWindowTitle(f'{self.company_name} - BigTime')
        self.setWindowIcon(create_app_icon())
        self.setMinimumSize(420, 420)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Clock group (stays at top)
        clock_group = QHBoxLayout()
        self.clock = QLabel(f'{self.company_name}')
        self.clock.setFont(fonts["monospace_large"])
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # clock_group.addStretch()
        clock_group.addWidget(self.clock)
        # clock_group.addStretch()
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

        self.status_label = QLabel('')
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(fonts["small_bold"])

        controls_layout.addLayout(btns_row)
        controls_layout.addWidget(self.status_label)
        middle_row.addWidget(controls_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(middle_row, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addStretch(1)

        # Footer: small Fetch button at left and compact Sync status anchored to bottom-right
        footer_layout = QHBoxLayout()
        fetch_btn = QPushButton('Sync')
        fetch_btn.setToolTip('Sync DB from BigTime server now')
        # fonts imported as `fonts` at module level
        fetch_btn.setFont(fonts['small'])
        fetch_btn.setFixedSize(QSize(56, 18))
        fetch_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        fetch_btn.clicked.connect(self.sync_now)
        self.fetch_btn = fetch_btn
        footer_layout.addWidget(fetch_btn, 0, Qt.AlignmentFlag.AlignLeft)
        footer_layout.addStretch()

        # Sync status: show online/offline/syncing indicator and last sync time
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)

        # Small label indicating sync state (emoji + text)
        self.sync_status_label = QLabel('')
        self.sync_status_label.setFont(fonts['small_bold'])
        status_layout.addWidget(self.sync_status_label)

        # Spacer
        status_layout.addSpacing(8)

        # Last sync time label
        self.last_sync_label = QLabel('')
        self.last_sync_label.setFont(fonts['small'])
        status_layout.addWidget(self.last_sync_label)

        self.status_container = status_container
        status_container.setVisible(True)
        footer_layout.addWidget(status_container, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        main_layout.addLayout(footer_layout)

        # Focus on input
        self.employee_input.setFocus()
        # Initialize footer sync status display
        try:
            self.update_footer_sync_status()
        except Exception:
            # If sync service not available yet, ignore
            pass

    def update_clock(self):
        """Update the clock display in the title label"""
        if hasattr(self, 'clock') and self.clock:
            self.clock.setText(f'{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')

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

        # Exit action
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        menubar.addAction(exit_action)

        # Moderator menu
        self.manager_login = QAction('Manager', self)
        self.manager_login.triggered.connect(self.validate_manager_access)
        menubar.addAction(self.manager_login)

        # Maintenance menu
        self.maintenance_menu = menubar.addMenu('Maintenance')

        add_emp_action = QAction('Add Employee', self)
        add_emp_action.triggered.connect(self.add_employee)
        self.maintenance_menu.addAction(add_emp_action)

        view_emp_action = QAction('View Employees', self)
        view_emp_action.triggered.connect(self.view_employees)
        self.maintenance_menu.addAction(view_emp_action)

        # Tools menu
        self.tools_menu = menubar.addMenu('Tools')

        view_logs_action = QAction('View Time Logs', self)
        view_logs_action.triggered.connect(self.view_time_logs)
        self.tools_menu.addAction(view_logs_action)

        edit_times_action = QAction('Edit Time Logs', self)
        edit_times_action.triggered.connect(self.edit_times)
        self.tools_menu.addAction(edit_times_action)

        self.tools_menu.addSeparator()

        settings_action = QAction('Settings', self)
        settings_action.triggered.connect(self.edit_settings)
        self.tools_menu.addAction(settings_action)

        server_config_action = QAction('Server Configuration', self)
        server_config_action.triggered.connect(self.configure_server)
        self.tools_menu.addAction(server_config_action)

        self.tools_menu.addSeparator()

        sync_now_action = QAction('Sync Now', self)
        sync_now_action.triggered.connect(self.sync_now)
        self.tools_menu.addAction(sync_now_action)

        retry_failed_action = QAction('Retry Failed Syncs', self)
        retry_failed_action.triggered.connect(self.retry_failed_syncs)
        self.tools_menu.addAction(retry_failed_action)

        # Reporting menu
        self.reporting_menu = menubar.addMenu('Reporting')

        gen_report_action = QAction('Generate Report', self)
        gen_report_action.triggered.connect(self.generate_report)
        self.reporting_menu.addAction(gen_report_action)

        backup_db_action = QAction('Backup Database', self)
        backup_db_action.triggered.connect(self.backup_database)
        self.reporting_menu.addAction(backup_db_action)

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

            break

    def validate_manager_access(self):
        """Handle moderator menu authentication"""
        if not self.is_moderator:
            from ui.dialogs import PinDialog
            pin_dialog = PinDialog(self, is_setting_pin=False)
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
                None, 'Confirm Removal',
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
            pin_dialog = PinDialog(self, is_setting_pin=True)
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
            pin_dialog = PinDialog(self, is_setting_pin=False)
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
            employee_name = result.get('employee_name', 'Employee')
            self.set_status_with_autoclear(f'✅ {employee_name} clocked in successfully')
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
            pin_dialog = PinDialog(self, is_setting_pin=True)
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
            pin_dialog = PinDialog(self, is_setting_pin=False)
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
            employee_name = result.get('employee_name', 'Employee')
            self.set_status_with_autoclear(
                f'✅ {employee_name} clocked out successfully.'
            )
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
        dlg = QDialog(self)
        dlg.setWindowTitle('Edit Time Logs')
        dlg.setFixedWidth(400)
        dlg.resize(400, 600)
        layout = QVBoxLayout(dlg)

        # Employee selection section
        title = QLabel('Time Log Editor')
        title.setFont(fonts["header"])
        sub_title = QLabel('Select an employee and press load logs.')
        sub_title.setFont(fonts["small"])
        sub_title.setStyleSheet('color: #666;')
        sub_title.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(sub_title)

        emp_label = QLabel('Select Employee:')
        layout.addWidget(emp_label)

        emp_table = QTableWidget()
        emp_table.setColumnCount(2)
        emp_table.setHorizontalHeaderLabels(['ID', 'Name'])
        emp_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        emp_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        emp_table.setColumnWidth(0, 40)
        emp_table.setColumnWidth(1, 320)
        layout.addWidget(emp_table)

        # Controls row (date selector and load button)
        controls_row = QHBoxLayout()
        date_label = QLabel('Date:')
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())
        load_btn = QPushButton('Load Logs')

        controls_row.addWidget(date_label)
        controls_row.addWidget(date_edit)
        controls_row.addWidget(load_btn)
        controls_row.addStretch()
        layout.addLayout(controls_row)

        # Logs table section
        logs_table = QTableWidget()
        logs_table.setColumnCount(4)
        logs_table.setHorizontalHeaderLabels(['ID', 'Clock In', 'Clock Out', ''])
        logs_table.setColumnWidth(0, 40)
        logs_table.setColumnWidth(1, 120)
        logs_table.setColumnWidth(2, 120)
        logs_table.setColumnWidth(3, 80)
        layout.addWidget(logs_table)

        # Bottom buttons
        btn_row = QHBoxLayout()
        close_btn = QPushButton('Close')
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        def load_employees():
            """Load employees into the employee table"""
            try:
                employees = self.client.get_all_employees()
                emp_table.setRowCount(len(employees))

                for r, emp in enumerate(employees):
                    badge = emp.badge
                    name = emp.name

                    badge_item = QTableWidgetItem(badge)
                    badge_item.setFlags(badge_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    # Store the employee object for later use
                    badge_item.setData(Qt.ItemDataRole.UserRole, emp)

                    name_item = QTableWidgetItem(name)
                    name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                    emp_table.setItem(r, 0, badge_item)
                    emp_table.setItem(r, 1, name_item)

            except Exception as e:
                QMessageBox.critical(dlg, 'Error', f'Failed to load employees: {str(e)}')

        def load_logs_for_selected():
            """Load logs for the selected employee and date"""
            selected = emp_table.selectedItems()
            if not selected:
                QMessageBox.warning(dlg, 'Select Employee', 'Please select an employee from the list.')
                return

            try:
                # Get the employee from the stored data
                badge_item = emp_table.item(selected[0].row(), 0)
                employee = badge_item.data(Qt.ItemDataRole.UserRole)
                badge_text = employee.badge

                # Get the selected date
                qdate = date_edit.date()
                selected_date = date(qdate.year(), qdate.month(), qdate.day())

                # Fetch logs for this employee and date
                logs = self.client.get_logs_for_range(badge_text, selected_date, selected_date)

                logs_table.setRowCount(len(logs))

                for r, log in enumerate(logs):
                    # ID column
                    id_item = QTableWidgetItem(str(log.id))
                    id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    logs_table.setItem(r, 0, id_item)

                    # Clock In column
                    clock_in_text = log.clock_in if log.clock_in else ''
                    ci_item = QTableWidgetItem(clock_in_text)
                    ci_item.setFlags(ci_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    logs_table.setItem(r, 1, ci_item)

                    # Clock Out column
                    clock_out_text = log.clock_out if log.clock_out else ''
                    co_item = QTableWidgetItem(clock_out_text)
                    co_item.setFlags(co_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    logs_table.setItem(r, 2, co_item)

                    # Edit button
                    edit_btn = QPushButton('Edit')
                    edit_btn.clicked.connect(lambda checked, log_obj=log: edit_single_log(log_obj))
                    logs_table.setCellWidget(r, 3, edit_btn)

            except Exception as e:
                QMessageBox.critical(dlg, 'Error', f'Failed to load logs: {str(e)}')

        def edit_single_log(log):
            """Edit a single time log entry"""
            try:
                # Convert log to format expected by EditLogsDialog
                log_data = [(log.id, log.clock_in, log.clock_out)]

                # Use local timezone for time display
                edit_dlg = EditLogsDialog(log_data, dlg, server_timezone='UTC')

                # Connect to the log_removed signal to handle log deletion
                def handle_log_removal(removed_log_id):
                    try:
                        # Delete the log from the database
                        success = self.client.delete_time_log(removed_log_id)
                        if success:
                            # Refresh the logs table to show the removal
                            load_logs_for_selected()
                        else:
                            QMessageBox.warning(dlg, 'Warning', 'Failed to remove log entry.')
                    except Exception as e:
                        QMessageBox.critical(dlg, 'Error', f'Failed to remove log: {str(e)}')

                edit_dlg.log_removed.connect(handle_log_removal)

                if edit_dlg.exec() == QDialog.DialogCode.Accepted:
                    # Process the updates
                    updates = edit_dlg.get_updates()
                    if updates:
                        log_id, new_clock_in, new_clock_out = updates[0]
                        self.client.update_time_log(log_id, new_clock_in, new_clock_out)
                        # Refresh the logs table
                        load_logs_for_selected()

            except Exception as e:
                QMessageBox.critical(dlg, 'Error', f'Failed to edit log: {str(e)}')

        # Connect signals
        load_btn.clicked.connect(load_logs_for_selected)
        close_btn.clicked.connect(dlg.accept)

        # Load initial data
        load_employees()

        # Show dialog
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
            except Exception:
                pass

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
                self.company_name = server_info['company_name']
                if hasattr(self, 'clock'):
                    self.setWindowTitle(f'{self.company_name} - BigTime')
        except Exception as e:
            pass  # Non-critical

    def on_connection_status_changed(self, is_connected):
        """Handle connection status changes from network worker"""
        try:
            # Update UI to reflect connection status if needed
            pass
        except Exception as e:
            pass  # Non-critical

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
        import shutil

        from shared.db_helpers import get_db_path

        db_path = get_db_path()
        backup_dir = get_data_path("backups")
        backup_dir.mkdir(exist_ok=True, parents=True)

        now = datetime.now()
        backup_name = now.strftime('%m-%d-%Y %H-%M-%S') + '.db'
        backup_path = backup_dir / backup_name

        try:
            shutil.copy2(db_path, backup_path)
            QMessageBox.information(self, 'Backup', f'Database backed up as {backup_path}')
        except Exception as e:
            QMessageBox.warning(self, 'Backup Failed', f'Could not backup database: {e}')

    def closeEvent(self, event):
        """Handle application close"""
        # Stop network worker and sync service
        try:
            if hasattr(self, 'network_worker'):
                self.network_worker.stop_sync_service.emit()
                self.network_worker.stop()
            if hasattr(self, 'network_thread') and self.network_thread.isRunning():
                self.network_thread.quit()
                self.network_thread.wait(2000)  # Wait up to 2 seconds for clean shutdown
        except Exception:
            pass

        super().closeEvent(event)


def main():
    """Main entry point for the BigTime client application"""
    app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName("BigTime Client")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("SCR LLC")

    # Create and show main window
    window = BigTimeClientApp()
    window.show()

    # Run the application
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
