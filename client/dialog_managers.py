"""
Complex Dialog Managers for BigTime Client
This module contains dialog managers that handle complex UI interactions
previously embedded in the main GUI application.
"""

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel,
                             QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from shared.models import Employee
from ui.dialogs import DateRangeDialog, EditEmployeeDialog
from ui.fonts import fonts


class EmployeeListManager:
    """Manager for the employee list dialog and operations."""

    @staticmethod
    def show_employee_list(parent, client, data_changed_callback=None):
        """
        Show the employee list dialog with edit/remove functionality.

        Args:
            parent: Parent widget for the dialog
            client: BigTime client instance for data operations
            data_changed_callback: Optional callback to call when employee data changes
        """
        # Create employee list dialog
        dlg = QDialog(parent)
        dlg.setWindowTitle('Employee Management')
        dlg.setMinimumSize(300, 400)
        # dlg.resize(600, 500)

        layout = QVBoxLayout(dlg)

        # Create table
        table = QTableWidget()
        table.setColumnCount(2)  # Badge, Name only (no buttons in table)
        table.setHorizontalHeaderLabels(['Badge', 'Name'])

        # Set column widths and make table selectable like API key window
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Make rows selectable and non-editable
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(200)

        def load_employees(table: QTableWidget):
            """Load/reload employees into the table"""
            employees = client.get_all_employees()
            table.setRowCount(len(employees))

            for row, emp in enumerate(employees):
                badge_val = emp.badge
                name = emp.name

                # Badge column
                badge_item = QTableWidgetItem(str(badge_val))
                badge_item.setFlags(badge_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                # Store employee data for later retrieval
                badge_item.setData(Qt.ItemDataRole.UserRole, emp)
                table.setItem(row, 0, badge_item)

                # Name column
                name_item = QTableWidgetItem(name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, 1, name_item)

        def get_selected_employee(table: QTableWidget) -> Employee:
            """Get the currently selected employee from the table"""
            current_row = table.currentRow()
            if current_row >= 0:
                badge_item = table.item(current_row, 0)
                if badge_item:
                    return badge_item.data(Qt.ItemDataRole.UserRole)
            return None

        def edit_selected_employee():
            """Edit the selected employee and refresh table"""
            employee = get_selected_employee(table)
            if not employee:
                QMessageBox.warning(dlg, 'No Selection', 'Please select an employee to edit.')
                return

            dlg_edit = EditEmployeeDialog(employee, dlg)
            if dlg_edit.exec() == QDialog.DialogCode.Accepted:
                updated_employee = dlg_edit.get_employee()
                try:
                    # Check if badge is changing for special handling
                    badge_changed = employee.badge != updated_employee.badge

                    if badge_changed:
                        # For badge changes, we need to handle it carefully
                        success = client.update_employee_badge(employee.badge, updated_employee.to_dict())
                        if success:
                            QMessageBox.information(dlg, 'Success',
                                                  f'Employee {updated_employee.name} updated successfully.')
                            # Trigger sync for updated employee data
                            if data_changed_callback:
                                data_changed_callback()
                        else:
                            QMessageBox.warning(dlg, 'Update Failed',
                                              'Failed to update employee badge. Badge may already exist.')
                            return
                    else:
                        # Normal update
                        success = client.update_employee(updated_employee)
                        if success:
                            QMessageBox.information(dlg, 'Success',
                                                  f'Employee {updated_employee.name} updated successfully.')
                        else:
                            QMessageBox.warning(dlg, 'Update Failed', 'Failed to update employee.')
                            return

                    load_employees(table)  # Refresh the table

                except Exception as e:
                    QMessageBox.critical(dlg, 'Error', f'Failed to update employee: {str(e)}')

        def delete_selected_employee():
            """Delete the selected employee after confirmation"""
            employee = get_selected_employee(table)
            if not employee:
                QMessageBox.warning(dlg, 'No Selection', 'Please select an employee to remove.')
                return

            reply = QMessageBox.question(
                dlg, 'Confirm Removal',
                f'Are you sure you want to remove {employee.name}?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    success = client.delete_employee(employee.badge)
                    if success:
                        QMessageBox.information(dlg, 'Success',
                                              f'Employee {employee.name} removed successfully.')
                        # Trigger sync for deleted employee data
                        if data_changed_callback:
                            data_changed_callback()
                        load_employees(table)  # Refresh the table
                    else:
                        QMessageBox.warning(dlg, 'Removal Failed', 'Failed to remove employee.')
                except Exception as e:
                    QMessageBox.critical(dlg, 'Error', f'Failed to remove employee: {str(e)}')        # Load initial data
        load_employees(table)

        # Enable double-click to edit
        table.itemDoubleClicked.connect(lambda: edit_selected_employee())

        layout.addWidget(table)

        # Employee controls (like API key controls)
        employee_controls = QHBoxLayout()
        edit_btn = QPushButton("Edit Selected")
        remove_btn = QPushButton("Remove Selected")
        refresh_btn = QPushButton("Refresh")
        close_btn = QPushButton('Close')

        # Style the remove button
        remove_btn.setStyleSheet('QPushButton { background-color: #ff6b6b; color: white; }')

        # Connect button actions
        edit_btn.clicked.connect(edit_selected_employee)
        remove_btn.clicked.connect(delete_selected_employee)
        refresh_btn.clicked.connect(lambda: [
            data_changed_callback() if data_changed_callback else None,
            load_employees(table)
        ])
        close_btn.clicked.connect(dlg.accept)

        employee_controls.addWidget(edit_btn)
        employee_controls.addWidget(remove_btn)
        employee_controls.addStretch()
        employee_controls.addWidget(refresh_btn)
        employee_controls.addWidget(close_btn)
        layout.addLayout(employee_controls)

        dlg.exec()


class TimeLogsManager:
    """Manager for time logs viewing dialog."""

    @staticmethod
    def show_time_logs(parent, client):
        """
        Show time logs dialog with date range selection.

        Args:
            parent: Parent widget for the dialog
            client: BigTime client instance for data operations
        """
        dlg = DateRangeDialog(parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            start_date, end_date = dlg.get_dates()

            try:
                # Get logs for the selected date range
                logs = []
                all_logs = client.get_all_time_logs()

                # Filter logs by date range if we have logs
                for log in all_logs:
                    if log.clock_in:
                        # Parse the date from clock_in timestamp
                        try:
                            log_date = datetime.fromisoformat(log.clock_in.replace('Z', '+00:00')).date()
                            if start_date <= log_date <= end_date:
                                logs.append(log)
                        except:
                            # If we can't parse the date, include it anyway
                            logs.append(log)

                if not logs:
                    QMessageBox.information(parent, 'Time Logs',
                                          f'No logs found from {start_date} to {end_date}')
                    return

                # Create and show logs dialog
                logs_dialog = QDialog(parent)
                logs_dialog.setWindowTitle(f'Time Logs ({start_date} to {end_date})')
                logs_dialog.setFixedWidth(400)

                layout = QVBoxLayout(logs_dialog)

                title = QLabel('Time Log Viewer')
                title.setFont(fonts["header"])
                sub_title = QLabel(f'Time Logs from {start_date} to {end_date}')
                sub_title.setFont(fonts["small"])
                layout.addWidget(title)
                layout.addWidget(sub_title)

                # Create table
                table = QTableWidget()
                table.setColumnCount(4)
                table.setHorizontalHeaderLabels(['ID', 'Name', 'Clock In', 'Clock Out'])
                table.setRowCount(len(logs))
                table.setColumnWidth(0, 40)
                table.setColumnWidth(1, 80)
                table.setColumnWidth(2, 120)
                table.setColumnWidth(3, 120)

                for row, log in enumerate(logs):
                    # ID
                    table.setItem(row, 0, QTableWidgetItem(log.badge))

                    # Name (Badge)
                    employee = client.get_employee_by_badge(log.badge)
                    name = employee.name if employee else log.badge
                    table.setItem(row, 1, QTableWidgetItem(name))

                    # Clock In
                    clock_in_text = log.clock_in if log.clock_in else 'N/A'
                    table.setItem(row, 2, QTableWidgetItem(clock_in_text))

                    # Clock Out
                    clock_out_text = log.clock_out if log.clock_out else 'Still clocked in'
                    table.setItem(row, 3, QTableWidgetItem(clock_out_text))

                # Make table read-only
                table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

                layout.addWidget(table)

                # Close button
                close_btn = QPushButton('Close')
                close_btn.clicked.connect(logs_dialog.accept)
                layout.addWidget(close_btn)

                logs_dialog.exec()

            except Exception as e:
                QMessageBox.critical(parent, 'Error', f'Failed to retrieve logs: {str(e)}')


class ReportManager:
    """Manager for report generation dialogs."""

    @staticmethod
    def generate_report(parent, client):
        """
        Handle report generation with user input dialogs.

        Args:
            parent: Parent widget for dialogs
            client: BigTime client instance for data operations
        """
        from collections import defaultdict
        from datetime import date, timedelta

        from PyQt6.QtWidgets import QInputDialog

        from ui.pdf_utils import generate_paystub_pdf

        # Get report type from user
        report_types = ['Daily', 'Weekly', 'Monthly', 'Yearly', 'Custom']
        report_type, ok = QInputDialog.getItem(
            parent, 'Generate Report', 'Select report type:', report_types, 0, False
        )
        if not ok:
            return

        # Determine date range based on report type
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
            start_date = (today - timedelta(days=364)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        else:  # Custom
            from ui.dialogs import DateRangeDialog
            dlg = DateRangeDialog(parent)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            start_date, end_date = dlg.get_dates()
            start_date = start_date.strftime('%Y-%m-%d')
            end_date = end_date.strftime('%Y-%m-%d')

        try:
            # Get all employees and their logs for the date range
            employees = client.get_all_employees()
            all_logs = client.get_all_time_logs()

            # Group logs by employee
            employee_logs = defaultdict(list)
            for log in all_logs:
                if log.clock_in:
                    try:
                        log_date = datetime.fromisoformat(log.clock_in.replace('Z', '+00:00')).date()
                        if datetime.strptime(start_date, '%Y-%m-%d').date() <= log_date <= datetime.strptime(end_date, '%Y-%m-%d').date():
                            employee_logs[log.badge].append(log)
                    except:
                        continue

            if not employee_logs:
                QMessageBox.information(parent, 'No Data',
                                      f'No time logs found for the selected period ({start_date} to {end_date})')
                return

            # Generate report for each employee
            from shared.utils import get_data_path
            report_path = client.get_setting('report_save_path', str(get_data_path("reports")))

            for employee in employees:
                if employee.badge in employee_logs:
                    logs = employee_logs[employee.badge]

                    # Calculate totals
                    total_hours = 0
                    for log in logs:
                        if log.clock_in and log.clock_out:
                            try:
                                clock_in_time = datetime.fromisoformat(log.clock_in.replace('Z', '+00:00'))
                                clock_out_time = datetime.fromisoformat(log.clock_out.replace('Z', '+00:00'))
                                duration = (clock_out_time - clock_in_time).total_seconds() / 3600
                                total_hours += duration
                            except:
                                continue

                    # Generate PDF
                    generate_paystub_pdf(
                        employee=employee,
                        logs=logs,
                        start_date=start_date,
                        end_date=end_date,
                        total_hours=total_hours,
                        save_path=report_path
                    )

            QMessageBox.information(parent, 'Report Generated',
                                  f'{report_type} report generated successfully for {len(employee_logs)} employees.\n'
                                  f'Reports saved to: {report_path}')

        except Exception as e:
            QMessageBox.critical(parent, 'Report Error', f'Failed to generate report: {str(e)}')
