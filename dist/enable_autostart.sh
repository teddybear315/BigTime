#!/bin/bash
# BigTime Server - Enable Autostart (Linux/macOS)
# This script sets up BigTime Server to start automatically on system boot

echo "==============================================="
echo " BigTime Server - Enable Autostart"
echo "==============================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 not found!"
    echo "   Please install Python 3.9 or newer"
    exit 1
fi

# Run the setup script
python3 setup_autostart.py --enable

echo ""
echo "==============================================="
