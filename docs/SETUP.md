# BigTime Setup Guide

Complete installation and configuration guide for BigTime Time Clock & Payroll Management System.

---

## 📋 Prerequisites

### System Requirements

**Operating System**:

- Windows 10/11 (64-bit)
- macOS 10.14+ (Mojave or later)
- Linux (Ubuntu 20.04+, Fedora 34+)

**Hardware**:

- **Minimum**: 2 GB RAM, 500 MB disk space
- **Recommended**: 4 GB RAM, 1 GB disk space
- Network connectivity (for client-server communication)

**Software** (for running from source):

- Python 3.9 or higher
- pip (Python package manager)
- Git (optional, for version control)

---

## 🚀 Installation

### Option 1: Using Pre-built Executables (Recommended)

1. **Download Executables**:
   - Get `BigTime-Client.exe` and `BigTime-Server.exe` from distribution folder
   - Or build from source (see Option 2)

2. **Install on Server Machine**:

   ```
   - Copy BigTime-Server.exe to server directory (e.g., C:\BigTime\Server\)
   - Run BigTime-Server.exe
   - Allow through firewall when prompted
   ```

3. **Install on Client Machines**:

   ```
   - Copy BigTime-Client.exe to each client (e.g., C:\BigTime\Client\)
   - Run BigTime-Client.exe
   - Complete first-time setup wizard
   ```

### Option 2: Running from Source

1. **Clone Repository**:

   ```bash
   git clone <repository-url>
   cd BigTime
   ```

2. **Create Virtual Environment** (recommended):

   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Verify Installation**:

   ```bash
   # Check all imports work
   python -c "import PyQt6; import flask; import waitress; import reportlab; print('All dependencies installed!')"
   ```

### Option 3: Building Executables

```bash
# Install PyInstaller
pip install pyinstaller

# Build client
pyinstaller BigTime-Client.spec

# Build server
pyinstaller BigTime-Server.spec

# Find executables in dist/ folder
```

---

## ⚙️ Configuration

### Server Setup

#### 1. First Run

Run the server application:

```bash
# From executable
BigTime-Server.exe

# From source
python launcher.py server
```

The server will:

- Create database (`server_bigtime.db`)
- Initialize logging directory (`logs/`)
- Start system tray icon (or console mode if tray unavailable)
- Bind to `0.0.0.0:5000` (all interfaces, port 5000)

#### 2. Configure Server Settings

Right-click system tray icon → **Server Settings**:

**General Tab**:

- **Company Name**: Your company name
- **Timezone**: Select your timezone (affects time calculations)

**Network Tab**:

- **Host**: `0.0.0.0` (all interfaces) or `127.0.0.1` (local only)
- **Port**: `5000` (default) or custom port
- **Enable CORS**: ✓ (required for client access)

**Time Sync Tab**:

- **Enable NTP Sync**: ✓ (recommended for accurate time)
- **NTP Server**: `pool.ntp.org` (default)
- **Sync Interval**: 300 seconds (5 minutes)

#### 3. Generate API Keys

Right-click system tray icon → **Server Settings** → **API Keys**:

1. Click **"Generate New Key"**
2. Enter Device ID (e.g., `client-workstation-1`)
3. Copy the generated API key (format: `bt-xxxxxxxxxxxx`)
4. Provide key to client for configuration

**Example**:

```
Device ID: client-reception
API Key: bt-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

#### 4. Firewall Configuration

**Windows**:

```powershell
# Allow inbound on port 5000
netsh advfirewall firewall add rule name="BigTime Server" dir=in action=allow protocol=TCP localport=5000
```

**Linux (UFW)**:

```bash
sudo ufw allow 5000/tcp
sudo ufw reload
```

**macOS**:

- System Preferences → Security & Privacy → Firewall → Firewall Options
- Add BigTime-Server to allowed applications

---

### Client Setup

#### 1. First Run (OOTB - Out of the Box Experience)

Run client application:

```bash
# From executable
BigTime-Client.exe

# From source
python launcher.py client
```

On first run, you'll see the setup wizard:

#### 2. Setup Wizard Steps

**Step 1: Company Information**

- Company Name: (auto-filled from server or enter manually)

**Step 2: Manager Settings**

- Manager Name: (for administrative access)
- Manager PIN: 4-6 digit PIN for accessing settings

**Step 3: Server Configuration**

- Enable Sync: ✓ (check to enable server sync)
- Server URL: `http://[server-ip]:5000`
  - Example: `http://192.168.1.100:5000`
  - Local: `http://127.0.0.1:5000`
- Device ID: Auto-generated (e.g., `bigtime-HOSTNAME-abc123`)
- API Key: Paste the API key from server
- Sync Interval: 30 seconds (default)
- Timeout: 10 seconds (default)

**Step 4: Test Connection**

- Click **"Test Connection"** to verify server accessibility
- Should show: ✓ "Connected successfully to [Company Name]"

**Step 5: Complete Setup**

- Click **"Save"** to complete setup
- Client will automatically sync with server

#### 3. Manual Configuration (After Setup)

Access settings: **Menu → Settings → Server Configuration**

Update any settings and click **"Test Connection"** before saving.

---

## 👥 Employee Setup

### Adding Employees (Server)

Use the server GUI or client to add employees:

**Via Client GUI**:

1. Open client application
2. Click **"Manage Employees"**
3. Click **"Add Employee"**
4. Fill in employee details:
   - Name (required)
   - Badge (required, unique identifier)
   - Phone Number
   - PIN (for clock in/out)
   - Department
   - Date of Birth
   - Hire Date
   - Pay Period (hourly/salary)
   - Pay Rate
5. Click **"Save"**

**Example Employee**:

```
Name: John Doe
Badge: JD001
Phone: 555-123-4567
PIN: 1234
Department: Engineering
Hire Date: 2025-01-15
Period: Hourly
Rate: $25.50/hour
```

### Badge System

Employees can clock in/out using:

- **Badge ID**: Scan or type badge number
- **PIN**: Optional security PIN after badge
- **Name Search**: Select from employee list

---

## 🔧 Advanced Configuration

### Database Location

By default, databases are stored in the executable directory:

**Server**:

```
[Server Directory]/server_bigtime.db
[Server Directory]/logs/server_*.log
```

**Client**:

```
[Client Directory]/bigtime.db
[Client Directory]/logs/client_*.log
[Client Directory]/logs/sync_*.log
```

### Custom Database Path

To use a custom database location, set environment variable:

```bash
# Windows
set BIGTIME_DATA_PATH=D:\BigTimeData

# Linux/macOS
export BIGTIME_DATA_PATH=/opt/bigtime/data
```

### Backup Strategy

**Automated** (recommended):

- Server creates daily backups at midnight
- Stored in `[Data Path]/backups/`
- Retention: 30 days

**Manual Backup**:

```bash
# Copy database files
copy server_bigtime.db server_bigtime_backup_YYYYMMDD.db
```

**Restore from Backup**:

1. Stop server/client
2. Replace current database with backup
3. Restart application

---

## 🌐 Network Configuration

### Same Machine Setup (Testing)

**Server**:

- Host: `127.0.0.1` or `localhost`
- Port: `5000`

**Client**:

- Server URL: `http://127.0.0.1:5000`

### Local Network Setup (Production)

**Server**:

- Host: `0.0.0.0` (all interfaces)
- Port: `5000`
- Static IP recommended (e.g., `192.168.1.100`)

**Client**:

- Server URL: `http://192.168.1.100:5000`

**Network Requirements**:

- All clients on same subnet as server
- No NAT/routing between client and server
- Firewall allows port 5000

### Internet/WAN Setup (Advanced)

**Server**:

- Public IP or DDNS hostname
- Port forwarding: External 5000 → Internal 5000
- Consider VPN or HTTPS reverse proxy for security

**Client**:

- Server URL: `http://[public-ip]:5000`
- VPN recommended for secure remote access

⚠️ **Security Warning**: BigTime uses HTTP (not HTTPS) by default. For internet deployments, use a reverse proxy (nginx, Apache) with SSL/TLS.

---

## 🔍 Verification

### Server Health Check

**From Browser**:

```
http://[server-ip]:5000/health
```

**Expected Response**:

```json
{
  "status": "ok",
  "timestamp": "2025-10-14T10:30:00Z"
}
```

**From Command Line**:

```bash
curl http://localhost:5000/health
```

### Client Connection Test

1. Open client application
2. Menu → Settings → Server Configuration
3. Click **"Test Connection"**
4. Should show: ✓ "Connected successfully"

### Sync Verification

1. Add employee on client
2. Wait 30 seconds (or trigger manual sync)
3. Check server database has the employee
4. Verify sync status indicator shows "Synced"

---

## 📊 Multi-Client Setup

### Scenario: Office with 3 Time Clocks

**Server** (Back office computer):

- IP: `192.168.1.100`
- Port: `5000`
- 3 API keys generated:
  - `client-reception` → `bt-abc123...`
  - `client-warehouse` → `bt-def456...`
  - `client-breakroom` → `bt-ghi789...`

**Client 1** (Reception):

- Device ID: `client-reception`
- API Key: `bt-abc123...`
- Server URL: `http://192.168.1.100:5000`

**Client 2** (Warehouse):

- Device ID: `client-warehouse`
- API Key: `bt-def456...`
- Server URL: `http://192.168.1.100:5000`

**Client 3** (Break Room):

- Device ID: `client-breakroom`
- API Key: `bt-ghi789...`
- Server URL: `http://192.168.1.100:5000`

All clients sync to the same server database.

---

## 🚨 Troubleshooting

### Server Won't Start

**Issue**: "Address already in use"

- **Cause**: Port 5000 is occupied
- **Solution**:
  - Change server port in settings
  - Or stop other application using port 5000
  - Check: `netstat -an | findstr :5000`

### Client Can't Connect

**Issue**: "Connection refused"

- **Check**:
  1. Server is running (check system tray)
  2. Correct server URL (IP address and port)
  3. Firewall allows port 5000
  4. Ping server: `ping [server-ip]`
  5. Test port: `telnet [server-ip] 5000`

**Issue**: "Invalid API key"

- **Solution**: Regenerate API key on server and update client

### Sync Not Working

**Check**:

1. Client shows "Online" status
2. Sync interval not zero
3. Server is accessible
4. Check sync logs: `logs/sync_*.log`

---

## 📞 Support

For setup assistance:

- Review [Troubleshooting Guide](TROUBLESHOOTING.md)
- Check application logs
- Review [API Documentation](API.md) for integration

---

**Last Updated**: October 14, 2025
**Version**: 2.0
