#!/bin/bash

# Move to the directory this script lives in
cd "$(dirname "$0")"

# Check setup has been run
if [ ! -d ".venv" ]; then
    echo "Setup has not been run yet."
    echo "Please double-click install.command first."
    read -p "Press Enter to exit..."
    exit 1
fi

# Launch the GUI
.venv/bin/python gui.py
