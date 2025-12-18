"""
Database backup and restore utilities for BigTime.
Provides abstracted methods for backup and restore operations used across client and server.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from shared.utils import get_data_path


def get_backup_dir() -> Path:
    """Get the backups directory path, creating it if necessary."""
    backup_dir = get_data_path("backups")
    backup_dir.mkdir(exist_ok=True, parents=True)
    return backup_dir


def get_latest_backup(db_name: str) -> Optional[Path]:
    """Get the most recent backup file for a given database.

    Args:
        db_name: Name of the database file (e.g., 'bigtime.db', 'server_bigtime.db')

    Returns:
        Path to the most recent backup file, or None if no backups exist
    """
    backup_dir = get_backup_dir()

    # Find all backup files
    backup_files = sorted(backup_dir.glob("*.db"))

    if not backup_files:
        return None

    # Return the most recent one (last in sorted order by filename)
    return backup_files[-1]


def create_backup(db_name: str, is_server: bool = False) -> Optional[Path]:
    """Create a timestamped backup of a database.

    Args:
        db_name: Name of the database file (e.g., 'bigtime.db', 'server_bigtime.db')
        is_server: Whether this is a server database (for path resolution)

    Returns:
        Path to the created backup file, or None if backup failed

    Raises:
        FileNotFoundError: If the source database file doesn't exist
        IOError: If backup file cannot be written
    """
    db_path = get_data_path(db_name)

    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    backup_dir = get_backup_dir()

    now = datetime.now()
    backup_name = now.strftime('%m-%d-%Y %H-%M-%S') + '.db'
    backup_path = backup_dir / backup_name

    try:
        shutil.copy2(db_path, backup_path)
        return backup_path
    except Exception as e:
        raise IOError(f"Failed to create backup: {e}")


def create_backup_from_source(source_path: str) -> Path:
    """Create a timestamped backup of a database file from any source location.

    This is useful for migrating or backing up databases from arbitrary locations
    (e.g., when user selects a file via file dialog).

    Args:
        source_path: Full path to the source database file to backup

    Returns:
        Path to the created backup file

    Raises:
        FileNotFoundError: If the source database file doesn't exist
        IOError: If backup file cannot be written
    """
    source = Path(source_path)

    if not source.exists():
        raise FileNotFoundError(f"Database file not found: {source}")

    backup_dir = source.parent  # Create backup in same directory as source

    now = datetime.now()
    backup_name = f'{source.stem}.backup.{now.strftime("%Y%m%d_%H%M%S")}.db'
    backup_path = backup_dir / backup_name

    try:
        shutil.copy2(source, backup_path)
        return backup_path
    except Exception as e:
        raise IOError(f"Failed to create backup: {e}")



def restore_from_backup(backup_path: Path, db_name: str) -> bool:
    """Restore a database from a backup file.

    Args:
        backup_path: Path to the backup file to restore from
        db_name: Name of the database file to restore to (e.g., 'bigtime.db')

    Returns:
        True if restore was successful, False otherwise

    Raises:
        FileNotFoundError: If the backup file doesn't exist
        IOError: If restore cannot be completed
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    db_path = get_data_path(db_name)

    try:
        # Create a safety backup of the current database before overwriting
        if db_path.exists():
            create_backup(db_name)

        # Restore from backup
        shutil.copy2(backup_path, db_path)
        return True
    except Exception as e:
        raise IOError(f"Failed to restore from backup: {e}")


def get_latest_backup_info(db_name: str) -> Optional[Tuple[Path, str]]:
    """Get the latest backup file and its human-readable timestamp.

    Scans backup directory and additional candidate locations (./reports, .)
    for possible restore candidates.

    Args:
        db_name: Name of the database file

    Returns:
        Tuple of (backup_path, formatted_timestamp) or None if no backups exist
    """
    backup_path = get_latest_backup(db_name)

    if not backup_path:
        # Scan additional directories for candidates
        from shared.utils import get_data_path
        candidate_dirs = [
            Path('.'),  # Current directory
            Path('.') / 'reports',  # Reports subdirectory
            get_data_path(''),  # Data directory
        ]

        latest_candidate = None
        latest_mtime = 0

        for candidate_dir in candidate_dirs:
            if not candidate_dir.exists():
                continue

            # Search for files matching the database name
            for file in candidate_dir.glob(f'*{db_name}*'):
                if file.is_file() and file.suffix == '.db':
                    mtime = file.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_candidate = file

        backup_path = latest_candidate

        if not backup_path:
            return None

    # Extract timestamp from filename (format: MM-dd-YYYY HH-MM-SS.db)
    filename = backup_path.stem
    try:
        # Parse the timestamp from filename
        backup_time = datetime.strptime(filename, '%m-%d-%Y %H-%M-%S')
        formatted = backup_time.strftime('%B %d, %Y at %I:%M:%S %p')
        return (backup_path, formatted)
    except ValueError:
        # Fallback if filename format is unexpected - use file modification time
        from datetime import datetime as dt
        mtime = backup_path.stat().st_mtime
        backup_time = dt.fromtimestamp(mtime)
        formatted = backup_time.strftime('%B %d, %Y at %I:%M:%S %p')
        return (backup_path, formatted)


def list_backups(limit: Optional[int] = None) -> list:
    """List all available backup files.

    Args:
        limit: Maximum number of backups to return (most recent first)

    Returns:
        List of backup file paths, sorted by creation time (most recent first)
    """
    backup_dir = get_backup_dir()
    backup_files = sorted(backup_dir.glob("*.db"), reverse=True)

    if limit:
        backup_files = backup_files[:limit]

    return backup_files
