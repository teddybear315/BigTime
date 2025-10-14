"""Client package for BigTime application.

Provides client abstraction layer and sync services for local and remote operations.
"""
from .sync_service import RemoteSyncService, get_sync_service
from .timeclock_client import BigTimeClient, get_client
from .gui_app import main as gui_main

__all__ = ["get_client", "BigTimeClient", "get_sync_service", "RemoteSyncService", "gui_main"]
