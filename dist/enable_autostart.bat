@echo off
REM BigTime Server - Enable Autostart (Windows)
REM This script sets up BigTime Server to start automatically on system boot

echo ===============================================
echo  BigTime Server - Enable Autostart
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
python setup_autostart.py --enable

echo.
echo ===============================================
pause
