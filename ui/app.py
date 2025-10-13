import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import ntplib
from PyQt6.QtCore import QDate, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QIcon
from PyQt6.QtWidgets import (QApplication, QDateEdit, QDialog,
                             QDialogButtonBox, QFileDialog, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QMenuBar,
                             QMessageBox, QPushButton, QSizePolicy,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

import db_helpers
from db_helpers import get_setting, set_setting
from ui.dialogs import (AddEmployeeDialog, DateRangeDialog, EditLogsDialog,
                        OOTBManagerDialog, SettingsDialog)
from ui.ntp_worker import NTPWorker
from ui.pdf_utils import generate_paystub_pdf
from utils import (fetch_employees, fetch_logs_for_employee_date,
                   to_int_optional)

# PROJECT_ROOT is the root folder for relative assets; keep behavior consistent with previous code
# PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TimeClockApp(QWidget):
    fonts = {
        "default": QFont("Verdana", 14),
        "large": QFont("Verdana", 20),
        "monospace": QFont("Courier New", 20),
    }

    def __init__(self):
        super().__init__()
        # Load defaults from database
        try:
            # Load instance defaults from settings using centralized helper
            self.company_name = get_setting('company_name', '')
            self.ntp_server = get_setting('ntp_server', 'tick.usnogps.navy.mil')
            self.manager_pin = get_setting('manager_pin', '')
            self.report_save_path = get_setting('report_save_path', str(Path(__file__).resolve() / "reports"))
            self.show_ntp_status = (get_setting('show_ntp_status', '1') == '1')
            # manager password and ootb flag may be present; check_manager_password will reconcile
            self.manager_password = get_setting('manager_password', None)
            self.manager_ootb = (get_setting('manager_password_ootb', '0') == '1')
        except Exception:
            # Fall back to sensible defaults
            self.ntp_server = 'tick.usnogps.navy.mil'
            self.company_name = ''
            self.manager_pin = ''
            self.report_save_path = str(Path(__file__).resolve() / "reports")
            self.show_ntp_status = True
            self.manager_password = None
            self.manager_ootb = False

        # Ensure manager password exists or run OOTB flow
        self.check_manager_password()
        self.setup_ntp_label()
        self.setup_menu()
        self.setup_form()
        self.setup_layout()
        self.ntp_thread = QThread()
        self.ntp_worker = NTPWorker(self.ntp_server, interval=5)
        self.ntp_worker.moveToThread(self.ntp_thread)
        self.ntp_worker.time_updated.connect(self.handle_ntp_time_updated)
        self.ntp_worker.error.connect(self.handle_ntp_error)
        self.ntp_thread.started.connect(self.ntp_worker.run)
        self.ntp_thread.start()

        # GUI-side clock updater: update the visible clock every 500ms using last NTP sync as baseline
        self.last_ntp_dt = None
        self.last_ntp_wall = None
        self.gui_clock_timer = QTimer(self)
        self.gui_clock_timer.timeout.connect(self.update_clock_display)
        self.gui_clock_timer.start(500)


    def check_manager_password(self):
        # Check settings using helper functions; ensure manager_pin exists
        mp = get_setting('manager_pin', None)
        if mp is None:
            set_setting('manager_pin', '1234')
            set_setting('manager_password_ootb', '1')
            self.manager_pin = '1234'
            self.manager_ootb = True
        else:
            self.manager_pin = mp
        if self.manager_ootb:
            self.prompt_change_manager_password()

    def setup_ntp_label(self):
        self.ntp_time_label = QLabel('NTP Time: ...')
        self.ntp_time_label.setFont(self.fonts["monospace"])
        # Small status indicator (like Notepad's UTF-8 indicator) for server + last sync
        self.ntp_status_label = QLabel('')
        small_font = QFont(self.fonts['default'].family(), 9)
        self.ntp_status_label.setFont(small_font)
        self.ntp_status_label.setStyleSheet('color: gray;')
        # Prevent the status from expanding vertically or horizontally
        self.ntp_status_label.setMinimumHeight(16)
        self.ntp_status_label.setMaximumHeight(16)

    def update_ntp_time(self):
        try:
            client = ntplib.NTPClient()
            response = client.request(self.ntp_server, version=3)
            dt = datetime.fromtimestamp(response.tx_time, tz=timezone.utc).astimezone()
            self.ntp_time_label.setText(f"{dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            self.ntp_time_label.setText('NTP Time: Error')

    def update_clock_display(self):
        """Update the visible clock every 500ms using the last NTP sync as baseline.
        If we have a last NTP datetime, advance it by wall-clock time since that sync.
        Otherwise, fall back to local system time."""
        if self.last_ntp_dt and self.last_ntp_wall:
            elapsed = time.time() - self.last_ntp_wall
            current = self.last_ntp_dt + timedelta(seconds=elapsed)
        else:
            current = datetime.now()
        # Show up to seconds (sync happens every 5s); updating twice a second keeps UI responsive
        self.ntp_time_label.setText(current.strftime('%Y-%m-%d %H:%M:%S'))


    def setup_menu(self):
        self.menu_bar = QMenuBar(self)
        self.is_moderator = False
        # Add Exit directly to the main menu bar for easy access
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        self.menu_bar.addAction(exit_action)

        # Moderator menu triggers login
        self.moderator_menu = self.menu_bar.addMenu('Moderator')
        self.moderator_menu.aboutToShow.connect(self.handle_moderator_menu)
        # Moderator menu actions
        logout_action = QAction('Logout', self)
        logout_action.triggered.connect(self.logout)
        self.moderator_menu.addAction(logout_action)

        # Admin menus (Maintenance, Tools) are disabled by default; Reporting is always enabled
        self.maintenance_menu = self.menu_bar.addMenu('Maintenance')
        self.tools_menu = self.menu_bar.addMenu('Tools')
        self.reporting_menu = self.menu_bar.addMenu('Reporting')
        for menu in [self.maintenance_menu, self.tools_menu]:
            menu.setEnabled(False)
        self.reporting_menu.setEnabled(True)

        # Example actions for each admin menu
        add_emp_action = QAction('Add Employee', self)
        add_emp_action.triggered.connect(self.add_employee)
        self.maintenance_menu.addAction(add_emp_action)
        view_emp_action = QAction('View Employees', self)
        view_emp_action.triggered.connect(self.view_employees)
        self.maintenance_menu.addAction(view_emp_action)
        # Add View Time Logs under Tools for admin inspection
        view_logs_action = QAction('View Time Logs', self)
        view_logs_action.triggered.connect(self.view_time_logs)
        self.tools_menu.addAction(view_logs_action)
        gen_report_action = QAction('Generate Report', self)
        gen_report_action.triggered.connect(self.generate_report)
        backup_db_action = QAction('Backup Database', self)
        backup_db_action.triggered.connect(self.backup_database)
        self.reporting_menu.addAction(gen_report_action)
        self.reporting_menu.addAction(backup_db_action)
        edit_times_action = QAction('Edit Time Logs', self)
        edit_times_action.triggered.connect(self.edit_times)
        self.tools_menu.addAction(edit_times_action)
        settings_action = QAction('Settings', self)
        settings_action.triggered.connect(self.edit_db_settings)
        self.tools_menu.addAction(settings_action)

    def setup_form(self):
        self.employee_label = QLabel('Employee ID:')
        self.employee_label.setFont(self.fonts["large"])
        self.employee_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.employee_input = QLineEdit()
        self.employee_input.setFont(self.fonts["large"])
        self.employee_input.setMinimumHeight(50)
        self.clock_in_btn = QPushButton('Clock In')
        self.clock_in_btn.setFont(self.fonts["large"])
        self.clock_in_btn.setMinimumHeight(60)
        self.clock_out_btn = QPushButton('Clock Out')
        self.clock_out_btn.setFont(self.fonts["large"])
        self.clock_out_btn.setMinimumHeight(60)
        self.status_label = QLabel('Status: Ready')
        self.status_label.setFont(self.fonts["default"])
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.clock_in_btn.clicked.connect(self.clock_in)
        self.clock_out_btn.clicked.connect(self.clock_out)

    def setup_layout(self):
        # self.setWindowIcon(QIcon(str(PROJECT_ROOT / 'ico.ico')))
        # Set title with company name if available
        self.setWindowTitle(f"{getattr(self, 'company_name', '') + ' - ' if getattr(self, 'company_name', '') else ''}TimeClock")
        main_layout = QVBoxLayout()
        main_layout.setMenuBar(self.menu_bar)
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(12)
        self.setMinimumSize(400, 400)

        # Clock group (stays at top)
        clock_group = QHBoxLayout()
        clock_group.addStretch()
        clock_group.addWidget(self.ntp_time_label)
        clock_group.addStretch()
        main_layout.addLayout(clock_group)

        # Middle row: employee group (left) and controls group (right)
        middle_row = QVBoxLayout()

        # Employee group: label above input, expands to take available space
        emp_widget = QWidget()
        emp_layout = QVBoxLayout(emp_widget)
        emp_layout.setContentsMargins(0, 0, 0, 0)
        emp_layout.setSpacing(6)
        emp_layout.addWidget(self.employee_label)
        emp_layout.addWidget(self.employee_input)
        middle_row.addWidget(emp_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # Controls group: buttons stacked and status underneath; keep compact width
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)
        btns_row = QHBoxLayout()
        btns_row.addWidget(self.clock_in_btn)
        btns_row.addWidget(self.clock_out_btn)
        controls_layout.addLayout(btns_row)
        controls_layout.addWidget(self.status_label)
        middle_row.addWidget(controls_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(middle_row, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addStretch(1)

        # Footer: small Fetch button at left and compact NTP status anchored to bottom-right
        footer_layout = QHBoxLayout()
        fetch_btn = QPushButton('Fetch')
        fetch_btn.setToolTip('Fetch time from NTP server now')
        fetch_btn.setFont(QFont(self.fonts['default'].family(), 9))
        fetch_btn.setFixedSize(QSize(56, 18))
        fetch_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        fetch_btn.clicked.connect(self.fetch_now)
        self.fetch_btn = fetch_btn
        footer_layout.addWidget(fetch_btn, 0, Qt.AlignmentFlag.AlignLeft)
        footer_layout.addStretch()
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.addWidget(self.ntp_status_label)
        self.status_container = status_container
        status_container.setVisible(getattr(self, 'show_ntp_status', True))
        self.fetch_btn.setVisible(getattr(self, 'show_ntp_status', True))
        footer_layout.addWidget(status_container, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        main_layout.addLayout(footer_layout)

        self.setLayout(main_layout)

    def edit_db_settings(self):
        current_path = get_setting('report_save_path', str(Path(__file__).resolve() / "reports"))
        company_name = get_setting('company_name', '')
        time_server = get_setting('ntp_server', self.ntp_server)
        manager_pin = get_setting('manager_pin', '')
        show_ntp = get_setting('show_ntp_status', '1')

        dlg = SettingsDialog(self, company_name=company_name, time_server=time_server, manager_pin=manager_pin, report_save_path=current_path, show_ntp=(show_ntp == '1'))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.get_values()
            for key, value in vals.items():
                set_setting(key, value)
            show_ntp_val = vals.get('show_ntp_status', get_setting('show_ntp_status', '1'))
            set_setting('show_ntp_status', show_ntp_val)
            self.ntp_server = vals.get('ntp_server', self.ntp_server)
            self.company_name = vals.get('company_name', self.company_name)
            self.manager_pin = vals.get('manager_pin', self.manager_pin)
            self.report_save_path = vals.get('report_save_path', self.report_save_path)
            self.show_ntp_status = (show_ntp_val == '1')
            self.setWindowTitle(f"{self.company_name} - TimeClock" if self.company_name else "TimeClock")
            try:
                if hasattr(self, 'ntp_worker'):
                    self.ntp_worker.server_changed.emit(self.ntp_server)
            except Exception:
                pass
            try:
                if hasattr(self, 'status_container'):
                    self.status_container.setVisible(self.show_ntp_status)
                    self.fetch_btn.setVisible(self.show_ntp_status)
            except Exception:
                pass

    def prompt_change_manager_password(self):
        current_path = get_setting('report_save_path', str(Path(__file__).resolve() / "reports"))
        company_name = get_setting('company_name', '')
        time_server = get_setting('ntp_server', self.ntp_server)
        manager_pin = get_setting('manager_pin', '')
        manager_pin_confirm = ''
        while True:
            dlg = OOTBManagerDialog(self, company_name=company_name, time_server=time_server, manager_pin=manager_pin, report_save_path=current_path)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                QMessageBox.warning(self, 'Required', 'You must complete manager setup to continue.')
                continue
            vals = dlg.get_values()
            if not vals['manager_pin']:
                QMessageBox.warning(self, 'Invalid', 'PIN cannot be empty.')
                continue
            if vals['manager_pin'] != vals['manager_pin_confirm']:
                QMessageBox.warning(self, 'Mismatch', 'PINs do not match. Try again.')
                continue
            for key in ['company_name', 'ntp_server', 'manager_pin', 'report_save_path']:
                set_setting(key, vals[key])
            set_setting('manager_password_ootb', '0')
            self.manager_pin = vals['manager_pin']
            self.manager_ootb = False
            self.ntp_server = vals['ntp_server']
            self.company_name = vals['company_name']
            self.setWindowTitle(f"{self.company_name} - TimeClock" if self.company_name else "TimeClock")
            try:
                if hasattr(self, 'ntp_worker'):
                    self.ntp_worker.server_changed.emit(self.ntp_server)
            except Exception:
                pass
            break

    def moderator_login(self):
        if self.is_moderator:
            return
        password, ok = QInputDialog.getText(self, 'Moderator Login', 'Enter manager PIN:', QLineEdit.EchoMode.Password)
        if ok:
            if password == self.manager_pin:
                for menu in [self.maintenance_menu, self.reporting_menu, self.tools_menu]:
                    menu.setEnabled(True)
                self.is_moderator = True
                if self.manager_ootb: self.prompt_change_manager_password()
            else:
                QMessageBox.warning(self, 'Moderator', 'Incorrect PIN.')

    def handle_moderator_menu(self):
        if not self.is_moderator:
            self.moderator_login()

    def logout(self):
        self.is_moderator = False
        for menu in [self.maintenance_menu, self.reporting_menu, self.tools_menu]:
            menu.setEnabled(False)

    def backup_database(self):
        import shutil
        db_path = Path(__file__).resolve() / 'timeclock.db'
        backup_dir = Path(__file__).resolve() / 'reports'
        backup_dir.mkdir(exist_ok=True)
        now = datetime.now()
        backup_name = now.strftime('%m-%d-%Y %H-%M-%S') + '.db'
        backup_path = backup_dir / backup_name
        try:
            shutil.copy2(db_path, backup_path)
            QMessageBox.information(self, 'Backup', f'Database backed up as {backup_path}')
        except Exception as e:
            QMessageBox.warning(self, 'Backup Failed', f'Could not backup database: {e}')

    def edit_times(self):
        # ...existing code...
        from db_helpers import fetch_all_employees
        dlg = QDialog(self)
        dlg.setWindowTitle('Edit Time Logs')
        dlg.setFixedWidth(420)
        main_layout = QVBoxLayout(dlg)

        emp_label = QLabel('Select Employee:')
        main_layout.addWidget(emp_label)
        emp_table = QTableWidget()
        emp_table.setColumnCount(2)
        emp_table.setHorizontalHeaderLabels(['ID', 'Name'])
        emp_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        emp_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        emp_table.setColumnWidth(0, 40)
        emp_table.setColumnWidth(1, 340)
        main_layout.addWidget(emp_table)

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
        main_layout.addLayout(controls_row)

        logs_table = QTableWidget()
        logs_table.setColumnCount(4)
        logs_table.setHorizontalHeaderLabels(['ID', 'Clock In', 'Clock Out', ''])
        logs_table.setColumnWidth(0, 40)
        logs_table.setColumnWidth(1, 120)
        logs_table.setColumnWidth(2, 120)
        logs_table.setColumnWidth(3, 80)
        main_layout.addWidget(logs_table)

        btn_row = QHBoxLayout()
        close_btn = QPushButton('Close')
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        main_layout.addLayout(btn_row)

        def load_employees():
            rows = fetch_employees()
            emp_table.setRowCount(len(rows))
            for r, emp in enumerate(rows):
                badge = emp.badge
                name = emp.name
                internal_id = emp.id
                badge_item = QTableWidgetItem(badge)
                badge_item.setFlags(badge_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                try:
                    badge_item.setData(Qt.ItemDataRole.UserRole, internal_id)
                except Exception:
                    badge_item.setData(32, internal_id)
                name_item = QTableWidgetItem(name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                emp_table.setItem(r, 0, badge_item)
                emp_table.setItem(r, 1, name_item)

        original_rows = {}

        def load_logs_for_selected():
            selected = emp_table.selectedItems()
            if not selected:
                QMessageBox.warning(dlg, 'Select Employee', 'Please select an employee from the list.')
                return
            badge_item = emp_table.item(selected[0].row(), 0)
            emp_id = None
            try:
                emp_id = badge_item.data(Qt.ItemDataRole.UserRole)
            except Exception:
                try:
                    emp_id = badge_item.data(32)
                except Exception:
                    emp_id = None
            if emp_id is None:
                badge_text = badge_item.text()
                emp_id = None
            else:
                badge_text = emp_table.item(selected[0].row(), 0).text()
            date_str = date_edit.date().toString('yyyy-MM-dd')
            rows = fetch_logs_for_employee_date(badge_text, date_str)
            logs_table.setRowCount(len(rows))
            original_rows.clear()
            for r, log in enumerate(rows):
                lid = log.id
                ci = log.clock_in or ''
                co = log.clock_out or ''
                id_item = QTableWidgetItem(str(lid))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                ci_item = QTableWidgetItem(ci)
                ci_item.setFlags(ci_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                co_item = QTableWidgetItem(co)
                co_item.setFlags(co_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                logs_table.setItem(r, 0, id_item)
                logs_table.setItem(r, 1, ci_item)
                logs_table.setItem(r, 2, co_item)
                edit_btn = QPushButton('Edit')
                def _make_edit(lid_, cin_, cout_):
                    return lambda: edit_single_log(lid_, cin_, cout_)
                edit_btn.clicked.connect(_make_edit(lid, ci, co))
                logs_table.setCellWidget(r, 3, edit_btn)

        def edit_single_log(lid, cin, cout):
            ed = EditLogsDialog([(lid, cin, cout)], dlg)
            def _on_removed(removed_lid):
                try:
                    db_helpers.delete_log_by_id(removed_lid)
                finally:
                    load_logs_for_selected()
            try:
                ed.log_removed.connect(_on_removed)
            except Exception:
                pass
            if ed.exec() == QDialog.DialogCode.Accepted:
                updates = ed.get_updates()
                if updates:
                    _, new_in, new_out = updates[0]
                    db_helpers.update_log(lid, clock_in=new_in, clock_out=new_out)
                    load_logs_for_selected()

        load_btn.clicked.connect(load_logs_for_selected)
        close_btn.clicked.connect(dlg.accept)

        load_employees()
        dlg.exec()

    def add_employee(self):
        dialog = AddEmployeeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            phone_int = to_int_optional(data.get('phone_number', ''))
            ssn_int = to_int_optional(data.get('ssn', ''))
            from models import Employee as _Employee
            emp_obj = _Employee(
                id=None,
                name=data['name'],
                phone_number=phone_int,
                badge=str(data.get('badge', '')).strip(),
                pin_enabled=data['pin_enabled'],
                pin=data['pin'],
                department=data['department'],
                date_of_birth=data['date_of_birth'],
                hire_date=data['hire_date'],
                deactivated=data['deactivated'],
                ssn=ssn_int,
                period=data['period'],
                rate=data['rate'],
            )
            try:
                db_helpers.insert_employee(emp_obj)
            except ValueError as e:
                QMessageBox.warning(self, 'Duplicate Badge', str(e))
                return

    def edit_employees(self):
        emp_badge, ok = QInputDialog.getText(self, 'Edit Employee', 'Enter Employee badge to edit:')
        if not ok or not emp_badge.strip():
            return
        emp_badge = emp_badge.strip()
        emp = db_helpers.get_employee_by_badge(emp_badge)
        if not emp:
            QMessageBox.warning(self, 'Not Found', f'No employee found with badge {emp_badge}')
            return
        dialog = AddEmployeeDialog(self)
        dialog.setWindowTitle('Edit Employee')
        dialog.set_data(emp)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_data()
            phone_int = to_int_optional(new_data.get('phone_number', ''))
            ssn_int = to_int_optional(new_data.get('ssn', ''))
            upd = {
                'name': new_data['name'],
                'phone_number': phone_int,
                'badge': str(new_data.get('badge', '')).strip(),
                'pin_enabled': new_data['pin_enabled'],
                'pin': new_data['pin'],
                'department': new_data['department'],
                'date_of_birth': new_data['date_of_birth'],
                'hire_date': new_data['hire_date'],
                'deactivated': new_data['deactivated'],
                'ssn': ssn_int,
                'period': new_data['period'],
                'rate': new_data['rate'],
            }
            db_helpers.update_employee_by_badge(emp.badge, upd)
            QMessageBox.information(self, 'Success', 'Employee updated successfully!')

    def view_employees(self):
        def load_employees(table: QTableWidget):
            rows = db_helpers.fetch_all_employees()
            table.setRowCount(len(rows))
            for r, emp in enumerate(rows):
                badge_val = emp.badge
                name = emp.name
                internal_id = emp.id
                id_item = QTableWidgetItem(str(badge_val))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                name_item = QTableWidgetItem(name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r, 0, id_item)
                table.setItem(r, 1, name_item)
                edit_btn = QPushButton('Edit')
                edit_btn.setProperty('badge', badge_val)
                edit_btn.clicked.connect(lambda _checked, _badge=badge_val: edit_employee_row(_badge, dlg, table))
                table.setCellWidget(r, 2, edit_btn)
                del_btn = QPushButton('Delete')
                del_btn.setProperty('badge', badge_val)
                del_btn.clicked.connect(lambda _checked, _badge=badge_val: delete_employee_row(_badge, dlg, table))
                table.setCellWidget(r, 3, del_btn)

        def edit_employee_row(badge, parent_dialog, table):
            emp = db_helpers.get_employee_by_badge(badge)
            if not emp:
                QMessageBox.warning(parent_dialog, 'Not Found', 'Employee not found.')
                return
            ed = AddEmployeeDialog(parent_dialog)
            ed.setWindowTitle('Edit Employee')
            ed.set_data(emp)
            if ed.exec() == QDialog.DialogCode.Accepted:
                new_data = ed.get_data()
                phone_int = to_int_optional(new_data.get('phone_number', ''))
                ssn_int = to_int_optional(new_data.get('ssn', ''))
                upd = {
                    'name': new_data['name'],
                    'phone_number': phone_int,
                    'badge': str(new_data.get('badge', '')).strip(),
                    'pin_enabled': new_data['pin_enabled'],
                    'pin': new_data['pin'],
                    'department': new_data['department'],
                    'date_of_birth': new_data['date_of_birth'],
                    'hire_date': new_data['hire_date'],
                    'deactivated': new_data['deactivated'],
                    'ssn': ssn_int,
                    'period': new_data['period'],
                    'rate': new_data['rate'],
                }
                db_helpers.update_employee_by_badge(emp.badge, upd)
                try:
                    old_badge = emp.badge
                    new_badge = str(new_data.get('badge', '')).strip()
                    if old_badge != new_badge:
                        db_helpers.update_employee_badge_for_logs(old_badge, new_badge)
                except Exception:
                    pass
                QMessageBox.information(parent_dialog, 'Success', 'Employee updated.')
                load_employees(table)

        def delete_employee_row(badge, parent_dialog, table):
            if QMessageBox.question(parent_dialog, 'Confirm Delete', f'Delete employee {badge}? This is irreversible.') != QMessageBox.StandardButton.Yes:
                return
            db_helpers.delete_employee_by_badge(badge)
            QMessageBox.information(parent_dialog, 'Deleted', 'Employee deleted.')
            load_employees(table)

        dlg = QDialog(self)
        dlg.setWindowTitle('Employees')
        layout = QVBoxLayout(dlg)
        table = QTableWidget()
        # Prevent inline editing in the logs viewer; edits should go through dialogs/buttons
        try:
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        except Exception:
            # older PyQt versions may differ; fall back to clearing flags on individual items
            pass
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(['ID', 'Name', '', ''])
        table.horizontalHeader().setStretchLastSection(False)
        table.setColumnWidth(0, 20)
        table.setColumnWidth(1, 100)
        table.setColumnWidth(2, 40)
        table.setColumnWidth(3, 60)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton('Add Employee')
        close_btn = QPushButton('Close')
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        def _add_emp():
            ad = AddEmployeeDialog(dlg)
            if ad.exec() == QDialog.DialogCode.Accepted:
                data = ad.get_data()
                phone_int = to_int_optional(data.get('phone_number', ''))
                ssn_int = to_int_optional(data.get('ssn', ''))
                emp_data = {
                    'name': data['name'],
                    'phone_number': phone_int,
                    'badge': str(data.get('badge', '')).strip(),
                    'pin_enabled': data['pin_enabled'],
                    'pin': data['pin'],
                    'department': data['department'],
                    'date_of_birth': data['date_of_birth'],
                    'hire_date': data['hire_date'],
                    'deactivated': data['deactivated'],
                    'ssn': ssn_int,
                    'period': data['period'],
                    'rate': data['rate'],
                }
                try:
                    db_helpers.insert_employee(emp_data)
                    QMessageBox.information(dlg, 'Added', 'Employee added.')
                except ValueError as e:
                    QMessageBox.warning(dlg, 'Duplicate Badge', str(e))
                    return
                load_employees(table)

        add_btn.clicked.connect(_add_emp)
        close_btn.clicked.connect(dlg.accept)

        load_employees(table)
        dlg.exec()

    def view_time_logs(self):
        def load_logs(table: QTableWidget):
            rows = db_helpers.fetch_all_logs()
            table.blockSignals(True)
            table.setRowCount(len(rows))
            for r, lv in enumerate(rows):
                badge_item = QTableWidgetItem(str(lv.badge) if lv.badge is not None else '')
                badge_item.setFlags(badge_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                name_item = QTableWidgetItem(lv.name or '')
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                ci_item = QTableWidgetItem(lv.clock_in or '')
                co_item = QTableWidgetItem(lv.clock_out or '')
                ci_item.setFlags(ci_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                co_item.setFlags(co_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                badge_item.setData(Qt.ItemDataRole.UserRole, lv.id)
                table.setItem(r, 0, badge_item)
                table.setItem(r, 1, name_item)
                table.setItem(r, 2, ci_item)
                table.setItem(r, 3, co_item)
            table.blockSignals(False)

        def on_item_changed(item):
            try:
                col = item.column()
                if col not in (2, 3):
                    return
                row = item.row()
                lid_item = table.item(row, 0)
                if not lid_item:
                    return
                lid = int(lid_item.text())
                val = item.text().strip()
                if val:
                    from datetime import datetime as _dt
                    try:
                        _dt.strptime(val, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        item.setBackground(QBrush(QColor('#ffaaaa')))
                        return
                item.setBackground(QBrush())
                if col == 2:
                    db_helpers.update_log(lid, clock_in=(val if val else None))
                else:
                    db_helpers.update_log(lid, clock_out=(val if val else None))
            except Exception:
                pass

        def delete_log(lid, parent_dialog, table):
            if QMessageBox.question(parent_dialog, 'Confirm Delete', f'Delete log {lid}?') != QMessageBox.StandardButton.Yes:
                return
            db_helpers.delete_log_by_id(lid)
            load_logs(table)

        dlg = QDialog(self)
        dlg.setWindowTitle('Time Logs')
        dlg.setFixedWidth(400)
        layout = QVBoxLayout(dlg)
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(['ID', 'Name', 'Clock In', 'Clock Out', ''])
        table.setColumnWidth(0, 40)
        table.setColumnWidth(1, 80)
        table.setColumnWidth(2, 120)
        table.setColumnWidth(3, 120)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        export_btn = QPushButton('Export CSV')
        close_btn = QPushButton('Close')
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        def _export():
            path, _ = QFileDialog.getSaveFileName(dlg, 'Save CSV', str(Path(__file__).resolve() / 'timelogs.csv'), 'CSV Files (*.csv)')
            if not path:
                return
            rows = db_helpers.fetch_all_logs()
            import csv
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['log_id','badge','name','clock_in','clock_out'])
                w.writerows([(r.id, r.badge, r.name, r.clock_in, r.clock_out) for r in rows])
            QMessageBox.information(dlg, 'Exported', f'Exported {len(rows)} rows to {path}')

        export_btn.clicked.connect(_export)
        close_btn.clicked.connect(dlg.accept)

        load_logs(table)
        dlg.exec()

    def clock_in(self):
        badge = self.employee_input.text().strip()
        if not badge:
            self.employee_input.setStyleSheet('background-color: #ffcccc')
            QMessageBox.warning(self, 'Input Error', 'Please enter your badge number.')
            return
        else:
            self.employee_input.setStyleSheet('')
        emp = db_helpers.get_employee_by_badge(badge)
        if not emp:
            self.employee_input.setStyleSheet('background-color: #ffcccc')
            QMessageBox.warning(self, 'Not Found', f'No employee found with badge {badge}')
            return
        # Prevent multiple simultaneous clock-ins for the same badge
        try:
            if db_helpers.has_open_log(badge):
                QMessageBox.warning(self, 'Already Clocked In', 'This employee already has an open clock-in. Please clock out before clocking in again.')
                return
        except Exception:
            # If the helper fails for any reason, fall back to attempting insert (keeps prior behavior)
            QMessageBox.warning(self, 'Error Checking Open Logs', 'Please have a manager check the logs for this employee.')
            return
        emp_id = emp.id
        emp_name = emp.name
        dob = emp.date_of_birth
        hire_date = emp.hire_date
        pin_enabled = emp.pin_enabled
        pin = emp.pin
        if not pin_enabled:
            cancelled = False
            while True:
                new_pin, ok = QInputDialog.getText(self, 'Set PIN', f'Set a new PIN for {emp_name}:', QLineEdit.EchoMode.Password)
                if not ok or not new_pin.strip():
                    QMessageBox.warning(self, 'PIN Required', 'You must set a PIN to continue.')
                    cancelled = True
                    break
                confirm_pin, ok2 = QInputDialog.getText(self, 'Confirm PIN', 'Re-enter new PIN:', QLineEdit.EchoMode.Password)
                if not ok2 or new_pin != confirm_pin:
                    QMessageBox.warning(self, 'Mismatch', 'PINs do not match. Try again.')
                    continue
                break
            if not cancelled:
                db_helpers.update_employee_by_badge(emp.badge, {'pin': new_pin, 'pin_enabled': 1})
                pin = new_pin
                pin_enabled = 1
                QMessageBox.information(self, 'PIN Set', 'PIN has been set and enabled for this employee.')
            else:
                QMessageBox.information(self, 'PIN Set', 'Action cancelled.')
        if pin_enabled:
            entered_pin, ok = QInputDialog.getText(self, 'PIN Required', f'Enter PIN for {emp_name}:', QLineEdit.EchoMode.Password)
            if not ok or entered_pin.strip() != str(pin):
                QMessageBox.warning(self, 'PIN Error', 'Incorrect PIN. Clock-in aborted.')
                return
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db_helpers.insert_log(badge, now)
        today = datetime.now().date()
        birthday_popup = False
        anniversary_popup = False
        if dob:
            try:
                dob_dt = datetime.strptime(dob, '%Y-%m-%d').date()
                if dob_dt.month == today.month and dob_dt.day == today.day:
                    birthday_popup = True
            except Exception:
                pass
        if hire_date:
            try:
                hire_dt = datetime.strptime(hire_date, '%Y-%m-%d').date()
                if hire_dt.month == today.month and hire_dt.day == today.day:
                    anniversary_popup = True
            except Exception:
                pass
        self.status_label.setText(f'Status: {emp_name} clocked in.')
        self.employee_input.clear()
        if birthday_popup and anniversary_popup:
            QMessageBox.information(self, 'Special Day!', f"Happy Birthday and Happy Work Anniversary, {emp_name}!")
        elif birthday_popup:
            QMessageBox.information(self, 'Birthday', f"Happy Birthday, {emp_name}!")
        elif anniversary_popup:
            QMessageBox.information(self, 'Work Anniversary', f"Happy Work Anniversary, {emp_name}!")

    def clock_out(self):
        badge = self.employee_input.text().strip()
        if not badge:
            self.employee_input.setStyleSheet('background-color: #ffcccc')
            QMessageBox.warning(self, 'Input Error', 'Please enter your badge number.')
            return
        else:
            self.employee_input.setStyleSheet('')
        emp = db_helpers.get_employee_by_badge(badge)
        if not emp:
            self.employee_input.setStyleSheet('background-color: #ffcccc')
            QMessageBox.warning(self, 'Not Found', f'No employee found with badge {badge}')
            return
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        closed = db_helpers.close_most_recent_log(badge, now)
        if not closed:
            QMessageBox.warning(self, 'No Open Log', 'No open clock-in found for this employee.')
            return
        self.status_label.setText(f'Status: {badge} clocked out.')
        self.employee_input.clear()

    def generate_report(self):
        report_types = ['Daily', 'Weekly', 'Monthly', 'Yearly', 'Custom']
        report_type, ok = QInputDialog.getItem(self, 'Generate Report', 'Select report type:', report_types, 0, False)
        if not ok:
            return
        badge, ok = QInputDialog.getText(self, 'Select Employee', 'Please enter Employee badge:')
        if not ok or not badge.strip():
            return
        badge = badge.strip()
        today = date.today()
        if report_type == 'Daily':
            start_date = end_date = today.strftime('%Y-%m-%d')
        elif report_type == 'Weekly':
            start_date = (today - timedelta(days=6)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        elif report_type == 'Monthly':
            start_date = (today - timedelta(days=27)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        elif report_type == 'Yearly':
            start_date = date(today.year, 1, 1).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        else:
            dr_dialog = DateRangeDialog(self)
            if dr_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            start_date, end_date = dr_dialog.get_dates()
        emp = db_helpers.get_employee_by_badge(badge)
        if not emp:
            QMessageBox.warning(self, 'Not Found', f'No employee found with badge {badge}')
            return
        emp_name = emp.name
        rate = emp.rate
        period = emp.period
        overtime_multiplier = 1.5
        logs_objs = db_helpers.fetch_logs_for_range(badge, start_date, end_date)
        from collections import defaultdict
        from datetime import datetime as dt
        week_hours = defaultdict(float)
        for log in logs_objs:
            clock_in = log.clock_in
            clock_out = log.clock_out
            if clock_in and clock_out:
                try:
                    t1 = dt.strptime(clock_in, '%Y-%m-%d %H:%M:%S')
                    t2 = dt.strptime(clock_out, '%Y-%m-%d %H:%M:%S')
                    hours = (t2 - t1).total_seconds() / 3600.0
                    year, week, _ = t1.isocalendar()
                    week_hours[(year, week)] += hours
                except Exception:
                    continue
        total_regular = 0.0
        total_overtime = 0.0
        for (year, week), hours in week_hours.items():
            if hours > 40:
                total_regular += 40
                total_overtime += hours - 40
            else:
                total_regular += hours
        total_hours = total_regular + total_overtime
        try:
            rate = float(rate)
            overtime_multiplier = float(overtime_multiplier)
        except Exception:
            rate = 0.0
            overtime_multiplier = 1.5
        if period == 'monthly':
            if report_type in ['Daily', 'Weekly']:
                gross_pay = rate / (28 if report_type == 'Daily' else 4)
            elif report_type == 'Yearly': gross_pay = rate * 13
            else: gross_pay = rate
        else: gross_pay = total_regular * rate
        overtime_pay = total_overtime * rate * overtime_multiplier
        total_pay = (gross_pay + overtime_pay) if period == 'hourly' else gross_pay
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            QMessageBox.warning(self, 'Missing Dependency', 'Please install reportlab: pip install reportlab')
            return
        base_dir = Path(get_setting('report_save_path', str(Path(__file__).resolve() / 'reports')))
        if not base_dir:
            base_dir = Path(__file__).resolve() / 'reports'
        emp_folder = base_dir / str(emp.badge)
        emp_folder.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        filename = emp_folder / f"paystub_{emp.badge}_{report_type}_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
        lines = [
            ('center', 'SCR Studio Paystub'),
            ('left', f'Report Type: {report_type}'),
            ('left', f'Date: {now.strftime("%Y-%m-%d")}'),
            ('left', f'Employee: {emp_name} (Badge: {emp.badge})')
        ]
        if report_type != 'Daily':
            lines.append(('left', f'Period: {start_date} to {end_date}'))
        lines.append(('left', f'Hours Worked: {total_hours:.2f}'))
        lines.append(('left', f'Rate: ${rate:.2f}/{"hr" if period == "hourly" else "mo"}'))
        lines.append(('left', f'Gross Pay: ${gross_pay:.2f}'))
        if total_overtime > 0 and period == 'hourly':
            lines.append(('left', f'Overtime: {total_overtime:.2f} hrs @ ${rate * overtime_multiplier:.2f}/hr'))
            lines.append(('left', f'Overtime Pay: ${overtime_pay:.2f}'))
        lines.append(('left', f'Total Pay: ${total_pay:.2f}'))
        lines.append(('left', 'Thank you!'))
        line_height = 20
        total_height = 30
        for _, text in lines:
            total_height += line_height
            if text.startswith('Date:'):
                total_height += 10
            if text.startswith('Total Pay:'):
                total_height += 20
        receipt_size = (216, total_height)
        try:
            generate_paystub_pdf(filename, lines, receipt_size)
        except Exception as e:
            QMessageBox.warning(self, 'PDF Error', f'Could not create PDF: {e}')
            return
        pdf_path = str(filename)
        try:
            from PyQt6.QtPdf import QPdfDocument
            from PyQt6.QtPdfWidgets import QPdfView
            class PdfDialog(QDialog):
                def __init__(self, pdf_path, pdf_height, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle('Paystub Preview')
                    h = max(400, min(pdf_height, 800))
                    self.resize(360, h)
                    layout = QVBoxLayout(self)
                    self.pdf_view = QPdfView(parent)
                    self.pdf_doc = QPdfDocument(parent)
                    self.pdf_doc.load(pdf_path)
                    self.pdf_view.setDocument(self.pdf_doc)
                    layout.addWidget(self.pdf_view)
                    # Button row: Print, Open File, Close
                    btn_row = QHBoxLayout()
                    print_btn = QPushButton('Print')
                    open_btn = QPushButton('Open File')
                    close_btn = QPushButton('Close')
                    btn_row.addWidget(print_btn)
                    btn_row.addWidget(open_btn)
                    btn_row.addStretch()
                    btn_row.addWidget(close_btn)
                    layout.addLayout(btn_row)

                    # Handlers use OS-level open/print where available
                    def _do_print():
                        try:
                            # Use Qt's print dialog for consistent, user-driven printing
                            from PyQt6.QtGui import QPainter
                            from PyQt6.QtPrintSupport import (QPrintDialog,
                                                              QPrinter)
                            printer = QPrinter()
                            dlg = QPrintDialog(printer, self)
                            if dlg.exec() == QDialog.DialogCode.Accepted:
                                painter = QPainter()
                                if not painter.begin(printer):
                                    raise RuntimeError('Could not begin QPainter on printer')
                                # Render the PDF view widget onto the printer device
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
                            p = str(pdf_path)
                            # Reveal in file manager: select on Windows/Finder, open folder on Linux
                            if sys.platform.startswith('win'):
                                # explorer /select,"path"
                                subprocess.run(['explorer', '/select,', p])
                            elif sys.platform == 'darwin':
                                subprocess.run(['open', '-R', p])
                            else:
                                # On Linux open the containing folder
                                subprocess.run(['xdg-open', os.path.dirname(p)])
                        except Exception as e:
                            QMessageBox.warning(self, 'Open Error', f'Could not reveal file: {e}')

                    print_btn.clicked.connect(_do_print)
                    open_btn.clicked.connect(_open_file)
                    close_btn.clicked.connect(self.accept)
            dlg = PdfDialog(pdf_path, round(receipt_size[1]*1.5), self)
            dlg.exec()
        except Exception as e:
            import os
            import traceback
            import webbrowser
            print("[PDF VIEWER ERROR]", e)
            print(traceback.format_exc())
            try:
                webbrowser.open_new(pdf_path)
            except Exception as e2:
                print("[BROWSER ERROR]", e2)
                try:
                    os.startfile(pdf_path)
                except Exception as e3:
                    print("[STARTFILE ERROR]", e3)
                    QMessageBox.warning(self, 'Open PDF', f'Could not open PDF automatically. Please open manually: {pdf_path}\nError: {e}')

    def handle_ntp_time_updated(self, timestr: str):
        try:
            try:
                parsed = datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S")
            except Exception:
                parsed = datetime.now()
            self.last_ntp_dt = parsed
            self.last_ntp_wall = time.time()
        except Exception:
            pass
        try:
            server = getattr(self, 'ntp_server', '')
            short_server = server if len(server) <= 30 else server[:27] + '...'
            if self.show_ntp_status:
                self.ntp_status_label.setText(f"{short_server} • {timestr}")
                self.ntp_status_label.setToolTip(f"Server: {server}\nLast Sync: {timestr}")
            try:
                if hasattr(self, 'fetch_btn'):
                    self.fetch_btn.setEnabled(True)
            except Exception:
                pass
        except Exception:
            pass

    def handle_ntp_error(self, msg: str):
        try:
            self.ntp_time_label.setText('NTP Time: Error')
        except Exception:
            pass
        try:
            server = getattr(self, 'ntp_server', '')
            short_server = server if len(server) <= 30 else server[:27] + '...'
            if self.show_ntp_status:
                self.ntp_status_label.setText(f"{short_server} • Error")
                self.ntp_status_label.setToolTip(f"Server: {server}\nLast Sync: Error")
            try:
                if hasattr(self, 'fetch_btn'):
                    self.fetch_btn.setEnabled(True)
            except Exception:
                pass
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            if hasattr(self, 'ntp_worker') and hasattr(self, 'ntp_thread'):
                self.ntp_worker.running = False
                self.ntp_thread.quit()
                self.ntp_thread.wait(5000)
        except Exception:
            pass
        super().closeEvent(event)

    def fetch_now(self):
        try:
            if hasattr(self, 'fetch_btn'):
                self.fetch_btn.setEnabled(False)
            if hasattr(self, 'ntp_worker'):
                self.ntp_worker.server_changed.emit(self.ntp_server)
            try:
                if self.show_ntp_status:
                    server = getattr(self, 'ntp_server', '')
                    short_server = server if len(server) <= 30 else server[:27] + '...'
                    self.ntp_status_label.setText(f"{short_server} • ...")
                    self.ntp_status_label.setToolTip(f"Server: {server}\nLast Sync: Pending")
            except Exception:
                pass
        except Exception:
            pass


def run_app():
    app = QApplication(sys.argv)
    window = TimeClockApp()
    window.show()
    sys.exit(app.exec())
