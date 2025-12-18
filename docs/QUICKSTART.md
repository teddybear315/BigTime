# 🚀 Quick Start

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd BigTime

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

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

# NOTE: These spec files do not exist, append use -w.spec for windows and -m.spec for others
```

Executables will be in `dist/` folder:

- `dist/BigTime.exe` (or .app on macOS)
- `dist/BigTime-Server.exe` (or .app on macOS)

Feel free to make a pull request to merge other platform's executables in a format similar to the one shown below

```text
dist/
└── <OS>/                         # OS Executable Package
    ├── BigTime.                  # Client Executable
    ├── BigTime-Server            # Server Executable
    └── BigTime-Server - Shortcut # Client Shortcut for Desktop (Windows only)
```

---

## 📕 Autostart

See [AUTOSTART GUIDE](/docs/API.md)

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
