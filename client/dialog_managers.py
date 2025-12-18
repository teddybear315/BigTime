"""
Complex Dialog Managers for BigTime Client
This module contains dialog managers that handle complex UI interactions
previously embedded in the main GUI application.
"""

from datetime import datetime

from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from ui.dialogs.shared import DateRangeDialog
from ui.dialogs.client import EmployeeListDialog
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
        dlg = EmployeeListDialog(client, parent, data_changed_callback)
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
        from datetime import date, datetime as dt, timedelta
        from pathlib import Path

        from PyQt6.QtWidgets import QInputDialog

        from shared.utils import get_data_path
        from ui.pdf_utils import generate_paystub_pdf

        # Get report type from user
        report_types = ['Daily', 'Weekly', 'Monthly', 'Yearly', 'Custom']
        report_type, ok = QInputDialog.getItem(
            parent, 'Generate Report', 'Select report type:', report_types, 0, False
        )
        if not ok:
            return

        # Get employee badge from user
        badge, ok = QInputDialog.getText(parent, 'Select Employee', 'Please enter Employee badge:')
        if not ok or not badge.strip():
            return
        badge = badge.strip()

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
            start_date = date(today.year, 1, 1).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        else:  # Custom
            dlg = DateRangeDialog(parent)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            start_date, end_date = dlg.get_dates()

        try:
            # Get employee details
            employee = client.get_employee_by_badge(badge)
            if not employee:
                QMessageBox.warning(parent, 'Not Found', f'No employee found with badge {badge}')
                return

            emp_name = employee.name
            rate = employee.rate
            period = employee.period
            overtime_multiplier = 1.5

            # Get logs for the date range
            all_logs = client.get_all_time_logs()
            logs_for_period = []

            for log in all_logs:
                if log.badge == badge and log.clock_in:
                    try:
                        log_date = dt.fromisoformat(log.clock_in.replace('Z', '+00:00')).date()
                        start_date_obj = dt.strptime(start_date, '%Y-%m-%d').date()
                        end_date_obj = dt.strptime(end_date, '%Y-%m-%d').date()
                        if start_date_obj <= log_date <= end_date_obj:
                            logs_for_period.append(log)
                    except:
                        continue

            if not logs_for_period:
                QMessageBox.information(parent, 'No Data',
                                      f'No time logs found for employee {badge} in the selected period ({start_date} to {end_date})')
                return

            # Calculate hours worked
            week_hours = defaultdict(float)
            for log in logs_for_period:
                clock_in = log.clock_in
                clock_out = log.clock_out

                if clock_in and clock_out:
                    try:
                        t1 = dt.strptime(clock_in, '%Y-%m-%d %H:%M:%S')
                        t2 = dt.strptime(clock_out, '%Y-%m-%d %H:%M:%S')
                        hours = (t2 - t1).total_seconds() / 3600.0
                        year, week, _ = t1.isocalendar()
                        week_hours[(year, week)] += hours
                    except:
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

            # Calculate pay
            try:
                rate = float(rate)
                overtime_multiplier = float(overtime_multiplier)
            except:
                rate = 0.0
                overtime_multiplier = 1.5

            if period == 'monthly':
                if report_type in ['Daily', 'Weekly']:
                    gross_pay = rate / (28 if report_type == 'Daily' else 4)
                elif report_type == 'Yearly':
                    gross_pay = rate * 13
                else:
                    gross_pay = rate
            else:
                gross_pay = total_regular * rate

            overtime_pay = total_overtime * rate * overtime_multiplier
            total_pay = (gross_pay + overtime_pay) if period == 'hourly' else gross_pay

            # Build report lines
            now = dt.now()
            lines = [
                ('center', 'SCR Studio Paystub'),
                ('left', f'Report Type: {report_type}'),
                ('left', f'Date: {now.strftime("%Y-%m-%d")}'),
                ('left', f'Employee: {emp_name} (Badge: {badge})')
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

            # Calculate PDF size
            line_height = 20
            total_height = 30
            for _, text in lines:
                total_height += line_height
                if text.startswith('Date:'):
                    total_height += 10
                if text.startswith('Total Pay:'):
                    total_height += 20

            receipt_size = (216, total_height)

            # Create output directory
            base_dir = Path(client.get_setting('report_save_path', str(get_data_path("reports"))))
            if not base_dir:
                base_dir = Path(__file__).resolve().parent.parent / 'reports'

            emp_folder = base_dir / str(badge)
            emp_folder.mkdir(parents=True, exist_ok=True)

            # Generate PDF
            filename = emp_folder / f"paystub_{badge}_{report_type}_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
            generate_paystub_pdf(filename, lines, receipt_size)

            # Display PDF preview
            pdf_path = str(filename)
            try:
                from PyQt6.QtPdf import QPdfDocument
                from PyQt6.QtPdfWidgets import QPdfView

                class PdfDialog(QDialog):
                    """Dialog for displaying and interacting with PDF documents."""

                    def __init__(self, pdf_path: str, pdf_height: int, parent=None):
                        """
                        Initialize the PDF preview dialog.

                        Args:
                            pdf_path: Path to the PDF file
                            pdf_height: Height of the PDF for sizing the dialog
                            parent: Parent widget
                        """
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
                                from PyQt6.QtGui import QPainter
                                from PyQt6.QtPrintSupport import (
                                    QPrintDialog,
                                    QPrinter,
                                )

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
                                import sys

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

                dlg = PdfDialog(pdf_path, round(receipt_size[1] * 1.5), parent)
                dlg.exec()

            except Exception as e:
                import os
                import subprocess
                import sys
                import traceback

                print("[PDF VIEWER ERROR]", e)
                print(traceback.format_exc())

                try:
                    import webbrowser
                    webbrowser.open_new(pdf_path)
                except Exception as e2:
                    print("[BROWSER ERROR]", e2)
                    try:
                        os.startfile(pdf_path)
                    except Exception as e3:
                        print("[STARTFILE ERROR]", e3)
                        QMessageBox.warning(parent, 'Open PDF', f'Could not open PDF automatically. Please open manually: {pdf_path}\nError: {e}')

        except Exception as e:
            import traceback
            QMessageBox.critical(parent, 'Report Error', f'Failed to generate report: {str(e)}\n{traceback.format_exc()}')
