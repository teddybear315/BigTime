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

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd BigTime

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

**Client** (Employee Time Clock):

```bash
python launcher.py client
# OR
python client_main.py
```

**Server** (Tray Mode with GUI):

```bash
python launcher.py server
```

**Server** (Console Mode):

```bash
python launcher.py console-server
```

---

## 📦 Building Executables

Build standalone executables with PyInstaller:

```bash
# Install pyinstaller
pip install pyinstaller
# OR (when windows doesnt like you)
python -m pip install pyinstaller

# Build client
pyinstaller BigTime-Client.spec

# Build server
pyinstaller BigTime-Server.spec

# Build both
pyinstaller BigTime-Client.spec && pyinstaller BigTime-Server.spec
```

Executables will be in `dist/` folder:

- `dist/BigTime-Client.exe` (or .app on macOS)
- `dist/BigTime-Server.exe` (or .app on macOS)

Feel free to make a pull request to merge other platform's executables in a format similar to the one shown below

```text
dist/
└── <OS>/                         # OS Executable Package
    ├── BigTime.                  # Client Executable
    ├── BigTime-Server            # Server Executable
    └── BigTime-Server - Shortcut # Client Shortcut for Desktop (Windows only)
```

### Server Autostart

Configure the server to automatically start on system boot.

Autostart setup files are located in the `dist/` folder.

**Windows**:
```bash
# Navigate to dist folder
cd dist

# Enable autostart
enable_autostart.bat

# Disable autostart
disable_autostart.bat
```

**Linux/macOS**:
```bash
# Navigate to dist folder
cd dist

# Enable autostart
chmod +x enable_autostart.sh
./enable_autostart.sh

# Disable autostart
chmod +x disable_autostart.sh
./disable_autostart.sh
```

**Manual (Advanced)**:
```bash
# From dist folder
python setup_autostart.py --enable --executable /path/to/BigTime-Server.exe

# Disable autostart
python setup_autostart.py --disable
```

**Note**: On Windows, requires `pywin32` and `winshell` packages:
```bash
pip install pywin32 winshell
```

See `docs/AUTOSTART.md` for detailed documentation.

---

## 🏗️ Architecture

### Component Breakdown

**Client Application** (`client/`):
- `gui_app.py`: Main PyQt6 GUI window with async initialization
- `timeclock_client.py`: High-level client abstraction layer
- `sync_service.py`: Background sync service with offline-first logic
- `background_worker.py`: Network operations in separate thread
- `dialog_managers.py`: Complex dialog management

**Server Application** (`server/`):
- `server.py`: Flask REST API with all endpoints
- `server_tray.py`: System tray application and settings GUI
- `timeserver_service.py`: NTP time synchronization

**Shared Components** (`shared/`):
- `db_helpers.py`: Database abstraction for local operations
- `models.py`: Shared data models (Employee, TimeLog, SyncState)
- `utils.py`: Common utilities and helpers
- `logging_config.py`: Standardized logging setup

**UI Components** (`ui/`):
- `dialogs.py`: Reusable dialog windows
- `pdf_utils.py`: PDF generation utilities
- `fonts.py`: Font definitions for consistent styling

### Data Models & Sync States

```
TimeLog {
  id: int (local)
  client_id: UUID (for idempotency)
  remote_id: int (server-assigned)
  badge: str
  clock_in: ISO datetime
  clock_out: ISO datetime
  sync_state: PENDING | SYNCED | FAILED
}

Employee {
  id: int
  name: str
  badge: str (unique)
  pin: str
  department: str
  rate: float
  period: hourly | monthly
  [+ contact & hire info]
}

SyncState: PENDING → SYNCED | FAILED
           FAILED → PENDING (retry)
           SYNCED → PENDING (data changed)
```

---

## 🔧 Configuration

### Client Configuration

Configure via GUI: **Settings → Server Configuration**

- **Server URL**: Default `http://127.0.0.1:5000`
- **Device ID**: Auto-generated unique identifier
- **API Key**: Obtained from server
- **Sync Interval**: Default 30 seconds

### Server Configuration

Managed in database (`server_bigtime.db`):

- Host: `0.0.0.0` (all interfaces)
- Port: `5000`
- API Keys: Managed via server GUI

---

## 🌐 Firewall Rules

```bash
# Allow server port (Windows)
netsh advfirewall firewall add rule name="BigTime Server" dir=in action=allow protocol=TCP localport=5000

# Allow server port (Linux)
sudo ufw allow 5000/tcp
```

---

## 📚 Documentation

Detailed documentation available in `docs/` folder:

- **[API Documentation](docs/API.md)** - Complete REST API reference
- **[Setup Guide](docs/SETUP.md)** - Detailed installation and configuration
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

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

- ✅ Automatic database initialization on first run
- ✅ Data persistence across app restarts
- ✅ Backup/restore capabilities
- ✅ Employee data migration on badge changes
- ✅ Comprehensive error handling and recovery

---

## 📈 Version History

### Version 2.1 (Current - December 11, 2025)

**Major Improvements**:
- ✅ **Enhanced Offline-First Sync**: Robust background sync service with exponential backoff
- ✅ **Better Error Handling**: Comprehensive error recovery and status reporting
- ✅ **Enhanced GUI**: Async initialization, better dialogs, improved UX
- ✅ **Connection Status Monitoring**: Real-time sync status indicators
- ✅ **Conflict Resolution**: Server-authoritative strategy with client change tracking

### Version 2.0 (Current - December 2025)

- ✅ **New Waitress WSGI Server**: Replaced simple Flask dev server with production-ready Waitress
- ✅ **Improved OOTB Setup**: Out-of-the-box experience with manager PIN setup
- ✅ **Enhanced error handling**: Basic error recovery and status reporting
- ✅ **Enhanced GUI**: Async initialization, better dialogs, improved UX
- ✅ **API Key Management**: Secure device authentication and key generation
- ✅ **Timezone Support**: Automatic timezone handling with NTP adjustment
- ✅ **WAL Mode Database**: SQLite with Write-Ahead Logging for reliability
- ✅ **System Tray Integration**: Server runs as system tray app (with console fallback)
- ✅ **Multi-Platform Build**: Specs for Windows, macOS, Linux

### Version 1.0 (Previous)

- Initial client-server architecture
- Basic Flask API
- Local SQLite database
- Basic time tracking functionality
- Employee management
- Simple payroll reports

---

## 🆘 Support

### 📞 Contact

**Suicide Clique Records LLC**
teddy@screcords.org

### Documentation

- Check `docs/` folder for detailed guides
- Review `TROUBLESHOOTING.md` for common issues

### Logs

- Client logs: `logs/client_YYYY-MM-DD.log`
- Server logs: `logs/server_YYYY-MM-DD.log`
- Sync logs: `logs/sync_YYYY-MM-DD.log`

### Common Issues

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## 🚧 Roadmap

Please do not expect updates, while I might dabble in software dev every now and again, I'm no longer a programmer, just a Claude script kiddie. Crazy fall off ik.

### Possible Features

- [ ] Web-based admin dashboard
- [ ] Advanced reporting analytics
- [ ] Integration with accounting software
- [ ] Role-based access control
- [ ] Automated backups
- [ ] Email notifications

---

## 📄 License

Proprietary - SCR LLC © 2025

Intended For Internal Use Only

---

**Last Updated**: December 11, 2025
**Version**: 2.1.1
**Status**: Production Ready
