# BigTime - Time Clock & Payroll Management System

## This program was written 100% by AI because I Dont Have Time™

A comprehensive time tracking and payroll management system with client-server architecture, built with Python and PyQt6.

---

## 📋 Overview

BigTime is a professional time clock application designed for small to medium businesses. It features:

- **Client Application**: Employee time tracking with badge-based clock in/out
- **Server Application**: Centralized data management with REST API
- **Sync Service**: Automatic synchronization between clients and server
- **Time Synchronization**: NTP-based accurate timekeeping
- **Payroll Reports**: PDF generation for paystubs and timesheets
- **Multi-Client Support**: Multiple clients can connect to one server

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
└── <OS>/                  # OS Executable Package
    ├── BigTime-Client     # Client Executable
    ├── BigTime-Server     # Server Executable
    └── BigTime - Shortcut # Client Shortcut for Desktop
```

---

## 🏗️ Architecture

### Client-Server Model

```text
┌─────────────────┐         ┌─────────────────┐
│  Client App     │         │  Server App     │
│  (PyQt6 GUI)    │ ◄─────► │  (REST API)     │
│                 │  HTTP   │  (Waitress)     │
│  - Time Clock   │         │  - Database     │
│  - Sync Service │         │  - Time Sync    │
│  - Reports      │         │  - API Routes   │
└─────────────────┘         └─────────────────┘
```

### Components

- **Client**: PyQt6 GUI application for employees to clock in/out
- **Server**: Flask REST API served by Waitress WSGI server
- **Shared**: Common utilities, models, and database helpers
- **UI**: Reusable dialog components and PDF generation
- **Sync Service**: Background service for client-server synchronization

---

## 📁 Project Structure

```text
BigTime/
├── client/                 # Client application
│   ├── gui_app.py         # Main GUI application
│   ├── sync_service.py    # Sync service
│   ├── background_worker.py
│   ├── dialog_managers.py
│   └── timeclock_client.py
│
├── server/                 # Server application
│   ├── server.py          # REST API routes
│   ├── server_tray.py     # System tray application
│   └── timeserver_service.py  # NTP time sync
│
├── shared/                 # Shared utilities
│   ├── db_helpers.py      # Database operations
│   ├── models.py          # Data models
│   ├── utils.py           # Common utilities
│   └── logging_config.py  # Logging setup
│
├── ui/                     # UI components
│   ├── dialogs.py         # Dialog windows
│   ├── fonts.py           # Font definitions
│   └── pdf_utils.py       # PDF generation
│
├── docs/                   # Documentation
│   ├── API.md             # Server API documentation
│   ├── SETUP.md           # Setup guide
│   └── TROUBLESHOOTING.md # Common issues
│
├── client_main.py         # Client entry point
├── launcher.py            # Development launcher
├── requirements.txt       # Python dependencies
├── BigTime-Client.spec    # Client build spec
├── BigTime-Server.spec    # Server build spec
└── README.md              # This file
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

## 📚 Documentation

Detailed documentation available in `docs/` folder:

- **[API Documentation](docs/API.md)** - Complete REST API reference
- **[Setup Guide](docs/SETUP.md)** - Detailed installation and configuration
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Testing Guide](TESTING_GUIDE.md)** - Testing procedures
- **[Codebase Analysis](CODEBASE_ANALYSIS.md)** - Code quality analysis

---

## 🛠️ Technology Stack

### Core Technologies

- **Python 3.9+**: Core language
- **PyQt6**: GUI framework
- **Flask**: Web framework (server API)
- **Waitress**: Production WSGI server
- **SQLite**: Database (with WAL mode)

### Key Libraries

- **requests**: HTTP client for sync
- **reportlab**: PDF generation
- **ntplib**: NTP time synchronization (optional)
- **zoneinfo/tzdata**: Timezone handling

---

## 🔒 Security

- **API Key Authentication**: All server requests require valid API key
- **Device ID Tracking**: Each client has unique identifier
- **CORS Protection**: Cross-origin request protection via Flask-CORS
- **Database Locking**: WAL mode prevents corruption
- **Data Validation**: Input validation on all endpoints

---

## 🌐 Network Requirements

### Client

- Outbound HTTP to server (default port 5000)
- Internet access for NTP time sync (optional)

### Server

- Inbound HTTP on port 5000 (configurable)
- Internet access for NTP time sync (optional)

### Firewall Rules

```bash
# Allow server port (Windows)
netsh advfirewall firewall add rule name="BigTime Server" dir=in action=allow protocol=TCP localport=5000

# Allow server port (Linux)
sudo ufw allow 5000/tcp
```

---

## 📊 Features

### Employee Management

- ✅ Add, edit, delete employees
- ✅ Badge-based identification
- ✅ Department organization
- ✅ Deactivation (soft delete)
- ✅ PIN protection

### Time Tracking

- ✅ Clock in/out with badge scan
- ✅ Automatic time synchronization
- ✅ Time log editing
- ✅ Audit trail

### Payroll

- ✅ Hourly/salary pay periods
- ✅ Overtime calculation
- ✅ PDF paystub generation
- ✅ Date range reports
- ✅ Employee time summaries

### Synchronization

- ✅ Automatic background sync
- ✅ Conflict resolution
- ✅ Offline operation support
- ✅ Manual sync trigger
- ✅ Sync status indicators

### Administration

- ✅ API key management
- ✅ Server configuration
- ✅ Database backups
- ✅ System tray integration
- ✅ Multi-platform support

---

## 🖥️ System Requirements

### Minimum

- **OS**: Windows 10, macOS 10.14, Linux (Ubuntu 20.04+)
- **RAM**: 2 GB
- **Disk**: 100 MB free space (distributed executables only)
- **Python**: 3.9+ (for source)

### Recommended

- **OS**: Windows 11, macOS 12+, Linux (Ubuntu 22.04+)
- **RAM**: 4 GB
- **Disk**: 1 GB free space
- **Network**: 100 Mbps

---

## 🤝 Contributing

This is a private business application. For internal development:

1. Follow existing code style
2. Update documentation for changes
3. Test thoroughly before committing
4. Use meaningful commit messages

---

## 📄 License

Proprietary - SCR LLC © 2025

---

## 🆘 Support

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

## 📈 Version History

### Version 2.0 (BigTime)

- ✅ New server built with Waitress
- ✅ Enhanced OOTB setup flow
- ✅ Enhanced error handling
- ✅ Enhanced GUI
- ✅ Cleaned up imports and dependencies
- ✅ Connect over HTTP

### Version 1.0 (SmallTime)

- Initial client-server architecture
- Basic time tracking functionality
- Employee management
- Payroll reports
- Single machine

---

## 🚧 Roadmap

Please do not expect updates, while I might dabble in software dev every now and again, I'm no longer a programmer, just a Claude script kiddie. Crazy fall off ik.

### Possible Features

- [ ] Web-based admin dashboard
- [ ] Mobile app support
- [ ] Advanced reporting analytics
- [ ] Integration with accounting software
- [ ] Role-based access control
- [ ] Automated backups
- [ ] Email notifications

---

## 📞 Contact

**Suicide Clique Records LLC**
teddy@screcords.org

---

Intended For Internal Use Only

---

**Last Updated**: October 14, 2025
**Version**: 2.0
**Status**: Production Ready
