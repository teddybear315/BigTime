#!/usr/bin/env python3
"""
BigTime Server - Autostart Setup Script

This script creates a startup shortcut for the BigTime Server executable
to automatically launch when the system boots.

Supports:
- Windows: Creates shortcut in Startup folder
- macOS: Creates LaunchAgent plist file
- Linux: Creates .desktop file in autostart directory

Usage:
    python setup_autostart.py [--enable|--disable] [--executable PATH]
"""

import argparse
import os
import platform
import sys
from pathlib import Path


def get_server_executable_path():
    """Find the BigTime-Server executable in the dist folder"""
    # Script is now located in dist folder
    script_dir = Path(__file__).parent.resolve()

    system = platform.system()

    if system == "Windows":
        # Look for Win11 subfolder or in same directory
        exe_path = script_dir / "Win11" / "BigTime-Server.exe"
        if not exe_path.exists():
            exe_path = script_dir / "BigTime-Server.exe"
    elif system == "Darwin":  # macOS
        # Look for MacOS subfolder
        exe_path = script_dir / "MacOS" / "BigTime-Server.app" / "Contents" / "MacOS" / "BigTime-Server"
        # Also check for standalone binary
        if not exe_path.exists():
            exe_path = script_dir / "BigTime-Server.app" / "Contents" / "MacOS" / "BigTime-Server"
        if not exe_path.exists():
            exe_path = script_dir / "BigTime-Server"
    else:  # Linux
        # Look for Linux subfolder or in same directory
        exe_path = script_dir / "Linux" / "BigTime-Server"
        if not exe_path.exists():
            exe_path = script_dir / "BigTime-Server"

    return exe_path


def setup_windows_autostart(executable_path, enable=True):
    """Create or remove Windows startup shortcut"""
    import winshell
    from win32com.client import Dispatch

    startup_folder = Path(winshell.startup())
    shortcut_path = startup_folder / "BigTime Server.lnk"

    if enable:
        if not executable_path.exists():
            print(f"❌ Error: Executable not found at {executable_path}")
            print(f"   Please build the server executable first using:")
            print(f"   pyinstaller BigTime-Server.spec")
            return False

        # Create shortcut
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.TargetPath = str(executable_path)
        shortcut.WorkingDirectory = str(executable_path.parent)
        shortcut.Description = "BigTime Server - Time Clock & Payroll System"
        shortcut.IconLocation = str(executable_path)
        shortcut.save()

        print(f"✅ Autostart enabled!")
        print(f"   Shortcut created: {shortcut_path}")
        print(f"   Target: {executable_path}")
        print(f"\n   BigTime Server will start automatically on system boot.")
        return True
    else:
        # Remove shortcut
        if shortcut_path.exists():
            shortcut_path.unlink()
            print(f"✅ Autostart disabled!")
            print(f"   Removed: {shortcut_path}")
            return True
        else:
            print(f"ℹ️  No autostart shortcut found.")
            return False


def setup_macos_autostart(executable_path, enable=True):
    """Create or remove macOS LaunchAgent"""
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)

    plist_path = launch_agents_dir / "com.scrllc.bigtime.server.plist"

    if enable:
        if not executable_path.exists():
            print(f"❌ Error: Executable not found at {executable_path}")
            print(f"   Please build the server executable first using:")
            print(f"   pyinstaller BigTime-Server.spec")
            return False

        # Create plist file
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.scrllc.bigtime.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>{executable_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>WorkingDirectory</key>
    <string>{executable_path.parent}</string>
    <key>StandardOutPath</key>
    <string>{Path.home()}/Library/Logs/BigTime-Server.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/Library/Logs/BigTime-Server-error.log</string>
</dict>
</plist>
"""

        plist_path.write_text(plist_content)

        # Load the launch agent
        os.system(f"launchctl load {plist_path}")

        print(f"✅ Autostart enabled!")
        print(f"   LaunchAgent created: {plist_path}")
        print(f"   Target: {executable_path}")
        print(f"\n   BigTime Server will start automatically on login.")
        print(f"\n   To manually start now:")
        print(f"   launchctl start com.scrllc.bigtime.server")
        return True
    else:
        # Unload and remove plist
        if plist_path.exists():
            os.system(f"launchctl unload {plist_path}")
            plist_path.unlink()
            print(f"✅ Autostart disabled!")
            print(f"   Removed: {plist_path}")
            return True
        else:
            print(f"ℹ️  No autostart LaunchAgent found.")
            return False


def setup_linux_autostart(executable_path, enable=True):
    """Create or remove Linux autostart .desktop file"""
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)

    desktop_path = autostart_dir / "bigtime-server.desktop"

    if enable:
        if not executable_path.exists():
            print(f"❌ Error: Executable not found at {executable_path}")
            print(f"   Please build the server executable first using:")
            print(f"   pyinstaller BigTime-Server.spec")
            return False

        # Make executable if not already
        executable_path.chmod(0o755)

        # Create .desktop file
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=BigTime Server
Comment=BigTime Server - Time Clock & Payroll System
Exec={executable_path}
Path={executable_path.parent}
Icon={executable_path.parent / 'ico.ico'}
Terminal=false
Categories=Office;
X-GNOME-Autostart-enabled=true
"""

        desktop_path.write_text(desktop_content)
        desktop_path.chmod(0o755)

        print(f"✅ Autostart enabled!")
        print(f"   Desktop file created: {desktop_path}")
        print(f"   Target: {executable_path}")
        print(f"\n   BigTime Server will start automatically on login.")
        return True
    else:
        # Remove desktop file
        if desktop_path.exists():
            desktop_path.unlink()
            print(f"✅ Autostart disabled!")
            print(f"   Removed: {desktop_path}")
            return True
        else:
            print(f"ℹ️  No autostart .desktop file found.")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Setup BigTime Server to start automatically on system boot"
    )
    parser.add_argument(
        '--enable',
        action='store_true',
        help='Enable autostart (default)'
    )
    parser.add_argument(
        '--disable',
        action='store_true',
        help='Disable autostart'
    )
    parser.add_argument(
        '--executable',
        type=Path,
        help='Path to BigTime-Server executable (auto-detected if not provided)'
    )

    args = parser.parse_args()

    # Determine enable/disable
    if args.disable:
        enable = False
    else:
        enable = True  # Default to enable

    # Get executable path
    if args.executable:
        executable_path = args.executable.resolve()
    else:
        executable_path = get_server_executable_path()

    print("=" * 60)
    print("BigTime Server - Autostart Setup")
    print("=" * 60)
    print(f"Operating System: {platform.system()}")
    print(f"Action: {'ENABLE' if enable else 'DISABLE'} autostart")
    print(f"Executable: {executable_path}")
    print("-" * 60)

    # Platform-specific setup
    system = platform.system()
    success = False

    try:
        if system == "Windows":
            # Check for required Windows modules
            try:
                import winshell
                import win32com.client
            except ImportError:
                print("❌ Error: Required modules not installed for Windows.")
                print("\n   Install with:")
                print("   pip install pywin32 winshell")
                return 1

            success = setup_windows_autostart(executable_path, enable)

        elif system == "Darwin":  # macOS
            success = setup_macos_autostart(executable_path, enable)

        elif system == "Linux":
            success = setup_linux_autostart(executable_path, enable)

        else:
            print(f"❌ Error: Unsupported operating system: {system}")
            return 1

        print("=" * 60)
        if success:
            return 0
        else:
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
