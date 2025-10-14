#!/usr/bin/env python3
"""
BigTime Application Launcher
Provides simple entry points for client and server applications.
"""

import sys
from pathlib import Path

# Add the project root to Python path for clean imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """Main launcher with command-line arguments"""

    if len(sys.argv) < 2:
        print("BigTime Application Launcher")
        print()
        print("Usage:")
        print("  python launcher.py client              # Run client GUI application")
        print("  python launcher.py server              # Run server (tray with console fallback)")
        print("  python launcher.py server-tray         # Run server (tray with console fallback)")
        print("  python launcher.py console-server      # Run server in console mode only")
        print()
        print("Note: All server modes use Waitress WSGI server")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'client':
        from client.gui_app import main as run_client
        run_client()

    elif command == 'server-tray' or command == 'server':
        from server import run_server_tray
        run_server_tray()

    elif command == 'console-server':
        from server import run_console_server
        run_console_server()

    else:
        print(f"Unknown command: {command}")
        print("Use 'client', 'server', 'server-tray', or 'console-server'")
        sys.exit(1)


if __name__ == '__main__':
    main()
