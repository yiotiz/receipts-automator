@echo off

REM Check setup has been run
if not exist ".venv" (
    echo Setup has not been run yet.
    echo Please double-click install.bat first.
    pause
    exit /b 1
)

REM Launch the GUI
.venv\Scripts\python gui.py
