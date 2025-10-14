from datetime import date
from typing import Any, Dict

from PyQt6.QtCore import QDate, QDateTime, Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDateTimeEdit,
                             QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QLabel, QLineEdit, QPushButton,
                             QSpinBox, QTableWidget, QTableWidgetItem,
                             QTextEdit, QVBoxLayout)

from shared.models import Employee
from shared.utils import create_app_icon
from ui.fonts import fonts


def set_dialog_icon(dialog):
    """Set the application icon on a dialog"""
    dialog.setWindowIcon(create_app_icon())


class EditLogsDialog(QDialog):
    log_removed = pyqtSignal(int)  # log_id
    def __init__(self, logs, parent=None, server_timezone='UTC'):
        super().__init__(parent)
        self.setWindowTitle('Time Log Editor')
        self.server_timezone = server_timezone
        # enforce a minimum width so the inline editor has room
        self.setMinimumSize(500,150)

        layout = QVBoxLayout(self)
        self.edits = []
        self.remove_buttons = {}

        from shared.utils import (format_datetime_local, parse_datetime,
                                  utc_to_local_datetime)

        # Header
        info_label = QLabel('Modify clock-in and clock-out times for selected logs. Times are displayed in your local timezone.')
        info_label.setWordWrap(True)
        info_label.setStyleSheet('color: #666;')
        layout.addWidget(info_label)

        for log_id, clock_in, clock_out in logs:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(f'Log ID: {log_id}'))

            # Clock In editor
            in_edit = QDateTimeEdit()
            in_edit.setCalendarPopup(True)
            in_edit.setDisplayFormat('MM-dd-yyyy HH:mm:ss')
            try:
                if clock_in:
                    # Parse UTC datetime from storage and convert to local for display
                    utc_dt = parse_datetime(clock_in)
                    if utc_dt:
                        local_dt = utc_to_local_datetime(utc_dt, self.server_timezone)
                        qt_dt = QDateTime.fromString(local_dt.strftime('%m-%d-%Y %H:%M:%S'), 'MM-dd-yyyy HH:mm:ss')
                        if qt_dt.isValid():
                            in_edit.setDateTime(qt_dt)
                        else:
                            in_edit.setDateTime(QDateTime.currentDateTime())
                    else:
                        in_edit.setDateTime(QDateTime.currentDateTime())
                else:
                    in_edit.setDateTime(QDateTime.currentDateTime())
            except Exception:
                in_edit.setDateTime(QDateTime.currentDateTime())

            # Clock Out editor
            out_edit = QDateTimeEdit()
            out_edit.setCalendarPopup(True)
            out_edit.setDisplayFormat('MM-dd-yyyy HH:mm:ss')

            # Checkbox to indicate if entry should remain clocked in (no clock out)
            still_clocked_in = QCheckBox("Still clocked in")

            # Track the original state and setup the controls
            originally_clocked_in = not clock_out

            try:
                if clock_out:
                    # Parse UTC datetime from storage and convert to local for display
                    utc_dt = parse_datetime(clock_out)
                    if utc_dt:
                        local_dt = utc_to_local_datetime(utc_dt, self.server_timezone)
                        qt_dt = QDateTime.fromString(local_dt.strftime('%m-%d-%Y %H:%M:%S'), 'MM-dd-yyyy HH:mm:ss')
                        if qt_dt.isValid():
                            out_edit.setDateTime(qt_dt)
                            still_clocked_in.setChecked(False)
                            out_edit.setEnabled(True)
                        else:
                            out_edit.setDateTime(QDateTime.currentDateTime())
                            still_clocked_in.setChecked(True)
                            out_edit.setEnabled(False)
                    else:
                        out_edit.setDateTime(QDateTime.currentDateTime())
                        still_clocked_in.setChecked(True)
                        out_edit.setEnabled(False)
                else:
                    out_edit.setDateTime(QDateTime.currentDateTime())
                    still_clocked_in.setChecked(True)
                    out_edit.setEnabled(False)
            except Exception:
                out_edit.setDateTime(QDateTime.currentDateTime())
                still_clocked_in.setChecked(originally_clocked_in)
                out_edit.setEnabled(not originally_clocked_in)

            # Connect checkbox to enable/disable clock out editor
            def toggle_clock_out(checked):
                out_edit.setEnabled(not checked)
                if checked:
                    # When "still clocked in" is checked, reset to current time but keep disabled
                    out_edit.setDateTime(QDateTime.currentDateTime())

            still_clocked_in.toggled.connect(toggle_clock_out)

            row_layout.addWidget(QLabel('In:'))
            row_layout.addWidget(in_edit)
            row_layout.addWidget(QLabel('Out:'))
            row_layout.addWidget(out_edit)
            row_layout.addWidget(still_clocked_in)

            # Remove button
            remove_btn = QPushButton('Remove')
            remove_btn.clicked.connect(lambda _, lid=log_id: self.remove_log(lid))
            row_layout.addWidget(remove_btn)
            self.remove_buttons[log_id] = remove_btn

            layout.addLayout(row_layout)
            self.edits.append((log_id, in_edit, out_edit, still_clocked_in))

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_updates(self):
        """Get the updated log data with proper timezone conversion"""
        from shared.utils import format_datetime, parse_datetime_to_utc

        updates = []
        for log_id, in_edit, out_edit, still_clocked_in in self.edits:
            try:
                # Get local time from UI and convert to UTC for storage
                local_in_str = in_edit.dateTime().toString('MM-dd-yyyy HH:mm:ss')
                utc_in_dt = parse_datetime_to_utc(local_in_str, self.server_timezone)
                in_str = format_datetime(utc_in_dt) if utc_in_dt else ''
            except Exception:
                in_str = ''

            try:
                # Check if employee should remain clocked in (no clock out time)
                if still_clocked_in.isChecked():
                    out_str = ''  # Empty string represents no clock out time
                else:
                    # Get local time from UI and convert to UTC for storage
                    local_out_str = out_edit.dateTime().toString('MM-dd-yyyy HH:mm:ss')
                    utc_out_dt = parse_datetime_to_utc(local_out_str, self.server_timezone)
                    out_str = format_datetime(utc_out_dt) if utc_out_dt else ''
            except Exception:
                out_str = ''

            updates.append((log_id, in_str, out_str))
        return updates

    def remove_log(self, log_id):
        """Remove a log entry and emit signal for database deletion"""
        self.log_removed.emit(log_id)
        # Disable the controls for the removed log to provide visual feedback
        for idx, (lid, in_edit, out_edit, still_clocked_in) in enumerate(self.edits):
            if lid == log_id:
                try:
                    in_edit.setDisabled(True)
                except Exception:
                    pass
                try:
                    still_clocked_in.setDisabled(True)
                except Exception:
                    pass
                self.remove_buttons[log_id].setDisabled(True)
                break



class AddEmployeeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add Employee')
        self.setModal(True)
        self.setMinimumSize(400, 300)
        # self.resize(400, 300)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)  # Reduce spacing between groups

        # Personal Information Group
        personal_group = QGroupBox("Personal Information")
        personal_layout = QFormLayout(personal_group)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Enter employee full name")
        personal_layout.addRow('Name:', self.name)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("#'s only (5551234567)")
        personal_layout.addRow('Phone Number:', self.phone)

        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        personal_layout.addRow('Date of Birth:', self.dob)

        self.ssn = QLineEdit()
        self.ssn.setPlaceholderText("#'s only (XXXXXXXXX)")
        personal_layout.addRow('SSN:', self.ssn)

        layout.addWidget(personal_group)

        # Work Information Group
        work_group = QGroupBox("Work Information")
        work_layout = QFormLayout(work_group)

        self.badge = QLineEdit()
        self.badge.setPlaceholderText("Employee badge/ID number")
        work_layout.addRow('Badge:', self.badge)

        self.department = QLineEdit()
        self.department.setPlaceholderText("Department or division")
        work_layout.addRow('Department:', self.department)

        self.hire_date = QDateEdit()
        self.hire_date.setCalendarPopup(True)
        work_layout.addRow('Hire Date:', self.hire_date)

        layout.addWidget(work_group)

        # Pay Information Group
        pay_group = QGroupBox("Pay Information")
        pay_layout = QFormLayout(pay_group)

        self.period = QComboBox()
        self.period.addItems(['hourly', 'monthly'])
        pay_layout.addRow('Period:', self.period)

        self.rate = QDoubleSpinBox()
        self.rate.setMaximum(1000000)
        self.rate.setPrefix("$")
        pay_layout.addRow('Rate:', self.rate)

        layout.addWidget(pay_group)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def set_data(self, data):
        """Set form data from Employee object or dictionary"""
        if not data:
            return

        try:
            # Handle Employee object (preferred)
            if isinstance(data, Employee):
                self.name.setText(data.name or '')
                self.phone.setText(str(data.phone_number or ''))
                self.badge.setText(data.badge or '')
                self.department.setText(data.department or '')
                self.ssn.setText(str(data.ssn or ''))

                # Handle dates
                if data.date_of_birth:
                    qdate = QDate(data.date_of_birth.year, data.date_of_birth.month, data.date_of_birth.day)
                    self.dob.setDate(qdate)
                else:
                    self.dob.setDate(QDate.fromString('01-01-2000', 'MM-dd-yyyy'))

                if data.hire_date:
                    qdate = QDate(data.hire_date.year, data.hire_date.month, data.hire_date.day)
                    self.hire_date.setDate(qdate)
                else:
                    self.hire_date.setDate(QDate.fromString('01-01-2000', 'MM-dd-yyyy'))

                # Handle period dropdown
                idx = self.period.findText(data.period or 'hourly')
                if idx >= 0:
                    self.period.setCurrentIndex(idx)

                self.rate.setValue(float(data.rate or 0))

            # Handle dictionary (legacy compatibility)
            elif isinstance(data, dict):
                self.name.setText(data.get('name', ''))
                self.phone.setText(str(data.get('phone_number', '')))
                self.badge.setText(str(data.get('badge', '')))
                self.department.setText(data.get('department', ''))
                self.ssn.setText(str(data.get('ssn', '')))

                # Handle date fields from string format
                dob_str = data.get('date_of_birth', '01-01-2000')
                self.dob.setDate(QDate.fromString(dob_str or '01-01-2000', 'MM-dd-yyyy'))

                hire_str = data.get('hire_date', '01-01-2000')
                self.hire_date.setDate(QDate.fromString(hire_str or '01-01-2000', 'MM-dd-yyyy'))

                # Handle period dropdown
                period = data.get('period', 'hourly')
                idx = self.period.findText(period or 'hourly')
                if idx >= 0:
                    self.period.setCurrentIndex(idx)

                self.rate.setValue(float(data.get('rate', 0) or 0))

        except Exception as e:
            print(f"Warning: Error setting employee data: {e}")
            # Set safe defaults on error
            self.dob.setDate(QDate.fromString('01-01-2000', 'MM-dd-yyyy'))
            self.hire_date.setDate(QDate.fromString('01-01-2000', 'MM-dd-yyyy'))
            self.period.setCurrentIndex(0)
            self.rate.setValue(0.0)

    def get_data(self):
        """Get form data as dictionary (for legacy compatibility)"""
        return {
            'name': self.name.text().strip(),
            'phone_number': self.phone.text().strip(),
            'badge': self.badge.text().strip(),
            'department': self.department.text().strip(),
            'date_of_birth': self.dob.date().toString('MM-dd-yyyy'),
            'hire_date': self.hire_date.date().toString('MM-dd-yyyy'),
            'ssn': self.ssn.text().strip(),
            'period': self.period.currentText(),
            'rate': float(self.rate.value()),
            # Set defaults for fields not in the dialog
            'pin': '',         # No PIN by default
            'deactivated': 0,  # Active by default
        }

    def get_employee(self) -> Employee:
        """Get form data as Employee object (preferred for internal app use)"""
        # Helper function to parse dates
        def parse_form_date(date_str: str) -> date:
            """Parse MM-dd-yyyy format from QDateEdit"""
            try:
                qdate = QDate.fromString(date_str, 'MM-dd-yyyy')
                return date(qdate.year(), qdate.month(), qdate.day())
            except:
                return date.today()

        # Convert phone and SSN to integers, handling empty strings
        def safe_int(value: str) -> int:
            try:
                return int(value.strip()) if value.strip() else None
            except:
                return None

        return Employee(
            name=self.name.text().strip(),
            badge=self.badge.text().strip(),
            phone_number=safe_int(self.phone.text()),
            pin='',             # No PIN by default
            department=self.department.text().strip(),
            date_of_birth=parse_form_date(self.dob.date().toString('MM-dd-yyyy')),
            hire_date=parse_form_date(self.hire_date.date().toString('MM-dd-yyyy')),
            deactivated=False,  # Active by default for new employees
            ssn=safe_int(self.ssn.text()),
            period=self.period.currentText(),
            rate=float(self.rate.value())
        )


class EditEmployeeDialog(AddEmployeeDialog):
    """Employee editing dialog - extends AddEmployeeDialog with additional functionality"""

    def __init__(self, employee: Employee, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Edit Employee')

        # Store original employee for comparison
        self.original_employee = employee

        # Populate form with existing employee data
        self.set_data(employee)

        # Add additional sections for editing (PIN and status)
        self._add_security_section()
        self._add_status_section()

    def _add_security_section(self):
        """Add security settings section for editing existing employees"""
        # Security Settings Group (for existing employees)
        security_group = QGroupBox("Security Settings")
        security_layout = QFormLayout(security_group)
        security_layout.setVerticalSpacing(8)

        self.pin = QLineEdit()
        self.pin.setMaxLength(4)
        self.pin.setPlaceholderText("Leave empty to keep current PIN")
        self.pin.setEchoMode(QLineEdit.EchoMode.Password)
        # Populate with existing PIN (will be masked)
        if self.original_employee.pin:
            self.pin.setText(self.original_employee.pin)
        security_layout.addRow('PIN:', self.pin)

        # Insert before buttons
        layout = self.layout()
        layout.insertWidget(layout.count() - 1, security_group)

    def _add_status_section(self):
        """Add status section for editing existing employees"""
        # Status Group (for existing employees)
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)

        self.deactivated = QCheckBox('Deactivated')
        # Populate with existing status
        self.deactivated.setChecked(bool(self.original_employee.deactivated))
        status_layout.addWidget(self.deactivated)

        # Insert before buttons
        layout = self.layout()
        layout.insertWidget(layout.count() - 1, status_group)

    def get_employee(self) -> Employee:
        """Get updated employee object with changes applied"""
        # Start with base employee data from parent
        updated_employee = super().get_employee()

        # Add ID from original employee
        updated_employee.id = self.original_employee.id

        # Update security and status fields
        # If PIN field is empty, preserve the original PIN
        pin_text = self.pin.text().strip()
        updated_employee.pin = pin_text if pin_text else self.original_employee.pin
        updated_employee.deactivated = self.deactivated.isChecked()

        return updated_employee

    def get_changes(self) -> Dict[str, Any]:
        """Get only the fields that have changed as a dictionary for database updates"""
        updated = self.get_employee()
        changes = {}
        # Compare with original and only include changed fields
        if updated.name != self.original_employee.name:
            changes['name'] = updated.name
        if updated.badge != self.original_employee.badge:
            changes['badge'] = updated.badge
        if updated.phone_number != self.original_employee.phone_number:
            changes['phone_number'] = updated.phone_number
        if updated.department != self.original_employee.department:
            changes['department'] = updated.department
        if updated.date_of_birth != self.original_employee.date_of_birth:
            if updated.date_of_birth:
                changes['date_of_birth'] = updated.date_of_birth.isoformat() if isinstance(updated.date_of_birth, date) else updated.date_of_birth
            else:
                changes['date_of_birth'] = None
        if updated.hire_date != self.original_employee.hire_date:
            if updated.hire_date:
                changes['hire_date'] = updated.hire_date.isoformat() if isinstance(updated.hire_date, date) else updated.hire_date
            else:
                changes['hire_date'] = None
        if updated.ssn != self.original_employee.ssn:
            changes['ssn'] = updated.ssn
        if updated.period != self.original_employee.period:
            changes['period'] = updated.period
        if updated.rate != self.original_employee.rate:
            changes['rate'] = updated.rate
        # Only include PIN if it actually changed (not empty field preserving original)
        pin_text = self.pin.text().strip()
        if pin_text and pin_text != self.original_employee.pin:
            changes['pin'] = pin_text
        if updated.deactivated != self.original_employee.deactivated:
            changes['deactivated'] = updated.deactivated

        return changes

    def accept(self):
        """Validate PIN before accepting"""
        pin = self.pin.text().strip()

        # Validate PIN format - allow empty (keeps current PIN), but if provided must be 4 digits
        if pin and (len(pin) != 4 or not pin.isdigit()):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid PIN", "Employee PIN must be exactly 4 digits. Leave empty to keep current PIN.")
            return

        super().accept()


class SettingsDialog(QDialog):
    def __init__(self, parent=None, manager_pin='', report_save_path=''):
        super().__init__(parent)
        self.setWindowTitle('Settings')
        set_dialog_icon(self)
        # self.setMinimumSize(450, 300)

        layout = QVBoxLayout(self)

        # Header
        title = QLabel('Settings')
        title.setFont(fonts["header"])

        layout.addWidget(title)

        # Info message about server-managed settings
        info_label = QLabel('Note: Company name and time settings are managed by the server.')
        info_label.setWordWrap(True)
        info_label.setFont(fonts["small"])
        info_label.setStyleSheet('color: #666; font-style: italic;')
        layout.addWidget(info_label)

        # Security Settings Group
        security_group = QGroupBox("Security Settings")
        security_layout = QFormLayout(security_group)

        self.pin_edit = QLineEdit(manager_pin)
        self.pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_edit.setMaxLength(4)
        self.pin_edit.setPlaceholderText("Enter 4-digit manager PIN")
        security_layout.addRow('Manager PIN:', self.pin_edit)

        layout.addWidget(security_group)

        # File Settings Group
        file_group = QGroupBox("File Settings")
        file_layout = QFormLayout(file_group)

        path_container = QHBoxLayout()
        self.path_edit = QLineEdit(report_save_path)
        self.path_edit.setPlaceholderText("Select directory for saving reports")
        self.browse_btn = QPushButton('Browse...')
        self.browse_btn.clicked.connect(self.browse)

        path_container.addWidget(self.path_edit)
        path_container.addWidget(self.browse_btn)

        file_layout.addRow('Report Save Path:', path_container)

        layout.addWidget(file_group)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def browse(self):
        dir_path = QFileDialog.getExistingDirectory(self, 'Select Directory', self.path_edit.text())
        if dir_path:
            self.path_edit.setText(dir_path)

    def accept(self):
        """Validate manager PIN before accepting"""
        pin = self.pin_edit.text().strip()

        # Validate PIN format - allow empty for no change, but if provided must be 4 digits
        if pin and (len(pin) != 4 or not pin.isdigit()):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid PIN", "Manager PIN must be exactly 4 digits.")
            return

        super().accept()

    def get_values(self):
        return {
            'manager_pin': self.pin_edit.text().strip(),
            'report_save_path': self.path_edit.text().strip()
        }


class OOTBClientDialog(QDialog):
    def __init__(self, parent=None, manager_pin='', report_save_path=''):
        super().__init__(parent)
        self.setWindowTitle('BigTime Setup')
        set_dialog_icon(self)
        # self.setMinimumSize(450, 350)

        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel('BigTime Setup')
        header_label.setFont(fonts["header"])
        layout.addWidget(header_label)

        info_label = QLabel('Set up manager credentials and preferences for your BigTime installation:')
        info_label.setWordWrap(True)
        info_label.setFont(fonts["default"])
        layout.addWidget(info_label)

        layout.addSpacing(10)

        # Security Settings Group
        security_group = QGroupBox("Manager Credentials")
        security_layout = QFormLayout(security_group)

        self.pin_edit = QLineEdit(manager_pin)
        self.pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_edit.setMaxLength(4)
        self.pin_edit.setPlaceholderText("Enter 4-digit PIN")
        security_layout.addRow('Manager PIN:', self.pin_edit)

        self.pin_confirm_edit = QLineEdit()
        self.pin_confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_confirm_edit.setMaxLength(4)
        self.pin_confirm_edit.setPlaceholderText("Confirm PIN")
        security_layout.addRow('Confirm PIN:', self.pin_confirm_edit)

        layout.addWidget(security_group)

        # File Settings Group
        file_group = QGroupBox("File Settings")
        file_layout = QFormLayout(file_group)

        path_container = QHBoxLayout()
        self.path_edit = QLineEdit(report_save_path)
        self.path_edit.setPlaceholderText("Select directory for saving reports")
        self.browse_btn = QPushButton('Browse...')
        self.browse_btn.clicked.connect(self.browse)

        path_container.addWidget(self.path_edit)
        path_container.addWidget(self.browse_btn)

        file_layout.addRow('Report Save Path:', path_container)

        layout.addWidget(file_group)

        # Server Sync Settings Group
        sync_group = QGroupBox("Server Synchronization (Optional)")
        sync_layout = QFormLayout(sync_group)

        # Enable sync checkbox
        self.enable_sync_checkbox = QCheckBox("Enable server synchronization")
        self.enable_sync_checkbox.stateChanged.connect(self.toggle_sync_fields)
        sync_layout.addRow('', self.enable_sync_checkbox)

        # Server URL
        self.server_url_edit = QLineEdit('http://127.0.0.1:5000')
        self.server_url_edit.setPlaceholderText("http://server-address:port")
        sync_layout.addRow('Server URL:', self.server_url_edit)

        # Device ID (auto-generated, but editable)
        self.device_id_edit = QLineEdit()
        self.device_id_edit.setPlaceholderText("Auto-generated device identifier")
        sync_layout.addRow('Device ID:', self.device_id_edit)

        # API Key
        self.api_key_edit = QLineEdit('default-api-key')
        self.api_key_edit.setPlaceholderText("API key from server")
        sync_layout.addRow('API Key:', self.api_key_edit)

        # Sync interval
        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setMinimum(5)
        self.sync_interval_spin.setMaximum(300)
        self.sync_interval_spin.setValue(30)
        self.sync_interval_spin.setSuffix(' seconds')
        sync_layout.addRow('Sync Interval:', self.sync_interval_spin)

        # Info text
        info_text = QLabel("Configure sync settings to automatically backup time logs to a BigTime server. "
                          "Leave unchecked to work offline only.")
        info_text.setWordWrap(True)
        info_text.setFont(fonts["small"])
        sync_layout.addRow('', info_text)

        layout.addWidget(sync_group)

        # Generate default device ID
        self.generate_device_id()

        # Initially disable sync fields
        self.toggle_sync_fields()

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def generate_device_id(self):
        """Generate a default device ID"""
        import platform
        import uuid
        hostname = platform.node() or 'unknown'
        device_id = f"bigtime-{hostname}-{uuid.uuid4().hex[:8]}"
        self.device_id_edit.setText(device_id)

    def toggle_sync_fields(self):
        """Enable/disable sync fields based on checkbox state"""
        enabled = self.enable_sync_checkbox.isChecked()
        self.server_url_edit.setEnabled(enabled)
        self.device_id_edit.setEnabled(enabled)
        self.api_key_edit.setEnabled(enabled)
        self.sync_interval_spin.setEnabled(enabled)

    def browse(self):
        dir_path = QFileDialog.getExistingDirectory(self, 'Select Directory', self.path_edit.text())
        if dir_path:
            self.path_edit.setText(dir_path)

    def accept(self):
        """Validate manager PIN before accepting"""
        pin = self.pin_edit.text().strip()
        confirm_pin = self.pin_confirm_edit.text().strip()

        # Validate PIN format
        if not pin or len(pin) != 4 or not pin.isdigit():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid PIN", "Manager PIN must be exactly 4 digits.")
            return

        # Validate PIN confirmation
        if pin != confirm_pin:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "PIN Mismatch", "Manager PIN and confirmation do not match.")
            return

        super().accept()

    def get_values(self):
        return {
            'manager_pin': self.pin_edit.text().strip(),
            'manager_pin_confirm': self.pin_confirm_edit.text().strip(),
            'report_save_path': self.path_edit.text().strip(),
            'enable_sync': self.enable_sync_checkbox.isChecked(),
            'server_url': self.server_url_edit.text().strip() if self.enable_sync_checkbox.isChecked() else '',
            'device_id': self.device_id_edit.text().strip() if self.enable_sync_checkbox.isChecked() else '',
            'api_key': self.api_key_edit.text().strip() if self.enable_sync_checkbox.isChecked() else '',
            'sync_interval': self.sync_interval_spin.value() if self.enable_sync_checkbox.isChecked() else 30
        }


class OOTBServerDialog(QDialog):
    def __init__(self, parent=None, company_name='BigTime', host='127.0.0.1', port=5000):
        super().__init__(parent)
        self.setWindowTitle('BigTime Server Setup')
        set_dialog_icon(self)
        # self.setMinimumSize(400, 400)

        layout = QVBoxLayout(self)

        # Header info
        header_label = QLabel('BigTime Server Setup')
        header_label.setFont(fonts["header"])
        layout.addWidget(header_label)

        info_label = QLabel('Configure essential server settings for your BigTime installation:')
        info_label.setWordWrap(True)
        info_label.setFont(fonts["default"])
        layout.addWidget(info_label)

        # Company settings group
        company_group = QGroupBox("Company Information")
        company_layout = QFormLayout(company_group)

        self.company_edit = QLineEdit(company_name)
        self.company_edit.setPlaceholderText("Enter your company or organization name")
        company_layout.addRow("Company Name:", self.company_edit)

        layout.addWidget(company_group)

        # Server settings group
        server_group = QGroupBox("Server Network Settings")
        server_layout = QFormLayout(server_group)

        self.host_edit = QLineEdit(host)
        self.host_edit.setPlaceholderText("127.0.0.1 for local, 0.0.0.0 for all interfaces")
        server_layout.addRow("Host Address:", self.host_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setMinimum(1024)
        self.port_spin.setMaximum(65535)
        self.port_spin.setValue(port)
        server_layout.addRow("Port:", self.port_spin)

        layout.addWidget(server_group)

        # Auto-start option
        autostart_group = QGroupBox("Startup Options")
        autostart_layout = QVBoxLayout(autostart_group)

        self.autostart_check = QCheckBox("Start server automatically when tray application launches")
        self.autostart_check.setChecked(True)
        autostart_layout.addWidget(self.autostart_check)

        layout.addWidget(autostart_group)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_values(self):
        return {
            'company_name': self.company_edit.text().strip(),
            'host': self.host_edit.text().strip(),
            'port': self.port_spin.value(),
            'autostart': self.autostart_check.isChecked()
        }


class DateRangeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Date Range')
        # self.setMinimumSize(350, 250)

        layout = QVBoxLayout(self)


        info_label = QLabel('Choose the date range for your report:')
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Date Selection Group
        date_group = QGroupBox("Date Range")
        date_layout = QFormLayout(date_group)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setDisplayFormat('MM-dd-yyyy')
        date_layout.addRow('Start Date:', self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat('MM-dd-yyyy')
        date_layout.addRow('End Date:', self.end_date)

        layout.addWidget(date_group)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_dates(self):
        return self.start_date.date().toString('MM-dd-yyyy'), self.end_date.date().toString('MM-dd-yyyy')


class ServerConfigDialog(QDialog):
    """Enhanced server configuration dialog with validation, timezone selection, and time sync"""

    def __init__(self, parent=None, host='127.0.0.1', port=5000, autostart=True):
        super().__init__(parent)
        self.setWindowTitle("BigTime Server Configuration")
        self.setModal(True)
        self.setMinimumSize(400, 400)

        layout = QVBoxLayout(self)

        # Server settings group
        server_group = QGroupBox("Server Settings")
        server_layout = QFormLayout(server_group)

        # Host input with validation
        self.host_input = QLineEdit(host)
        self.host_input.setPlaceholderText("0.0.0.0 for all interfaces, 127.0.0.1 for local only")
        self.host_input.textChanged.connect(self.validate_inputs)
        server_layout.addRow("Host Address:", self.host_input)

        # Port input with spinner
        self.port_input = QSpinBox()
        self.port_input.setMinimum(1024)
        self.port_input.setMaximum(65535)
        self.port_input.setValue(port)
        self.port_input.valueChanged.connect(self.validate_inputs)
        server_layout.addRow("Port:", self.port_input)

        layout.addWidget(server_group)

        # API Key Management
        api_group = QGroupBox("API Key Management")
        api_layout = QVBoxLayout(api_group)

        # API Keys table
        self.api_table = QTableWidget()
        self.api_table.setColumnCount(4)
        self.api_table.setHorizontalHeaderLabels(['API Key', 'Device ID', 'Status', 'Last Used'])

        # Set column widths
        header = self.api_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.api_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.api_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Make non-editable
        self.api_table.setMinimumHeight(150)
        api_layout.addWidget(self.api_table)

        # API Key controls
        api_controls = QHBoxLayout()
        self.generate_key_btn = QPushButton("Generate New Key")
        self.copy_key_btn = QPushButton("Copy Key")
        self.revoke_key_btn = QPushButton("Revoke Selected Key")
        self.refresh_keys_btn = QPushButton("Refresh")

        self.generate_key_btn.clicked.connect(self.generate_api_key)
        self.copy_key_btn.clicked.connect(self.copy_api_key)
        self.revoke_key_btn.clicked.connect(self.revoke_api_key)
        self.refresh_keys_btn.clicked.connect(self.load_api_keys)

        api_controls.addWidget(self.generate_key_btn)
        api_controls.addWidget(self.copy_key_btn)
        api_controls.addWidget(self.revoke_key_btn)
        api_controls.addStretch()
        api_controls.addWidget(self.refresh_keys_btn)
        api_layout.addLayout(api_controls)

        layout.addWidget(api_group)

        # Startup settings group
        startup_group = QGroupBox("Startup Settings")
        startup_layout = QVBoxLayout(startup_group)

        self.autostart_checkbox = QCheckBox("Start server automatically when tray app launches")
        self.autostart_checkbox.setChecked(autostart)
        startup_layout.addWidget(self.autostart_checkbox)

        layout.addWidget(startup_group)

        # Information section
        info_group = QGroupBox("Server Information")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setMaximumHeight(120)
        info_text.setReadOnly(True)
        info_text.setPlainText(
            "The BigTime server provides a REST API for multiple client devices to sync time tracking data. "
            "Configure the host and port based on your network requirements:\n\n"
            "• Use 127.0.0.1 (localhost) for single-machine testing\n"
            "• Use 0.0.0.0 to accept connections from all network interfaces\n"
            "• Use specific IP address to bind to one network interface\n"
            "• Default port 5000 should work for most installations\n\n"
            "Time synchronization uses NTP servers optimized for the selected timezone."
        )
        info_layout.addWidget(info_text)

        layout.addWidget(info_group)

        # Validation status
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Initial validation
        self.validate_inputs()

    def validate_inputs(self):
        """Validate user inputs and update UI accordingly"""
        host = self.host_input.text().strip()
        port = self.port_input.value()

        # Basic host validation
        valid = True
        status_msg = "✅ Configuration valid"

        if not host:
            valid = False
            status_msg = "❌ Host address is required"
        elif host not in ['0.0.0.0', '127.0.0.1', 'localhost']:
            # Basic IP validation (could be improved)
            import re
            if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', host):
                valid = False
                status_msg = "⚠️ Please verify host address format"

        # Port validation
        if port < 1024:
            valid = False
            status_msg = "❌ Port must be 1024 or higher"

        self.status_label.setText(status_msg)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)

    def showEvent(self, event):
        """Load API keys when dialog is shown"""
        super().showEvent(event)
        self.load_api_keys()

    def load_api_keys(self):
        """Load and display API keys from the server database"""
        try:
            from server.server import get_standalone_db

            conn = get_standalone_db()
            cursor = conn.execute("""
                SELECT key, device_id, active, last_used, created_at
                FROM api_keys
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            conn.close()

            self.api_table.setRowCount(len(rows))

            for i, row in enumerate(rows):
                # Mask API key for display (show first 8 and last 4 characters)
                api_key = row['key']
                if len(api_key) > 12:
                    masked_key = api_key[:8] + '...' + api_key[-4:]
                else:
                    masked_key = api_key

                self.api_table.setItem(i, 0, QTableWidgetItem(masked_key))
                self.api_table.setItem(i, 1, QTableWidgetItem(row['device_id'] or 'N/A'))

                status = "✅ Active" if row['active'] else "❌ Revoked"
                self.api_table.setItem(i, 2, QTableWidgetItem(status))

                last_used = row['last_used'] or 'Never'
                if last_used != 'Never':
                    # Format timestamp nicely
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(last_used)
                        last_used = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass

                self.api_table.setItem(i, 3, QTableWidgetItem(last_used))

                # Store full API key in item data for revocation
                self.api_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, api_key)

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Error', f'Failed to load API keys: {e}')

    def generate_api_key(self):
        """Generate a new API key"""
        try:
            import uuid

            from PyQt6.QtWidgets import QInputDialog, QMessageBox

            from server.server import get_standalone_db

            # Get device ID from user
            device_id, ok = QInputDialog.getText(
                self, 'New API Key', 'Enter device ID (optional):',
                text=f'device-{uuid.uuid4().hex[:8]}'
            )

            if not ok:
                return

            device_id = device_id.strip() or f'device-{uuid.uuid4().hex[:8]}'

            # Generate API key
            api_key = f'bt-{uuid.uuid4().hex}'

            # Save to database
            conn = get_standalone_db()
            conn.execute("""
                INSERT INTO api_keys (key, device_id, active, created_at, last_used)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP, NULL)
            """, (api_key, device_id))
            conn.commit()
            conn.close()

            # Show generated key to user
            QMessageBox.information(
                self, 'API Key Generated',
                f'New API Key: {api_key}\n\nDevice ID: {device_id}\n\n'
                'Please copy and save this API key securely. '
                'It will be masked in the list for security.'
            )

            # Refresh the list
            self.load_api_keys()

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Error', f'Failed to generate API key: {e}')

    def revoke_api_key(self):
        """Revoke the selected API key"""
        try:
            current_row = self.api_table.currentRow()
            if current_row < 0:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, 'No Selection', 'Please select an API key to revoke.')
                return

            # Get the full API key from item data
            api_key_item = self.api_table.item(current_row, 0)
            api_key = api_key_item.data(Qt.ItemDataRole.UserRole)

            # Confirm revocation
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, 'Confirm Revocation',
                f'Are you sure you want to revoke this API key?\n\n'
                f'Key: {api_key_item.text()}\n'
                f'Device: {self.api_table.item(current_row, 1).text()}\n\n'
                'This action cannot be undone.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Update database
            from server.server import get_standalone_db
            conn = get_standalone_db()
            conn.execute("""
                UPDATE api_keys
                SET active = 0, last_used = CURRENT_TIMESTAMP
                WHERE key = ?
            """, (api_key,))
            conn.commit()
            conn.close()

            QMessageBox.information(self, 'Success', 'API key has been revoked.')

            # Refresh the list
            self.load_api_keys()

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Error', f'Failed to revoke API key: {e}')

    def copy_api_key(self):
        """Copy selected API key information to clipboard"""
        try:
            current_row = self.api_table.currentRow()
            if current_row < 0:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, 'No Selection', 'Please select an API key to copy.')
                return

            # Get the API key and device ID from the selected row
            api_key_item = self.api_table.item(current_row, 0)
            device_id_item = self.api_table.item(current_row, 1)
            status_item = self.api_table.item(current_row, 2)

            # Get the full API key from item data
            full_api_key = api_key_item.data(Qt.ItemDataRole.UserRole)
            device_id = device_id_item.text()
            status = status_item.text()

            # Check if the key is active
            if "Revoked" in status:
                from PyQt6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self, 'Revoked Key',
                    'This API key has been revoked and will not work for authentication. '
                    'Do you still want to copy it?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            # Format the text to copy
            copy_text = f"Device-ID: {device_id}\nAPI-Key: {full_api_key}"

            # Copy to clipboard
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(copy_text)

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Error', f'Failed to copy API key: {e}')

    def get_values(self):
        """Get the configuration values"""
        return {
            'host': self.host_input.text().strip() or '127.0.0.1',
            'port': self.port_input.value(),
            'autostart': self.autostart_checkbox.isChecked()
        }


class ClientSyncConfigDialog(QDialog):
    """Client-side server sync configuration dialog"""

    def __init__(self, parent=None, server_url='', device_id='', api_key='', sync_interval=5):
        super().__init__(parent)
        self.setWindowTitle("Server Sync Configuration")
        set_dialog_icon(self)
        self.setModal(True)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # Server connection group
        server_group = QGroupBox("Server Connection")
        server_layout = QFormLayout(server_group)

        # Server URL
        self.server_url_input = QLineEdit(server_url)
        self.server_url_input.setPlaceholderText("http://127.0.0.1:5000")
        self.server_url_input.textChanged.connect(self.validate_inputs)
        server_layout.addRow("Server URL:", self.server_url_input)

        # Device ID
        self.device_id_input = QLineEdit(device_id)
        self.device_id_input.setPlaceholderText("unique-device-name")
        server_layout.addRow("Device ID:", self.device_id_input)

        # API Key
        self.api_key_input = QLineEdit(api_key)
        self.api_key_input.setPlaceholderText("your-api-key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        # Show/Hide API Key button
        show_api_btn = QPushButton("Show")
        show_api_btn.setMaximumWidth(60)
        show_api_btn.clicked.connect(self.toggle_api_key_visibility)
        api_layout = QHBoxLayout()
        api_layout.addWidget(self.api_key_input)
        api_layout.addWidget(show_api_btn)
        server_layout.addRow("API Key:", api_layout)

        layout.addWidget(server_group)

        # Sync settings group
        sync_group = QGroupBox("Sync Settings")
        sync_layout = QFormLayout(sync_group)

        # Sync interval
        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setMinimum(5)
        self.sync_interval_spin.setMaximum(360)
        self.sync_interval_spin.setSuffix(' seconds')
        self.sync_interval_spin.setValue(sync_interval)
        sync_layout.addRow("Sync Interval:", self.sync_interval_spin)

        layout.addWidget(sync_group)

        # Test connection button
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        layout.addWidget(self.test_btn)

        # Information section
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)

        info_text = QLabel()
        info_text.setWordWrap(True)
        info_text.setText(
            "Configure your BigTime client to sync with a BigTime server. The server URL should include "
            "the protocol (http:// or https://) and port number. Your device ID should be unique for "
            "this client installation, and you'll need a valid API key from your server administrator."
        )
        info_layout.addWidget(info_text)

        layout.addWidget(info_group)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Initial validation
        self.validate_inputs()

    def toggle_api_key_visibility(self):
        """Toggle API key field visibility"""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.sender().setText("Hide")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.sender().setText("Show")

    def validate_inputs(self):
        """Validate form inputs"""
        valid = True
        status_msg = "✅ Configuration looks good"

        server_url = self.server_url_input.text().strip()

        # Validate server URL
        if not server_url:
            valid = False
            status_msg = "❌ Server URL is required"
        elif not (server_url.startswith('http://') or server_url.startswith('https://')):
            valid = False
            status_msg = "❌ Server URL must start with http:// or https://"

        self.status_label.setText(status_msg)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)

    def test_connection(self):
        """Test connection to the server"""
        import requests
        from PyQt6.QtWidgets import QApplication

        server_url = self.server_url_input.text().strip()
        api_key = self.api_key_input.text().strip()

        if not server_url:
            self.status_label.setText("❌ Enter server URL first")
            return

        self.test_btn.setText("Testing...")
        self.test_btn.setEnabled(False)
        self.status_label.setText("⏳ Connecting to server...")
        QApplication.processEvents()

        try:
            headers = {'Content-Type': 'application/json'}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'

            # Test /health endpoint first
            response = requests.get(f"{server_url}/health", headers=headers, timeout=10)

            if response.status_code == 200:
                # Also test /api/v1/info to verify API key works
                if api_key:
                    try:
                        info_response = requests.get(
                            f"{server_url}/api/v1/info",
                            headers=headers,
                            timeout=5
                        )
                        if info_response.status_code == 200:
                            data = info_response.json()
                            if data.get('success'):
                                company = data.get('data', {}).get('company_name', 'Unknown')
                                self.status_label.setText(f"✅ Connected to {company}!")
                            else:
                                self.status_label.setText("✅ Connection successful (verify API key)")
                        elif info_response.status_code == 401:
                            self.status_label.setText("⚠️ Server reachable but API key invalid")
                        else:
                            self.status_label.setText(f"✅ Server reachable (API status: {info_response.status_code})")
                    except Exception:
                        self.status_label.setText("✅ Server reachable (couldn't verify API key)")
                else:
                    self.status_label.setText("✅ Server reachable (no API key to test)")
            elif response.status_code == 401:
                self.status_label.setText("⚠️ Server reachable but authentication failed")
            else:
                self.status_label.setText(f"❌ Server error: HTTP {response.status_code}")

        except requests.exceptions.ConnectionError as e:
            error_msg = str(e)
            if "Errno 10061" in error_msg or "Connection refused" in error_msg:
                self.status_label.setText("❌ Server not running or port blocked")
            elif "Name or service not known" in error_msg or "nodename nor servname provided" in error_msg:
                self.status_label.setText("❌ Invalid server address")
            else:
                self.status_label.setText(f"❌ Cannot connect: {error_msg[:50]}")
        except requests.exceptions.Timeout:
            self.status_label.setText("❌ Connection timeout (server too slow or unreachable)")
        except Exception as e:
            self.status_label.setText(f"❌ Connection failed: {str(e)[:60]}")
        finally:
            self.test_btn.setText("Test Connection")
            self.test_btn.setEnabled(True)

    def get_values(self):
        """Get the configuration values"""
        return {
            'server_url': self.server_url_input.text().strip(),
            'device_id': self.device_id_input.text().strip(),
            'api_key': self.api_key_input.text().strip(),
            'sync_interval': self.sync_interval_spin.value()
        }


class PinDialog(QDialog):
    """Dialog for PIN entry and setting"""

    def __init__(self, parent=None, is_setting_pin=False):
        super().__init__(parent)
        self.is_setting_pin = is_setting_pin
        self.setWindowTitle("Set PIN" if is_setting_pin else "Enter PIN")
        # self.setFixedSize(350, 200)

        layout = QVBoxLayout(self)

        # Main group box
        group_box = QGroupBox(self)
        group_layout = QFormLayout(group_box)

        # Header
        if is_setting_pin:
            header_text = "Set Your PIN"
            instruction_text = "Please set a 4-digit PIN for secure clock operations:"
        else:
            header_text = "Enter PIN"

        header_label = QLabel(header_text)
        header_label.setFont(fonts["header"])
        layout.addWidget(header_label)

        if is_setting_pin:
            info_label = QLabel(instruction_text)
            info_label.setWordWrap(True)
            info_label.setStyleSheet('color: #666; margin-bottom: 10px;')
            layout.addWidget(info_label)
        else: layout.addSpacing(10)

        # PIN input
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setMaxLength(4)
        self.pin_input.setPlaceholderText("Enter 4-digit PIN")
        group_layout.addRow("PIN:", self.pin_input)

        # Confirm PIN input (only for setting)
        if is_setting_pin:
            self.confirm_pin_input = QLineEdit()
            self.confirm_pin_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_pin_input.setMaxLength(4)
            self.confirm_pin_input.setPlaceholderText("Confirm PIN")
            group_layout.addRow("Confirm PIN:", self.confirm_pin_input)

        layout.addWidget(group_box)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Set focus to PIN input
        self.pin_input.setFocus()

    def get_pin(self) -> str:
        """Get the entered PIN"""
        return self.pin_input.text().strip()

    def get_confirm_pin(self) -> str:
        """Get the confirmed PIN (only for setting)"""
        if self.is_setting_pin:
            return self.confirm_pin_input.text().strip()
        return ""

    def accept(self):
        """Validate PIN before accepting"""
        pin = self.get_pin()

        # Validate PIN format
        if not pin or len(pin) != 4 or not pin.isdigit():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid PIN", "PIN must be exactly 4 digits.")
            return

        # Validate PIN confirmation if setting
        if self.is_setting_pin:
            confirm_pin = self.get_confirm_pin()
            if pin != confirm_pin:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "PIN Mismatch", "PINs do not match. Please try again.")
                return

        super().accept()
