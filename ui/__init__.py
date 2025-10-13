"""UI package export for the timeclock application.

Expose a simple run_app() function from the app module so the top-level
`main.py` can remain a thin launcher.
"""
from .app import run_app

__all__ = ["run_app"]
