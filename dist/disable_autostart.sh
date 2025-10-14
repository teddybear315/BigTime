#!/bin/bash
# BigTime Server - Disable Autostart (Linux/macOS)
# This script removes BigTime Server from automatic startup

echo "==============================================="
echo " BigTime Server - Disable Autostart"
echo "==============================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 not found!"
    echo "   Please install Python 3.9 or newer"
    exit 1
fi

# Run the setup script
python3 setup_autostart.py --disable

echo ""
echo "==============================================="
