#!/usr/bin/env python3
"""
Entry point for BigTime client application
This is the target entry point for PyInstaller builds
"""

import sys
import os

# Add the project root to the path to ensure imports work
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import and run the client GUI application
from client.gui_app import main

if __name__ == '__main__':
    main()