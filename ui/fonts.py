"""
UI Font definitions for BigTime application.
Provides consistent font styling across all UI components.
"""

from PyQt6.QtGui import QFont

# Font definitions - direct QFont objects ready to use
fonts = {
    # Standard Verdana fonts
    "default": QFont("Verdana", 14),
    "large": QFont("Verdana", 20),
    "small": QFont("Verdana", 9),

    # Monospace fonts (Courier New) - sized 14 with variants
    "monospace": QFont("Courier New", 14),
    "monospace_small": QFont("Courier New", 9),
    "monospace_large": QFont("Courier New", 20),

    # Bold variants
    "default_bold": QFont("Verdana", 14, QFont.Weight.Bold),
    "large_bold": QFont("Verdana", 20, QFont.Weight.Bold),
    "small_bold": QFont("Verdana", 9, QFont.Weight.Bold),

    # Monospace bold variants
    "monospace_bold": QFont("Courier New", 14, QFont.Weight.Bold),
    "monospace_small_bold": QFont("Courier New", 9, QFont.Weight.Bold),
    "monospace_large_bold": QFont("Courier New", 20, QFont.Weight.Bold),

    # Header fonts (larger and bold)
    "header": QFont("Verdana", 18, QFont.Weight.Bold),
    "subheader": QFont("Verdana", 16, QFont.Weight.Bold),
    "title": QFont("Verdana", 24, QFont.Weight.Bold),
}
