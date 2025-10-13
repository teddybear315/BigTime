from PyQt6.QtCore import QDate, QDateTime, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDateTimeEdit,
                             QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QVBoxLayout)


class EditLogsDialog(QDialog):
    log_removed = pyqtSignal(int)  # log_id
    def __init__(self, logs, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Edit Time Logs')
        # enforce a minimum width so the inline editor has room
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        self.edits = []
        self.remove_buttons = {}
        for log_id, clock_in, clock_out in logs:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(f'Log ID: {log_id}'))
            in_edit = QDateTimeEdit()
            in_edit.setCalendarPopup(True)
            in_edit.setDisplayFormat('MM-dd-yyyy HH:mm:ss')
            try:
                if clock_in:
                    dt = QDateTime.fromString(clock_in, 'MM-dd-yyyy HH:mm:ss')
                    if dt.isValid():
                        in_edit.setDateTime(dt)
                else:
                    in_edit.setDateTime(QDateTime.currentDateTime())
            except Exception:
                in_edit.setDateTime(QDateTime.currentDateTime())

            out_edit = QDateTimeEdit()
            out_edit.setCalendarPopup(True)
            out_edit.setDisplayFormat('MM-dd-yyyy HH:mm:ss')
            try:
                if clock_out:
                    dt2 = QDateTime.fromString(clock_out, 'MM-dd-yyyy HH:mm:ss')
                    if dt2.isValid():
                        out_edit.setDateTime(dt2)
                else:
                    out_edit.setDateTime(QDateTime.currentDateTime())
            except Exception:
                out_edit.setDateTime(QDateTime.currentDateTime())

            row_layout.addWidget(QLabel('In:'))
            row_layout.addWidget(in_edit)
            row_layout.addWidget(QLabel('Out:'))
            row_layout.addWidget(out_edit)
            remove_btn = QPushButton('Remove')
            remove_btn.clicked.connect(lambda _, lid=log_id: self.remove_log(lid))
            row_layout.addWidget(remove_btn)
            self.remove_buttons[log_id] = remove_btn
            layout.addLayout(row_layout)
            self.edits.append((log_id, in_edit, out_edit))
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_updates(self):
        updates = []
        for log_id, in_edit, out_edit in self.edits:
            try:
                in_str = in_edit.dateTime().toString('MM-dd-yyyy HH:mm:ss')
            except Exception:
                in_str = ''
            try:
                out_str = out_edit.dateTime().toString('MM-dd-yyyy HH:mm:ss')
            except Exception:
                out_str = ''
            updates.append((log_id, in_str, out_str))
        return updates

    def remove_log(self, log_id):
        self.log_removed.emit(log_id)
        for idx, (lid, in_edit, out_edit) in enumerate(self.edits):
            if lid == log_id:
                try:
                    in_edit.setDisabled(True)
                except Exception:
                    pass
                try:
                    out_edit.setDisabled(True)
                except Exception:
                    pass
                self.remove_buttons[log_id].setDisabled(True)
                break



class AddEmployeeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add Employee')
        self.setModal(True)
        layout = QFormLayout(self)
        self.name = QLineEdit()
        self.phone = QLineEdit()
        self.badge = QLineEdit()
        self.pin_enabled = QCheckBox('Enable PIN?')
        self.pin = QLineEdit()
        self.department = QLineEdit()
        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.hire_date = QDateEdit()
        self.hire_date.setCalendarPopup(True)
        self.deactivated = QCheckBox('Deactivated')
        self.ssn = QLineEdit()
        self.period = QComboBox()
        self.period.addItems(['hourly', 'monthly'])
        self.rate = QDoubleSpinBox()
        self.rate.setMaximum(1000000)
        layout.addRow('Name:', self.name)
        layout.addRow('Phone Number:', self.phone)
        layout.addRow('Badge:', self.badge)
        layout.addRow(self.pin_enabled)
        layout.addRow('PIN:', self.pin)
        layout.addRow('Department:', self.department)
        layout.addRow('Date of Birth:', self.dob)
        layout.addRow('Hire Date:', self.hire_date)
        layout.addRow(self.deactivated)
        layout.addRow('SSN:', self.ssn)
        layout.addRow('Period:', self.period)
        layout.addRow('Rate:', self.rate)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    def set_data(self, data):
        try:
            if hasattr(data, 'name'):
                self.name.setText(getattr(data, 'name', ''))
                self.phone.setText(str(getattr(data, 'phone_number', '') or ''))
                self.badge.setText(str(getattr(data, 'badge', '') or ''))
                self.pin_enabled.setChecked(bool(getattr(data, 'pin_enabled', 0)))
                self.pin.setText(str(getattr(data, 'pin', '') or ''))
                self.department.setText(getattr(data, 'department', '') or '')
                self.dob.setDate(QDate.fromString(getattr(data, 'date_of_birth', '01-01-2000') or '01-01-2000', 'MM-dd-yyyy'))
                self.hire_date.setDate(QDate.fromString(getattr(data, 'hire_date', '01-01-2000') or '01-01-2000', 'MM-dd-yyyy'))
                self.deactivated.setChecked(bool(getattr(data, 'deactivated', 0)))
                self.ssn.setText(str(getattr(data, 'ssn', '') or ''))
                idx = self.period.findText(getattr(data, 'period', 'hourly') or 'hourly')
                if idx >= 0:
                    self.period.setCurrentIndex(idx)
                self.rate.setValue(float(getattr(data, 'rate', 0) or 0))
                return
        except Exception:
            pass
        self.name.setText(data.get('name', ''))
        self.phone.setText(str(data.get('phone_number', '')))
        self.badge.setText(str(data.get('badge', '')))
        self.pin_enabled.setChecked(bool(data.get('pin_enabled', 0)))
        self.pin.setText(str(data.get('pin', '')))
        self.department.setText(data.get('department', ''))
        self.dob.setDate(QDate.fromString(data.get('date_of_birth', '01-01-2000'), 'MM-dd-yyyy'))
        self.hire_date.setDate(QDate.fromString(data.get('hire_date', '01-01-2000'), 'MM-dd-yyyy'))
        self.deactivated.setChecked(bool(data.get('deactivated', 0)))
        self.ssn.setText(str(data.get('ssn', '')))
        idx = self.period.findText(data.get('period', 'hourly'))
        if idx >= 0:
            self.period.setCurrentIndex(idx)
        self.rate.setValue(float(data.get('rate', 0)))

    def get_data(self):
        return {
            'name': self.name.text().strip(),
            'phone_number': self.phone.text().strip(),
            'badge': self.badge.text().strip(),
            'pin_enabled': int(self.pin_enabled.isChecked()),
            'pin': self.pin.text().strip(),
            'department': self.department.text().strip(),
            'date_of_birth': self.dob.date().toString('MM-dd-yyyy'),
            'hire_date': self.hire_date.date().toString('MM-dd-yyyy'),
            'deactivated': int(self.deactivated.isChecked()),
            'ssn': self.ssn.text().strip(),
            'period': self.period.currentText(),
            'rate': float(self.rate.value()),
        }


class SettingsDialog(QDialog):
    def __init__(self, parent=None, company_name='', time_server='', manager_pin='', report_save_path='', show_ntp=True):
        super().__init__(parent)
        self.setWindowTitle('Database Settings')
        layout = QVBoxLayout(self)
        self.company_label = QLabel('Company Name:')
        self.company_edit = QLineEdit(company_name)
        layout.addWidget(self.company_label)
        layout.addWidget(self.company_edit)
        self.ntp_label = QLabel('Time Server Address:')
        self.ntp_edit = QLineEdit(time_server)
        layout.addWidget(self.ntp_label)
        layout.addWidget(self.ntp_edit)
        self.pin_label = QLabel('Manager PIN:')
        self.pin_edit = QLineEdit(manager_pin)
        self.pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pin_label)
        layout.addWidget(self.pin_edit)
        self.show_ntp_cb = QCheckBox('Show NTP status indicator')
        self.show_ntp_cb.setChecked(bool(show_ntp))
        layout.addWidget(self.show_ntp_cb)
        self.path_label = QLabel('Report Save Path:')
        self.path_edit = QLineEdit(report_save_path)
        self.browse_btn = QPushButton('Browse...')
        self.browse_btn.clicked.connect(self.browse)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        layout.addWidget(self.path_label)
        layout.addLayout(path_layout)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def browse(self):
        dir_path = QFileDialog.getExistingDirectory(self, 'Select Directory', self.path_edit.text())
        if dir_path:
            self.path_edit.setText(dir_path)

    def get_values(self):
        return {
            'company_name': self.company_edit.text().strip(),
            'ntp_server': self.ntp_edit.text().strip(),
            'manager_pin': self.pin_edit.text().strip(),
            'report_save_path': self.path_edit.text().strip(),
            'show_ntp_status': '1' if self.show_ntp_cb.isChecked() else '0'
        }


class OOTBManagerDialog(QDialog):
    def __init__(self, parent=None, company_name='', time_server='', manager_pin='', report_save_path=''):
        super().__init__(parent)
        self.setWindowTitle('Manager Setup')
        layout = QVBoxLayout(self)
        self.company_label = QLabel('Company Name:')
        self.company_edit = QLineEdit(company_name)
        layout.addWidget(self.company_label)
        layout.addWidget(self.company_edit)
        self.ntp_label = QLabel('Time Server Address:')
        self.ntp_edit = QLineEdit(time_server)
        layout.addWidget(self.ntp_label)
        layout.addWidget(self.ntp_edit)
        self.pin_label = QLabel('Manager PIN:')
        self.pin_edit = QLineEdit(manager_pin)
        self.pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pin_label)
        layout.addWidget(self.pin_edit)
        self.pin_confirm_label = QLabel('Confirm PIN:')
        self.pin_confirm_edit = QLineEdit()
        self.pin_confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pin_confirm_label)
        layout.addWidget(self.pin_confirm_edit)
        self.path_label = QLabel('Report Save Path:')
        self.path_edit = QLineEdit(report_save_path)
        self.browse_btn = QPushButton('Browse...')
        self.browse_btn.clicked.connect(self.browse)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        layout.addWidget(self.path_label)
        layout.addLayout(path_layout)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def browse(self):
        dir_path = QFileDialog.getExistingDirectory(self, 'Select Directory', self.path_edit.text())
        if dir_path:
            self.path_edit.setText(dir_path)

    def get_values(self):
        return {
            'company_name': self.company_edit.text().strip(),
            'ntp_server': self.ntp_edit.text().strip(),
            'manager_pin': self.pin_edit.text().strip(),
            'manager_pin_confirm': self.pin_confirm_edit.text().strip(),
            'report_save_path': self.path_edit.text().strip()
        }


class DateRangeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Date Range')
        layout = QVBoxLayout(self)
        self.start_label = QLabel('Start Date:')
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.end_label = QLabel('End Date:')
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        layout.addWidget(self.start_label)
        layout.addWidget(self.start_date)
        layout.addWidget(self.end_label)
        layout.addWidget(self.end_date)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_dates(self):
        return self.start_date.date().toString('MM-dd-yyyy'), self.end_date.date().toString('MM-dd-yyyy')
