"""
Shared utility functions for BigTime application.
"""

import sys
import zoneinfo
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Union


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller

    For bundled read-only resources like icons, fonts, etc.
    Use get_data_path() for writable data like databases and logs.
    """
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        # Check if we're running in onefile mode (sys._MEIPASS exists)
        if hasattr(sys, '_MEIPASS'):
            # Onefile mode: bundled resources are in the temp extraction folder
            base_path = Path(sys._MEIPASS)
        else:
            # Onedir mode: bundled resources are alongside the executable
            base_path = Path(sys.executable).parent
    else:
        # Running in development - go up from shared/ to project root
        base_path = Path(__file__).parent.parent

    return base_path / relative_path


def get_data_path(relative_path: str) -> Path:
    """Get absolute path to writable data files (databases, logs, backups, reports)
    Returns a stable, writable location for runtime data.

    Behavior:
    - In development (not frozen) this returns a path under the project root
      (keeps existing dev behavior).
    - For frozen/packaged applications (PyInstaller), prefer a per-user data
      directory so updates to the app bundle do not overwrite the database.

    On macOS this will resolve to: ``~/Library/Application Support/<AppName>/...``
    (or the path returned by ``platformdirs.user_data_dir`` when available).
    """
    # Development: keep existing behavior for convenience
    # if not getattr(sys, 'frozen', False):
    #     return Path(__file__).parent.parent / relative_path

    # Packaged app: prefer a per-user data dir (does not live inside the .app bundle)
    try:
        # platformdirs provides cross-platform user data locations
        from platformdirs import user_data_dir

        base_path = Path(user_data_dir("BigTime"))
    except Exception:
        # Fallbacks if platformdirs is not available
        if sys.platform == 'darwin':
            base_path = Path.home() / 'Library' / 'Application Support' / 'BigTime'
        elif sys.platform == 'win32':
            # Use %APPDATA% (Roaming) if set
            appdata = os.getenv('APPDATA')
            if appdata:
                base_path = Path(appdata) / 'BigTime'
            else:
                base_path = Path.home() / 'AppData' / 'Roaming' / 'BigTime'
        else:
            # Linux and other Unix-like systems
            base_path = Path.home() / '.local' / 'share' / 'BigTime'

    # Ensure the directory exists
    try:
        base_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Last-ditch fallback to executable dir if we cannot create user dir
        base_path = Path(sys.executable).parent

    return base_path / relative_path


def to_int_optional(value: Union[str, int, None]) -> Optional[int]:
    """Convert string to int, return None if invalid"""
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def format_datetime(dt: datetime) -> str:
    """Format datetime to standard string format"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse datetime string, return None if invalid"""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # Try ISO format
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except ValueError:
            return None


def format_date(d) -> str:
    """Format date to standard string format"""
    if isinstance(d, date):
        return d.isoformat()
    elif isinstance(d, str):
        return d  # Already a string
    else:
        return str(d)  # Convert other types to string


def parse_date(date_str: str) -> Optional[date]:
    """Parse date string, return None if invalid"""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None


def validate_badge(badge: str) -> bool:
    """Validate employee badge format"""
    return bool(badge and badge.strip())


def validate_pin(pin: str) -> bool:
    """Validate PIN format"""
    return bool(pin and len(pin.strip()) >= 4)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem usage"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def utc_to_local_datetime(utc_dt: datetime, local_tz: str = None) -> datetime:
    """Convert UTC datetime to local timezone for display"""
    if utc_dt.tzinfo is None:
        # Assume it's UTC if no timezone info
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    if local_tz:
        try:
            local_timezone = zoneinfo.ZoneInfo(local_tz)
            return utc_dt.astimezone(local_timezone)
        except Exception:
            pass

    # Fallback to system local timezone
    return utc_dt.astimezone()


def local_to_utc_datetime(local_dt: datetime, local_tz: str = None) -> datetime:
    """Convert local datetime to UTC for storage"""
    if local_dt.tzinfo is None:
        # Assume it's in the specified local timezone or system timezone
        if local_tz:
            try:
                local_timezone = zoneinfo.ZoneInfo(local_tz)
                local_dt = local_dt.replace(tzinfo=local_timezone)
            except Exception:
                local_dt = local_dt.astimezone()
        else:
            local_dt = local_dt.astimezone()

    return local_dt.astimezone(timezone.utc)


def format_datetime_local(utc_dt: datetime, local_tz: str = None) -> str:
    """Format UTC datetime as local time string for display"""
    local_dt = utc_to_local_datetime(utc_dt, local_tz)
    return local_dt.strftime('%m-%d-%Y %H:%M:%S')


def parse_datetime_to_utc(dt_str: str, local_tz: str = None) -> Optional[datetime]:
    """Parse local datetime string to UTC for storage"""
    if not dt_str:
        return None

    try:
        # Try MM-dd-yyyy HH:mm:ss format (UI format)
        local_dt = datetime.strptime(dt_str, '%m-%d-%Y %H:%M:%S')
        return local_to_utc_datetime(local_dt, local_tz)
    except ValueError:
        try:
            # Try standard format
            local_dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            return local_to_utc_datetime(local_dt, local_tz)
        except ValueError:
            return None


def get_icon_path() -> Path:
    """Get path to the application icon file"""
    return get_resource_path('ico.ico')


def create_app_icon():
    """Create QIcon from bundled icon file, with fallback"""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap

    icon_path = get_icon_path()

    # Debug: log the icon path being checked
    import logging
    logger = logging.getLogger('CLIENT')
    logger.debug(f"Looking for icon at: {icon_path}")
    logger.debug(f"Icon exists: {icon_path.exists()}")

    # Try to load the bundled icon file
    if icon_path.exists():
        logger.debug("Using real icon file")
        return QIcon(str(icon_path))

    # Fallback: Create a simple programmatic icon
    logger.warning(f"Icon file not found at {icon_path}, using fallback")
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setBrush(QBrush(QColor(0, 120, 215)))  # Blue circle
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()

    return QIcon(pixmap)
