@echo off
REM BigTime Server - Disable Autostart (Windows)
REM This script removes BigTime Server from automatic startup

echo ===============================================
echo  BigTime Server - Disable Autostart
echo ===============================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found!
    echo Please install Python 3.9 or newer from python.org
    pause
    exit /b 1
)

REM Run the setup script
python setup_autostart.py --disable

echo.
echo ===============================================
pause
