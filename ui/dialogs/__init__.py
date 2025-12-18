"""Dialog submodules for BigTime application.

This package contains dialog classes organized by their usage:
- client: Client-specific dialogs
- server: Server-specific dialogs
- shared: Dialogs used by both client and server
"""

# Import all submodules to ensure they're available
from . import client
from . import server
from . import shared

__all__ = ['client', 'server', 'shared']
