@echo off
echo ================================================
echo  Receipt Scanner - First Time Setup
echo ================================================
echo.

REM Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed.
    echo.
    echo Please download and install Python from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to tick "Add Python to PATH" during installation.
    echo Then run this file again.
    pause
    exit /b 1
)

echo Python found. Setting up...
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Install dependencies
echo Installing dependencies (this may take a minute)...
.venv\Scripts\pip install -r requirements.txt

REM Create folders
if not exist "input" mkdir input
if not exist "output" mkdir output
if not exist "failed" mkdir failed

echo.
echo ================================================
echo  Setup complete!
echo  You can now double-click run.bat to start.
echo ================================================
echo.
pause
