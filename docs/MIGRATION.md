# Database Migration Tool

## Overview

BigTime includes a comprehensive database migration tool that automatically updates database schemas to the current version while preserving all existing data. The migration tool is available in both client and server applications through the user interface.

## Features

### Automatic Schema Updates
- **Table Creation**: Creates missing tables with proper schema
- **Column Addition**: Adds new columns to existing tables with appropriate defaults
- **Data Preservation**: Maintains all existing records during migration
- **Integrity Checks**: Performs database integrity verification before and after migration
- **Backup Creation**: Automatically creates timestamped backups before migration

### Migration Capabilities

The migration tool handles the following schema updates:

#### Server Database (`server_bigtime.db`)
- **API Keys Table**: Ensures proper API key management with device tracking
- **Settings Table**: Centralizes server configuration storage
- **Employees Table**: Updates employee schema with PIN support and status tracking
- **Time Logs Table**: Enhances time tracking with sync states and audit trails
- **Pending Changes Table**: Supports offline-first synchronization queuing

#### Client Database (`bigtime.db`)
- **Employees Table**: Matches server schema for local caching
- **Time Logs Table**: Client-side time tracking with sync state management
- **Pending Changes Table**: Local change queuing for background sync
- **Settings Table**: Client configuration persistence

### Network Mount Support

The migration tool includes special handling for databases on network mounts (common on macOS):
- Automatically detects network-mounted databases
- Creates temporary local copies for migration
- Ensures atomic operations to prevent corruption
- Copies migrated database back to original location

## Usage

### Server Application

#### Via System Tray (GUI Mode)
1. Right-click the BigTime Server tray icon
2. Select **"Maintenance"** → **"Migrate Database..."**
3. Choose the database file to migrate
4. Confirm the operation
5. Wait for migration completion

#### Via Console Mode
The migration tool is primarily designed for GUI usage but can be invoked programmatically:

```python
from shared.db_helpers import perform_database_migration

# Migrate a database file
perform_database_migration("/path/to/database.db")
```

### Client Application

#### Via Settings Menu
1. Open the client application
2. Navigate to **Settings** → **"Migrate Database"**
3. Select the database file to migrate
4. Confirm the operation
5. Restart the client to use migrated database

### File Selection

The migration tool provides an intuitive file selection dialog:

#### Auto-Detection
- Automatically searches common locations for database files
- Suggests appropriate default filenames based on context
- Shows file path tooltips for confirmation

#### Manual Selection
- Browse button for custom file selection
- Filters for SQLite database files (*.db)
- Support for all file types as fallback

## Migration Process

### Step-by-Step Process

1. **File Validation**
   - Verifies selected database file exists
   - Checks file permissions and accessibility

2. **Pre-Migration Backup**
   - Creates timestamped backup in same directory as source
   - Format: `originalname.backup.YYYYMMDD_HHMMSS.db`
   - Backup location displayed in completion message

3. **Network Mount Detection**
   - Automatically detects if database is on network storage
   - Creates temporary local copy if needed for reliability

4. **Integrity Check**
   - Runs SQLite `PRAGMA integrity_check`
   - Performs `REINDEX` if integrity issues detected
   - Logs any repair operations performed

5. **Schema Migrations**
   - Sequentially applies all required schema updates
   - Uses `CREATE TABLE IF NOT EXISTS` for safety
   - Adds missing columns with `ALTER TABLE`
   - Updates existing data where needed

6. **Final Verification**
   - Commits all changes atomically
   - Verifies migration success
   - Copies migrated database back if temporary copy was used

7. **Cleanup**
   - Removes temporary files if created
   - Displays success message with backup location

### Schema Migrations Applied

#### Migration 1: API Keys Table
```sql
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key TEXT UNIQUE NOT NULL,
    device_id TEXT,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP
);
```

Adds missing columns: `device_id`, `active`, `created_at`, `last_used`

#### Migration 2: Settings Table
```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Migration 3: Employees Table Updates
```sql
-- Adds missing columns if they don't exist:
ALTER TABLE employees ADD COLUMN pin TEXT;
ALTER TABLE employees ADD COLUMN deactivated INTEGER DEFAULT 0;
ALTER TABLE employees ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
```

#### Migration 4: Time Logs Table Updates
```sql
-- Adds sync tracking and audit columns:
ALTER TABLE time_logs ADD COLUMN synced INTEGER DEFAULT 0;
ALTER TABLE time_logs ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
```

#### Migration 5: Pending Changes Table
```sql
CREATE TABLE IF NOT EXISTS pending_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Safety Features

### Automatic Backups
- **Pre-Migration**: Backup created before any changes
- **Timestamped**: Unique filename prevents overwriting
- **Same Location**: Backup stored alongside original database
- **Notification**: Backup location shown in completion dialog

### Atomic Operations
- **Single Transaction**: All migrations wrapped in single transaction
- **Rollback Support**: Failed migrations automatically rolled back
- **No Partial Updates**: Either all migrations succeed or none applied

### Data Preservation
- **Non-Destructive**: Never removes existing tables or columns
- **Additive Only**: Only adds new schema elements
- **Default Values**: New columns get appropriate defaults
- **Existing Data**: All existing records preserved unchanged

### Error Handling
- **Graceful Failures**: Clear error messages with context
- **Backup Preservation**: Backup retained even on migration failure
- **Logging**: Detailed migration logs for troubleshooting
- **Recovery Information**: Instructions provided for manual recovery

## Troubleshooting

### Common Issues

#### "Database file not found"
- **Cause**: Selected file path is invalid or inaccessible
- **Solution**: Verify file exists and has read/write permissions

#### "Migration failed: database is locked"
- **Cause**: Database in use by another process
- **Solution**: Close all BigTime applications before migrating

#### "Network mount detected, creating temporary copy failed"
- **Cause**: Insufficient disk space or permissions for temporary file
- **Solution**: Free up disk space or migrate from local copy

### Recovery Procedures

#### Failed Migration
1. Check that backup file exists in same directory as original
2. Close all BigTime applications
3. Replace original database with backup file
4. Restart application and retry migration

#### Corrupted Migration
1. Locate timestamped backup file
2. Use backup/restore functionality to restore from backup
3. Verify restored database works correctly
4. Re-attempt migration if needed

## Migration History

Migrations are designed to be idempotent - running the same migration multiple times is safe and will not cause issues. The migration tool:

- Checks for existing tables before creating
- Checks for existing columns before adding
- Uses appropriate defaults for new columns
- Preserves all existing data and relationships

## Version Compatibility

The migration tool is designed to update databases from any previous version to the current schema:

- **v1.x to v2.1.x**: Complete schema overhaul with data preservation
- **v2.0.x to v2.1.x**: Incremental updates for new features
- **v2.1.0 to v2.1.2**: Minor schema additions and improvements

## Best Practices

### Before Migration
- **Backup Manually**: Create additional manual backup if database is critical
- **Close Applications**: Ensure no BigTime processes are accessing database
- **Verify Space**: Ensure sufficient disk space for temporary files
- **Network Stability**: Use stable connection if database is on network storage

### After Migration
- **Test Functionality**: Verify all features work correctly with migrated database
- **Backup Verification**: Confirm backup was created and is accessible
- **Log Review**: Check application logs for any migration warnings
- **Import Process**: For server databases, use "Restore Database" to import migrated file

### Maintenance
- **Regular Backups**: Continue regular backup routine after migration
- **Monitor Performance**: Watch for any performance changes after migration
- **Keep Backups**: Retain pre-migration backup until confident in new schema
- **Documentation**: Note migration date and version for future reference

## Technical Details

### Implementation Location
- **Core Function**: `shared/db_helpers.py` - `perform_database_migration()`
- **Server UI**: `server/server_tray.py` - `migrate_database()`
- **Client UI**: Accessible through Settings menu
- **Dialog**: `ui/dialogs/shared.py` - `DatabaseSelectDialog`

### Dependencies
- **SQLite3**: Core database operations
- **Pathlib**: File path handling
- **Shutil**: File copy operations
- **Tempfile**: Temporary file creation for network mounts
- **Logging**: Detailed operation logging

### Thread Safety
The migration tool is designed for single-threaded execution:
- Requires exclusive access to database file
- Creates locks during migration process
- Should not be run concurrently on same database
