@echo off
title AIMScribe Recorder
echo ============================================================
echo AIMScribe Recorder - System Tray Application
echo ============================================================
echo.
echo Trigger Server: http://localhost:5050
echo Backend: http://localhost:6000
echo AIMS LAB Server: http://localhost:7000
echo.
echo Press Ctrl+C to stop, or use system tray icon to exit.
echo ============================================================
echo.

cd /d "%~dp0recorder"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".deps_installed" (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    echo. > .deps_installed
)

echo Starting recorder...
python main.py

pause
