@echo off
title AIMS LAB Audio Server
echo ============================================================
echo AIMS LAB Audio Server
echo ============================================================
echo.
echo This server receives audio files from doctor PCs
echo and stores them in D:\AIMSLAB_AUDIO_STORAGE
echo.
echo Server will run on: http://0.0.0.0:7000
echo ============================================================
echo.

cd /d "%~dp0"

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
    echo. > .deps_installed
)

echo Starting server...
python main.py

pause
