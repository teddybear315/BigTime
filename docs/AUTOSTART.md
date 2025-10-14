# Autostart Setup - Additional Requirements

The autostart setup script requires some additional Python packages on Windows.

**Location**: All autostart files are located in the `dist/` folder.

## Windows Requirements

Install the required packages:

```bash
pip install pywin32 winshell
```

Or install all requirements at once:

```bash
pip install -r requirements.txt
pip install pywin32 winshell
```

## Linux/macOS Requirements

No additional packages required. The script uses standard Python libraries.

## Usage

### Simple (Recommended)

**Windows**:

1. Navigate to the `dist` folder
2. Double-click `enable_autostart.bat` to enable autostart
3. Double-click `disable_autostart.bat` to disable autostart

**Linux/macOS**:

```bash
cd dist
chmod +x enable_autostart.sh disable_autostart.sh
./enable_autostart.sh    # Enable
./disable_autostart.sh   # Disable
```

### Advanced

```bash
# Navigate to dist folder
cd dist

# Enable with auto-detected executable
python setup_autostart.py --enable

# Enable with custom path
python setup_autostart.py --enable --executable /path/to/BigTime-Server.exe

# Disable autostart
python setup_autostart.py --disable
```

## How It Works

### Windows

- Creates a shortcut in the Windows Startup folder
- Location: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BigTime Server.lnk`
- Server will start when user logs in

### macOS

- Creates a LaunchAgent plist file
- Location: `~/Library/LaunchAgents/com.scrllc.bigtime.server.plist`
- Logs: `~/Library/Logs/BigTime-Server.log`
- Server will start when user logs in

### Linux

- Creates a .desktop file in autostart directory
- Location: `~/.config/autostart/bigtime-server.desktop`
- Server will start when user logs in to desktop environment

## Troubleshooting

### Windows: "Module not found" error

Install the required modules:

```bash
pip install pywin32 winshell
```

### macOS: Permission denied

Make the script executable:

```bash
chmod +x enable_autostart.sh
```

### Linux: Server doesn't start

1. Check executable permissions:

   ```bash
   chmod +x dist/BigTime-Server
   ```

2. Check the .desktop file:

   ```bash
   cat ~/.config/autostart/bigtime-server.desktop
   ```

3. Test manually:

   ```bash
   ./dist/BigTime-Server
   ```

### Verify Autostart is Enabled

**Windows**:

- Open `shell:startup` in Windows Explorer
- Check for "BigTime Server.lnk" shortcut

**macOS**:

```bash
launchctl list | grep bigtime
```

**Linux**:

```bash
ls ~/.config/autostart/bigtime-server.desktop
```
