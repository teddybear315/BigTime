"""UI package for BigTime client application.

Contains UI widgets and dialog components used by the client application.
Main GUI application logic is now in client.gui_app.BigTimeClientApp.
"""

# Export the dialog components that are used by the client
from .dialogs import (AddEmployeeDialog, DateRangeDialog, EditEmployeeDialog,
                      EditLogsDialog, OOTBClientDialog, OOTBServerDialog,
                      ServerConfigDialog, SettingsDialog)
from .fonts import fonts
from .pdf_utils import generate_paystub_pdf

__all__ = [
    "AddEmployeeDialog", "EditEmployeeDialog", "DateRangeDialog", "EditLogsDialog",
    "OOTBClientDialog", "OOTBServerDialog", "ServerConfigDialog", "SettingsDialog",
    "generate_paystub_pdf",
    "fonts"
]
