# BigTime - Time Clock & Payroll Management System

## This program was written 100% by AI because I Dont Have Time™

A robust time tracking and payroll management system with client-server architecture and offline-first synchronization, built with Python and PyQt6.

---

## 📋 Overview

BigTime is a professional, production-ready time clock application designed for small to medium businesses. It features:

- **Client Application**: Employee time tracking with badge-based clock in/out and offline support
- **Server Application**: Centralized data management with REST API and Waitress WSGI server
- **Offline-First Sync Service**: Automatic background synchronization with conflict resolution
- **Time Synchronization**: NTP-based accurate timekeeping with timezone support
- **Payroll Reports**: PDF generation for paystubs and time summaries
- **Multi-Client Support**: Multiple clients can connect to one server simultaneously
- **System Tray Integration**: Server runs as system tray application (with console fallback)
- **Database Backup & Recovery**: SQLite with WAL mode for reliability

---

## 📚 Documentation

Detailed documentation available in `docs/` folder:

- **[Quick Start](docs/QUICKSTART.md)** - Quick start guide
- **[Version History](docs/VERSION_HISTORY.md) - Detailed changelog and version history
- **[Setup Guide](docs/SETUP.md)** - Detailed installation and configuration
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Database Migration Guide](docs/MIGRATION.md)** - Comprehensive migration tool documentation (for corrupt databases)
- **[API Documentation](docs/API.md)** - Complete REST API reference

---

## 🛠️ Technology Stack

### Core Technologies

- **Python 3.9+**: Core programming language
- **PyQt6**: Cross-platform GUI framework for client
- **Flask**: Lightweight web framework for REST API
- **Waitress**: Production-grade WSGI server (no external processes)
- **SQLite**: Lightweight database with WAL mode for reliability
- **requests**: HTTP client library for sync operations

### Additional Libraries

- **reportlab + Pillow**: PDF generation for paystubs and reports
- **ntplib**: NTP client for time synchronization (optional, has fallback)
- **flask-cors**: CORS support for multi-client connections
- **zoneinfo + tzdata**: Timezone handling (Windows compatibility)
- **termcolor**: Colored console output (optional, has fallback)
- **platformdirs**: Cross-platform data directory handling

### Key Design Patterns

- **Offline-First**: Client operates independently, syncs when available
- **Thread-Based Async**: Background tasks in separate threads (no async/await)
- **Idempotent Requests**: Client-generated UUIDs prevent duplicate entries
- **Exponential Backoff**: Smart retry logic with progressive delays
- **Server-Wins Conflict Resolution**: Server state is authoritative
- **Graceful Degradation**: Features work with limited fallbacks

---

## 🔒 Security

- **API Key Authentication**: All server requests require valid API key
- **Device ID Tracking**: Each client has unique identifier
- **CORS Protection**: Cross-origin request protection via Flask-CORS
- **Database Locking**: WAL mode prevents corruption
- **Data Validation**: Input validation on all endpoints

---

## 📊 Core Features

### Employee Management

- ✅ Add, edit, delete, and deactivate employees
- ✅ Badge Number-based identification (unique, searchable)
- ✅ Department and hire date tracking
- ✅ Employee rate and pay period configuration (hourly/monthly)
- ✅ PIN-based access control for secure operations
- ✅ Phone number, SSN, and date of birth fields
- ✅ Multi-device employee synchronization

### Time Tracking

- ✅ **Number-based Clock In/Out**: Input badge number to record time
- ✅ **Offline Operation**: Works without server connection
- ✅ **Automatic Time Sync**: NTP-based accurate timekeeping
- ✅ **Time Log Editing**: Managers can edit/correct clock entries
- ✅ **Client-side UUID Tracking**: Ensures idempotent sync operations
- ✅ **Audit Trail**: Created/updated timestamps on all records
- ✅ **Sync State Tracking**: PENDING/SYNCED/FAILED states for all records

### Payroll & Reporting

- ✅ Hourly and monthly pay period support
- ✅ Employee rate configuration and storage
- ✅ PDF paystub and timesheet generation
- ✅ Date range based time summaries
- ✅ Employee work history and time analysis
- ✅ ReportLab-based PDF export

### Background Synchronization (Offline-First)

- ✅ **Automatic Background Sync**: Runs every 30 seconds by default
- ✅ **Conflict Resolution**: Server-wins strategy with local change tracking
- ✅ **Offline Support**: Buffers changes locally during disconnection
- ✅ **Exponential Backoff**: Prevents excessive retries on failure
- ✅ **Manual Sync Trigger**: Force immediate synchronization
- ✅ **Sync Status Indicators**: Real-time connection status display
- ✅ **Persistent Queue**: Changes persist across app restarts
- ✅ **Separate Sync States**: Track employee changes vs time log changes

### Server Management

- ✅ REST API with Flask and Waitress WSGI server
- ✅ API Key management for device authentication
- ✅ Server configuration via GUI settings dialog
- ✅ Timezone support with automatic daylight saving handling
- ✅ NTP time synchronization with regional server selection
- ✅ CORS enabled for multi-client support
- ✅ SQLite database with WAL mode for concurrent access
- ✅ 5-second database busy timeout for reliability

### Administration

- ✅ Manager PIN setup on first run
- ✅ Out-of-the-box (OOTB) initial configuration
- ✅ Server Settings GUI with multiple tabs
- ✅ API key generation and device tracking
- ✅ Timezone and NTP configuration
- ✅ System tray integration (with console fallback)
- ✅ Multi-platform support (Windows, macOS, Linux)

### Data Management

- ✅ **Automatic Database Initialization**: Creates and configures databases on first run
- ✅ **Data Persistence**: Reliable storage across app restarts with SQLite WAL mode
- ✅ **Backup & Restore System**: Timestamped backups with GUI restore functionality
- ✅ **Database Migration Tool**: Automated schema updates with data preservation
  - Schema migration from any previous version to current
  - Automatic backup creation before migration
  - Network mount support for macOS compatibility
  - Integrity checks and repair functionality
  - Atomic operations with rollback protection
- ✅ **Employee Badge Migration**: Automatic data migration when badge numbers change
- ✅ **Comprehensive Error Recovery**: Graceful handling of database issues and corruption

---

## 🆘 Support

### 📞 Contact

**Suicide Clique Records LLC**
teddy@screcords.org

### Documentation

- Check `docs/` folder for detailed guides
- Review `TROUBLESHOOTING.md` for common issues

### Logs

- Client logs: `logs/client_MM-DD-YYYY HH:MM:SS.log`
- Server logs: `logs/server_MM-DD-YYYY HH:MM:SS.log`
- Sync logs: `logs/sync_MM-DD-YYYY HH:MM:SS.log`

### Common Issues

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## 🚧 Roadmap

Please do not expect updates, while I might dabble in software dev every now and again, I'm no longer a programmer, just a Claude script kiddie. Crazy fall off ik.

### Planned Updates

- [ ] UI/UX Refinement
- [ ] Increased data security via encryption

### Possible Features

- [ ] Web-based admin dashboard
- [ ] Advanced reporting analytics
- [ ] Role-based access control
- [ ] Automated backups
- [ ] Email notifications

### AI Proposed, Unplanned Features
- [ ] Integration with accounting software

---

## 📄 License

Proprietary - SCR LLC © 2025

Intended For Internal Use Only

---

**Last Updated**: December 17, 2025
**Version**: 2.1.3
**Status**: Production Ready
