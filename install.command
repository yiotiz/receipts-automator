#!/bin/bash
echo "================================================"
echo " Receipt Scanner - First Time Setup"
echo "================================================"
echo ""

# Check Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python is not installed."
    echo ""
    echo "Please download and install Python from:"
    echo "https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Python found. Setting up..."
echo ""

# Move to the directory this script lives in
cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Install dependencies
echo "Installing dependencies (this may take a minute)..."
.venv/bin/pip install -r requirements.txt

# Create folders
mkdir -p input output failed

echo ""
echo "================================================"
echo " Setup complete!"
echo " You can now double-click run.command to start."
echo "================================================"
echo ""
read -p "Press Enter to exit..."
