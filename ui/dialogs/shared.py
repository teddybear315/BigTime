"""Shared dialog classes used by both client and server.

This module contains dialog classes that are utilized by multiple
parts of the application (client and/or server).
"""
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                             QFormLayout, QGroupBox, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QVBoxLayout)

from shared.utils import create_app_icon
from ui.fonts import fonts

__all__ = [
    'set_dialog_icon',
    'DateRangeDialog',
    'DatabaseSelectDialog'
]


def set_dialog_icon(dialog: QDialog) -> None:
    """Set the application icon on a dialog.

    Args:
        dialog: The dialog to set the icon for
    """
    dialog.setWindowIcon(create_app_icon())


class DateRangeDialog(QDialog):
    """Dialog for selecting a date range for reports.

    Allows user to select start and end dates with calendar popups
    for generating time reports over a specific period.
    """

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the date range dialog.

        Args:
            parent: Parent widget for modal presentation
        """
        super().__init__(parent)
        self.setWindowTitle('Select Date Range')

        layout = QVBoxLayout(self)

        info_label = QLabel('Choose the date range for your report:')
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Date Selection Group
        date_group = QGroupBox("Date Range")
        date_layout = QFormLayout(date_group)

        from PyQt6.QtWidgets import QDateEdit
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

    def get_dates(self) -> Tuple[str, str]:
        """Get the selected date range.

        Returns:
            Tuple of (start_date, end_date) as MM-dd-yyyy strings
        """
        return self.start_date.date().toString('MM-dd-yyyy'), self.end_date.date().toString('MM-dd-yyyy')


class DatabaseSelectDialog(QDialog):
    """Dialog for selecting a database file for migration or restoration.

    Allows user to select a database file to migrate/restore and provides
    confirmation before proceeding with the operation.
    """

    def __init__(
        self,
        parent: Optional[QDialog] = None,
        default_filename: str = 'server_bigtime.db',
        restore: bool = False,
        migrate: bool = False
    ) -> None:
        """Initialize the database selection dialog.

        Args:
            parent: Parent widget for modal presentation
            default_filename: Default filename to search for (e.g., 'server_bigtime.db')
            restore: If True, dialog is for restore operation
            migrate: If True, dialog is for migration operation
        """
        super().__init__(parent)
        self.restore = restore
        self.migrate = migrate
        if restore:
            self.setWindowTitle('Restore Database')
        elif migrate:
            self.setWindowTitle('Migrate Database')
        else:
            self.setWindowTitle('Select Database')
        self.setWindowIcon(create_app_icon())
        self.setMinimumWidth(500)
        self.default_filename = default_filename
        self.selected_file: Optional[str] = None

        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            f'Select a {default_filename} file to complete this action.\n\n'
            'A backup will be created before it begins.'
        )
        instructions.setFont(fonts['default'])
        layout.addWidget(instructions)

        # File selection group
        file_group = QGroupBox('Database File')
        file_layout = QVBoxLayout(file_group)

        self.file_input = QLineEdit()
        self.file_input.setReadOnly(True)
        self.file_input.setPlaceholderText('No file selected')
        file_layout.addWidget(self.file_input)

        browse_btn = QPushButton('Browse...')
        browse_btn.clicked.connect(self.browse_for_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.handle_confirmation)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Try to auto-populate with default file if it exists
        self._try_auto_populate_default_file()

    def browse_for_file(self) -> None:
        """Open file browser to select database file."""
        import os

        # Try to find the default file first
        initial_dir = ''
        default_file = self.default_filename

        # Look for the file in common locations
        search_paths = [
            os.getcwd(),  # Current working directory
            str(Path.cwd().parent),  # Parent of current directory
            str(Path(__file__).parent.parent.parent),  # Project root
        ]

        for search_path in search_paths:
            potential_file = os.path.join(search_path, default_file)
            if os.path.exists(potential_file):
                initial_dir = search_path
                break

        # If not found, use the current directory
        if not initial_dir:
            initial_dir = os.getcwd()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            'Select Database File',
            initial_dir,
            'SQLite Database Files (*.db);;All Files (*)'
        )

        if file_path:
            self.selected_file = file_path
            # Show just the filename in the input, but store full path
            self.file_input.setText(str(Path(file_path).name))
            self.file_input.setToolTip(file_path)

    def handle_confirmation(self) -> None:
        """Show confirmation dialog before accepting operation."""
        if not self.selected_file:
            QMessageBox.warning(self, 'No File Selected', 'Please select a database file.')
            return
        if self.migrate:
            reply = QMessageBox.question(
                self,
                'Confirm Migration',
                f'Migrate the selected database?\n\n'
                f'File: {self.file_input.text()}\n\n'
                'A backup will be created before migration begins.\n'
                'All existing data will be preserved.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                super().accept()
        elif self.restore:
            reply = QMessageBox.question(
                self,
                'Confirm Restore',
                f'Restore the selected database?\n\n'
                f'File: {self.file_input.text()}\n\n'
                'A backup will be created before restoration begins.\n'
                'All existing data will be preserved.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                super().accept()
        else:
            super().accept()

    def _try_auto_populate_default_file(self) -> None:
        """Try to find and auto-populate the default database file."""
        import os

        # Search paths in order of likelihood
        search_paths = [
            os.getcwd(),  # Current working directory
            str(Path(__file__).parent.parent.parent),  # Project root
            str(Path.home()),  # User home directory
        ]

        for search_path in search_paths:
            potential_file = os.path.join(search_path, self.default_filename)
            if os.path.exists(potential_file):
                self.selected_file = potential_file
                self.file_input.setText(self.default_filename)
                self.file_input.setToolTip(potential_file)
                return

    def get_file_path(self) -> str:
        """Get the selected file path.

        Returns:
            Full path to the selected database file
        """
        return self.selected_file or ''
