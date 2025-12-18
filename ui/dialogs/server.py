"""Server-specific dialog classes.

This module contains dialog classes used primarily by the BigTime server
application for configuration, setup, and management.
"""

from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                             QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPushButton, QSpinBox,
                             QTableWidget, QTableWidgetItem, QTextEdit,
                             QVBoxLayout)

import shared
from shared.utils import create_app_icon
from ui.fonts import fonts

__all__ = [
    'set_dialog_icon',
    'OOTBDialog',
    'ConfigDialog'
]


def set_dialog_icon(dialog: QDialog) -> None:
    """Set the application icon on a dialog.

    Args:
        dialog: The dialog to set the icon for
    """
    dialog.setWindowIcon(create_app_icon())


class OOTBDialog(QDialog):
    """Out-of-the-box setup dialog for BigTime server.

    Guides initial server configuration including company name,
    network settings, and database restoration options.
    """

    def __init__(
        self,
        parent: Optional[QDialog] = None,
        company_name: str = 'BigTime',
        host: str = '127.0.0.1',
        port: int = 5000
    ) -> None:
        """Initialize the server setup dialog.

        Args:
            parent: Parent widget for modal presentation
            company_name: Default company name
            host: Default host address
            port: Default port number
        """
        super().__init__(parent)
        self.setWindowTitle('BigTime Server Setup')
        set_dialog_icon(self)

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

        self.port_spin = QLineEdit(str(port))
        self.port_spin.setPlaceholderText("1024-65535")
        self.port_spin.setMaximumWidth(150)
        # Only allow digits
        port_validator = QRegularExpressionValidator(QRegularExpression(r"^\d{0,5}$"), self.port_spin)
        self.port_spin.setValidator(port_validator)
        server_layout.addRow("Port:", self.port_spin)

        layout.addWidget(server_group)

        # Auto-start option
        autostart_group = QGroupBox("Startup Options")
        autostart_layout = QVBoxLayout(autostart_group)

        self.autostart_check = QCheckBox("Start server automatically when tray application launches")
        self.autostart_check.setChecked(True)
        autostart_layout.addWidget(self.autostart_check)

        layout.addWidget(autostart_group)

        layout.addSpacing(10)

        # Restore from backup option
        restore_group = QGroupBox("Restore Option")
        restore_layout = QVBoxLayout(restore_group)

        restore_info = QLabel("If you have existing backups, you can restore from the most recent backup:")
        restore_info.setWordWrap(True)
        restore_info.setFont(fonts["small"])
        restore_layout.addWidget(restore_info)

        self.restore_btn = QPushButton("Restore from Last Backup")
        self.restore_btn.clicked.connect(self.restore_from_backup)
        restore_layout.addWidget(self.restore_btn)

        layout.addWidget(restore_group)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def restore_from_backup(self) -> None:
        """Restore database from the most recent backup."""
        from shared.backup_utils import get_latest_backup_info, restore_from_backup as restore_db

        # Get the latest backup
        backup_info = get_latest_backup_info('server_bigtime.db')

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
            restore_db(backup_path, 'server_bigtime.db')
            QMessageBox.information(
                self,
                'Restore Complete',
                'Database has been restored from backup.\n\nPlease restart the server for changes to take effect.'
            )
        except Exception as e:
            QMessageBox.critical(self, 'Restore Failed', f'Could not restore database: {e}')

    def get_values(self) -> Dict[str, Any]:
        """Get the configuration values.

        Returns:
            Dictionary with keys: company_name, host, port, autostart
        """
        port_text = self.port_spin.text().strip()
        try:
            port = int(port_text) if port_text else 5000
        except ValueError:
            port = 5000
        return {
            'company_name': self.company_edit.text().strip(),
            'host': self.host_edit.text().strip(),
            'port': port,
            'autostart': self.autostart_check.isChecked()
        }


class ConfigDialog(QDialog):
    """Enhanced server configuration dialog with API key management.

    Provides settings for host/port configuration, API key generation/revocation,
    and server information display.
    """

    def __init__(
        self,
        parent: Optional[QDialog] = None,
        host: str = '127.0.0.1',
        port: int = 5000,
        autostart: bool = True
    ) -> None:
        """Initialize the server configuration dialog.

        Args:
            parent: Parent widget for modal presentation
            host: Current host address
            port: Current port number
            autostart: Whether server auto-starts
        """
        super().__init__(parent)
        self.setWindowTitle("BigTime Server Configuration")
        self.setModal(True)
        self.setMinimumSize(400, 400)

        layout = QVBoxLayout(self)

        self.version_label = QLabel(f'BigTime Client v{shared.__VERSION__} API: v{shared.__API_VERSION__}')
        self.version_label.setFont(fonts['monospace_small'])
        self.version_label.setStyleSheet('color: #666;')
        layout.addWidget(self.version_label, 0, Qt.AlignmentFlag.AlignCenter)

        # Server settings group
        server_group = QGroupBox("Server Settings")
        server_layout = QFormLayout(server_group)

        # Host input with validation
        self.host_input = QLineEdit(host)
        self.host_input.setPlaceholderText("0.0.0.0 for all interfaces, 127.0.0.1 for local only")
        self.host_input.textChanged.connect(self.validate_inputs)
        server_layout.addRow("Host Address:", self.host_input)

        # Port input with text field
        self.port_input = QLineEdit(str(port))
        self.port_input.setPlaceholderText("1024-65535")
        self.port_input.setMaximumWidth(150)
        # Only allow digits
        port_validator = QRegularExpressionValidator(QRegularExpression(r"^\d{0,5}$"), self.port_input)
        self.port_input.setValidator(port_validator)
        self.port_input.textChanged.connect(self.validate_inputs)
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
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)

        self.api_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.api_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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

    def validate_inputs(self) -> None:
        """Validate user inputs and update UI accordingly."""
        host = self.host_input.text().strip()
        port_text = self.port_input.text().strip()

        # Basic host validation
        valid = True
        status_msg = "✅ Configuration valid"

        if not host:
            valid = False
            status_msg = "❌ Host address is required"
        elif host not in ['0.0.0.0', '127.0.0.1', 'localhost']:
            # Basic IP validation
            import re
            if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', host):
                valid = False
                status_msg = "⚠️ Please verify host address format"

        # Port validation
        if not port_text:
            valid = False
            status_msg = "❌ Port is required"
        else:
            try:
                port = int(port_text)
                if port < 1024 or port > 65535:
                    valid = False
                    status_msg = "❌ Port must be 1024-65535"
            except ValueError:
                valid = False
                status_msg = "❌ Port must be a number"

        self.status_label.setText(status_msg)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)

    def showEvent(self, event: Any) -> None:
        """Load API keys when dialog is shown."""
        super().showEvent(event)
        self.load_api_keys()

    def load_api_keys(self) -> None:
        """Load and display API keys from the server database."""
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
                    except Exception:
                        pass

                self.api_table.setItem(i, 3, QTableWidgetItem(last_used))

                # Store full API key in item data for revocation
                self.api_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, api_key)

        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to load API keys: {e}')

    def generate_api_key(self) -> None:
        """Generate a new API key."""
        try:
            import uuid
            from datetime import datetime

            from PyQt6.QtWidgets import QInputDialog

            from server.server import get_standalone_db
            from shared.utils import format_datetime
            from shared.logging_config import get_client_logger

            logger = get_client_logger()

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

            # Strip any potential whitespace
            api_key = api_key.strip()
            logger.info(f"Generated API key: {api_key[:8]}... (length={len(api_key)}, repr={repr(api_key)})")

            # Save to database with properly formatted timestamps
            try:
                conn = get_standalone_db()
                now = format_datetime(datetime.now())
                logger.info(f"Inserting API key {api_key[:8]}... for device {device_id}")
                conn.execute("""
                    INSERT INTO api_keys (key, device_id, created_at, last_used, active)
                    VALUES (?, ?, ?, ?, 1)
                """, (api_key, device_id, now, now))
                conn.commit()

                # Verify the insert worked
                verify_cursor = conn.execute("SELECT key, active FROM api_keys WHERE key = ?", (api_key,))
                verify_row = verify_cursor.fetchone()
                if verify_row:
                    logger.info(f"Successfully inserted API key {api_key[:8]}... (active={verify_row['active']}, length={len(verify_row['key'])})")
                else:
                    logger.error(f"Failed to verify API key insertion - key not found immediately after insert!")

                conn.close()
            except Exception as db_error:
                logger.error(f"Failed to insert API key into database: {db_error}")
                raise

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
            QMessageBox.warning(self, 'Error', f'Failed to generate API key: {e}')

    def revoke_api_key(self) -> None:
        """Revoke the selected API key."""
        try:
            current_row = self.api_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, 'No Selection', 'Please select an API key to revoke.')
                return

            # Get the full API key from item data
            api_key_item = self.api_table.item(current_row, 0)
            api_key = api_key_item.data(Qt.ItemDataRole.UserRole)

            # Confirm revocation
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
            QMessageBox.warning(self, 'Error', f'Failed to revoke API key: {e}')

    def copy_api_key(self) -> None:
        """Copy selected API key information to clipboard."""
        try:
            current_row = self.api_table.currentRow()
            if current_row < 0:
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
            QMessageBox.warning(self, 'Error', f'Failed to copy API key: {e}')

    def get_values(self) -> Dict[str, Any]:
        """Get the configuration values.

        Returns:
            Dictionary with keys: host, port, autostart
        """
        port_text = self.port_input.text().strip()
        try:
            port = int(port_text) if port_text else 5000
        except ValueError:
            port = 5000
        return {
            'host': self.host_input.text().strip() or '127.0.0.1',
            'port': port,
            'autostart': self.autostart_checkbox.isChecked()
        }

    def accept(self) -> None:
        """Override accept to validate inputs."""
        self.validate_inputs()  # Validate before accepting
        super().accept()
