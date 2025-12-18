# BigTime Troubleshooting Guide

Common issues and solutions for BigTime Time Clock & Payroll Management System.

---

## 🔍 Table of Contents

1. [Server Issues](#server-issues)
2. [Client Issues](#client-issues)
3. [Sync Issues](#sync-issues)
4. [Database Issues](#database-issues)
5. [Network Issues](#network-issues)
6. [Build Issues](#build-issues)
7. [Performance Issues](#performance-issues)
8. [Logging & Debugging](#logging--debugging)

---

## 🖥️ Server Issues

### Server Won't Start

**Symptom**: Application exits immediately or shows error message

**Common Causes & Solutions**:

1. **Port Already in Use**:

   ```
   Error: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 5000): only one usage of each socket address
   ```

   **Solution**:

   ```bash
   # Check what's using port 5000
   netstat -ano | findstr :5000

   # Kill the process (Windows)
   taskkill /PID [process-id] /F

   # Or change server port in settings
   ```

2. **Database Locked**:

   ```
   Error: database is locked
   ```

   **Solution**:
   - Close any other instances of the server
   - Delete `server_bigtime.db-wal` and `server_bigtime.db-shm` files
   - Restart server

3. **Missing Dependencies**:

   ```
   ModuleNotFoundError: No module named 'waitress'
   ```

   **Solution**:

   ```bash
   pip install -r requirements.txt
   ```

### System Tray Icon Not Showing

**Symptom**: Server runs but no tray icon appears

**Solutions**:

1. **System Tray Disabled**:
   - Use console mode instead: `python launcher.py console-server`

2. **Display Server Not Available** (Linux):

   ```bash
   # Check DISPLAY variable
   echo $DISPLAY

   # Set if missing
   export DISPLAY=:0
   ```

3. **Run Console Mode**:

   ```bash
   python launcher.py console-server
   ```

### NTP Sync Failures

**Symptom**: Time sync errors in logs

**Solutions**:

1. **Firewall Blocking NTP**:

   ```bash
   # Allow UDP port 123 (NTP)
   # Windows
   netsh advfirewall firewall add rule name="NTP" dir=out action=allow protocol=UDP remoteport=123
   ```

2. **No Internet Connection**:
   - NTP sync is optional - server will use system time
   - Check logs for fallback message

3. **Change NTP Server**:
   - Server Settings → Time Sync → NTP Server
   - Try: `time.google.com` or `time.nist.gov`

---

## 💻 Client Issues

### Client Won't Start

**Symptom**: Application crashes on startup

**Solutions**:

1. **Corrupted Database**:

   ```bash
   # Backup and reset
   move bigtime.db bigtime.db.backup
   # Restart client - will create new database
   ```

2. **Missing Icon File**:

   ```
   Error: cannot load icon 'ico.ico'
   ```

   **Solution**:
   - Copy `ico.ico` to client directory
   - Or rebuild with: `pyinstaller BigTime-Client.spec`

3. **Qt Platform Plugin Error**:

   ```
   qt.qpa.plugin: Could not find the Qt platform plugin "windows"
   ```

   **Solution**:

   ```bash
   # Reinstall PyQt6
   pip uninstall PyQt6
   pip install PyQt6
   ```

### OOTB Setup Loop

**Symptom**: Setup wizard keeps appearing

**Solutions**:

1. **Check Manager Settings**:
   - Ensure manager name and PIN were saved
   - Check `bigtime.db` exists

2. **Reset and Redo Setup**:

   ```bash
   # Delete local settings
   DELETE FROM settings WHERE key IN ('manager_name', 'manager_pin');
   # Restart client
   ```

### PDF Generation Fails

**Symptom**: Error when generating paystubs

**Solutions**:

1. **Missing reportlab**:

   ```bash
   pip install reportlab
   ```

2. **Font Issues**:

   ```python
   # Check available fonts
   from reportlab.pdfbase import pdfmetrics
   print(pdfmetrics.getRegisteredFontNames())
   ```

3. **Permission Error**:
   - Ensure write access to output directory
   - Try running as administrator

---

## 🔄 Sync Issues

### "Sync Locked" Error

**Symptom**: Sync service shows "already syncing" or stuck

**Solutions**:

1. **Restart Client**:
   - Exit and restart application

2. **Manual Lock Reset**:

   ```sql
   -- In database
   UPDATE settings SET value='0' WHERE key='sync_locked';
   ```

3. **Check Logs**:

   ```
   logs/sync_YYYY-MM-DD.log
   ```

   - Look for stuck operations or exceptions

### Sync Never Completes

**Symptom**: Sync status shows "Syncing..." indefinitely

**Solutions**:

1. **Check Server Connection**:
   - Test: `curl http://[server]:5000/health`
   - Verify API key is correct

2. **Increase Timeout**:
   - Settings → Server Configuration → Timeout: 30 seconds

3. **Check Network Latency**:

   ```bash
   ping [server-ip]
   # Should be < 100ms for good sync performance
   ```

### Sync Conflicts

**Symptom**: "Conflict detected" errors

**Solutions**:

1. **Server Wins Strategy** (default):
   - Server changes overwrite client changes
   - Check logs for conflicted records

2. **Manual Resolution**:
   - Review conflict in logs
   - Edit record manually if needed

3. **Full Re-sync**:
   - Settings → Server Configuration → Save
   - Triggers full sync

### "Invalid API Key" Error

**Symptom**: 401 Unauthorized responses

**Solutions**:

1. **Regenerate API Key**:
   - Server: Right-click tray → Server Settings → API Keys
   - Generate new key for device
   - Client: Update key in settings

2. **Check Key Format**:
   - Should start with `bt-`
   - No spaces or special characters

3. **Verify Device ID**:
   - Ensure device ID matches server records

---

## 💾 Database Issues

### "Database is Locked" Error

**Symptom**: Cannot read/write database

**Solutions**:

1. **Close Other Instances**:

   ```bash
   # Windows - check running processes
   tasklist | findstr BigTime

   # Kill all instances
   taskkill /IM BigTime-Client.exe /F
   taskkill /IM BigTime-Server.exe /F
   ```

2. **Delete WAL Files**:

   ```bash
   del bigtime.db-wal
   del bigtime.db-shm
   ```

3. **Verify Database Integrity**:

   ```bash
   sqlite3 bigtime.db "PRAGMA integrity_check;"
   ```

### Database Corruption

**Symptom**: "Database disk image is malformed"

**Solutions**:

1. **Recover from Backup**:

   ```bash
   # Server creates daily backups
   copy backups\server_bigtime_YYYYMMDD.db server_bigtime.db
   ```

2. **Export and Recreate**:

   ```bash
   # Export data
   sqlite3 bigtime.db .dump > backup.sql

   # Create new database
   del bigtime.db
   sqlite3 bigtime.db < backup.sql
   ```

3. **Start Fresh** (last resort):

   ```bash
   # Backup old database
   move bigtime.db bigtime.db.corrupt
   # Restart application - creates new DB
   ```

### Missing Tables

**Symptom**: "Table not found" errors

**Solution**:

- Database not initialized properly
- Delete database and restart application
- Initialization will create all tables

---

## 🌐 Network Issues

### Client Can't Reach Server

**Symptom**: "Connection refused" or "Network unreachable"

**Diagnostic Steps**:

1. **Test Connectivity**:

   ```bash
   # Ping server
   ping [server-ip]

   # Test port
   telnet [server-ip] 5000

   # Or use curl
   curl http://[server-ip]:5000/health
   ```

2. **Check Firewall** (Server):

   ```powershell
   # Windows - check firewall rule
   netsh advfirewall firewall show rule name="BigTime Server"

   # If not exists, add rule
   netsh advfirewall firewall add rule name="BigTime Server" dir=in action=allow protocol=TCP localport=5000
   ```

3. **Verify Server is Listening**:

   ```bash
   # Check if port is open
   netstat -an | findstr :5000

   # Should show: 0.0.0.0:5000  LISTENING
   ```

### Slow Sync Performance

**Symptom**: Sync takes very long or times out

**Solutions**:

1. **Check Network Speed**:

   ```bash
   # Test bandwidth between client and server
   # Use iperf or similar tool
   ```

2. **Reduce Sync Interval**:
   - Settings → Sync Interval: 60 seconds (instead of 30)

3. **Optimize Database**:

   ```sql
   VACUUM;
   ANALYZE;
   ```

4. **Check Server Load**:
   - Look at CPU/memory usage
   - Reduce number of concurrent clients

### CORS Errors

**Symptom**: "Cross-origin request blocked"

**Solution**:

- Flask-CORS is already enabled
- Check if using correct URL (IP vs hostname)
- Ensure no proxy between client and server

---

## 🔨 Build Issues

### PyInstaller Build Fails

**Symptom**: Build errors or warnings

**Common Issues**:

1. **Missing Hidden Imports**:

   ```
   ImportError: No module named 'waitress'
   ```

   **Solution**: Already fixed in `.spec` files
   - Check `hiddenimports` in spec file

2. **UPX Compression Fails**:

   ```
   Cannot find upx
   ```

   **Solution**:

   ```python
   # In .spec file, set:
   upx=False,
   ```

3. **Too Many Warnings**:
   - Most warnings are harmless
   - Check `warn-*.txt` in build folder for details

### Executable Won't Run

**Symptom**: Built executable crashes or shows error

**Solutions**:

1. **Test in Console**:

   ```bash
   # Run from command line to see errors
   BigTime-Client.exe
   ```

2. **Missing DLLs**:
   - Ensure PyQt6 is properly included
   - Rebuild with `--clean` flag

3. **Antivirus Blocking**:
   - Some antivirus flags PyInstaller executables
   - Add exception for BigTime executables

### Build Size Too Large

**Symptom**: Executable is > 200 MB

**Solutions**:

1. **Already Optimized**:
   - Excludes: tkinter, matplotlib, numpy, PIL
   - Client excludes server deps (flask, waitress)

2. **Further Optimization**:

   ```python
   # In .spec file, add more excludes
   excludes=['email', 'xml', 'html', ...],
   ```

3. **Use OneDirBuild** (faster):
   - Change `exe = EXE(...` to create folder instead of single file
   - Slightly faster startup

---

## ⚡ Performance Issues

### Slow Startup

**Solutions**:

1. **Large Database**:
   - Archive old records
   - Vacuum database regularly

2. **Many Fonts Loaded**:
   - Reduce custom fonts in `ui/fonts.py`

3. **Antivirus Scanning**:
   - Exclude BigTime directory from real-time scanning

### High CPU Usage

**Solutions**:

1. **Sync Running Too Frequently**:
   - Increase sync interval to 60+ seconds

2. **Too Many Clients**:
   - Server handles ~10-20 clients comfortably
   - For more, consider load balancing

3. **Database Not Optimized**:

   ```sql
   VACUUM;
   REINDEX;
   ```

### High Memory Usage

**Solutions**:

1. **Memory Leak in Logs**:
   - Log rotation is enabled by default
   - Check if old logs are being held in memory

2. **Too Many Records Loaded**:
   - Add pagination to employee lists
   - Limit time log queries to date ranges

---

## 📝 Logging & Debugging

### Enable Debug Logging

**Client**:

```python
# In shared/logging_config.py
# Change level from INFO to DEBUG
logger.setLevel(logging.DEBUG)
```

**Server**:

```python
# Same as above
```

### Log Locations

```
logs/
├── client_2025-10-14.log    # Client application
├── server_2025-10-14.log    # Server application
└── sync_2025-10-14.log      # Sync service
```

### Reading Logs

**Look for**:

- `ERROR` - Serious issues
- `WARNING` - Potential problems
- `INFO` - Normal operations
- `DEBUG` - Detailed debugging

**Example**:

```
2025-10-14 10:30:45 ERROR [sync] Failed to connect to server: Connection refused
2025-10-14 10:30:46 INFO [sync] Retrying in 30 seconds...
```

### Common Log Messages

| Message              | Meaning                       | Action                       |
| -------------------- | ----------------------------- | ---------------------------- |
| `Connection refused` | Server not running/accessible | Check server, firewall       |
| `Invalid API key`    | Authentication failed         | Regenerate key               |
| `Database is locked` | Concurrent access issue       | Restart application          |
| `Already syncing`    | Sync in progress              | Wait or check for stuck sync |
| `NTP sync failed`    | Time sync unavailable         | Optional - check internet    |

---

## 🆘 Getting Help

### Before Requesting Support

1. **Check logs** for error messages
2. **Try common solutions** from this guide
3. **Test basic connectivity** (ping, curl)
4. **Verify configuration** (settings match requirements)

### Information to Provide

When reporting issues, include:

- **Version**: BigTime 2.1.2
- **OS**: Windows 11, macOS 12, etc.
- **Error message**: Exact text from error dialog or log
- **Steps to reproduce**: What you did before error
- **Logs**: Relevant log file excerpts
- **Configuration**: Server URL, settings (no API keys!)

### Log Submission

```bash
# Collect relevant logs
copy logs\client_*.log support_logs\
copy logs\sync_*.log support_logs\
copy logs\server_*.log support_logs\
```

---

## 📊 Diagnostic Checklist

Use this checklist to diagnose issues:

- [ ] Application version is 2.1.2
- [ ] All dependencies installed (`pip list`)
- [ ] Server is running and accessible
- [ ] Firewall allows server port
- [ ] Database files exist and not corrupted
- [ ] API key is valid and correctly entered
- [ ] Network connectivity between client/server
- [ ] Sufficient disk space (> 1 GB free)
- [ ] No other instances running
- [ ] Logs show no critical errors
- [ ] System time is correct (important for sync)

---

**Last Updated**: December 11, 2025
**Version**: 2.1.2
