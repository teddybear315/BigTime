"""Server package for BigTime application.

Provides entry points for both the system tray server (default) and console server.
The tray server is cross-platform and includes GUI configuration and fallback to console mode.
All server modes use Waitress WSGI server for production-ready performance.
"""
from .server import app as flask_app
from .server import init_server_db, run_server
from .server_tray import main as run_server_tray  # Tray application

__all__ = ["run_server", "run_server_tray", "flask_app", "init_server_db", "run_console_server"]

# Default server port configuration
DEFAULT_SERVER_PORT: int = 5000


def run_console_server(host='127.0.0.1', port=DEFAULT_SERVER_PORT, debug=False):
    """Run the server directly in console mode using Waitress"""
    print(f"BigTime Server - Console Mode")
    print(f"Starting server on {host}:{port}")
    print(f"Using Waitress WSGI server")
    if debug:
        print("Note: Debug mode does not affect Waitress (use logging for debugging)")

    init_server_db()
    run_server(host=host, port=port)
