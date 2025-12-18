"""UI package for BigTime client application.

Contains UI widgets and dialog components used by the client application.
Main GUI application logic is now in client.gui_app.BigTimeClientApp.
"""

# Import submodules to ensure they're available for compilation
from . import dialogs
from .fonts import fonts
from .pdf_utils import generate_paystub_pdf

__all__ = [
    "dialogs",
    "set_dialog_icon",
    "generate_paystub_pdf",
    "fonts"
]

from shared.utils import create_app_icon

def set_dialog_icon(dialog):
    """Set the application icon on a dialog"""
    dialog.setWindowIcon(create_app_icon())
