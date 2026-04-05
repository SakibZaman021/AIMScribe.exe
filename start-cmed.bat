@echo off
title CMED Web Frontend
echo ============================================================
echo CMED Web - Doctor Dashboard
echo ============================================================
echo.
echo Frontend will run on: http://localhost:3000
echo.
echo Press Ctrl+C to stop.
echo ============================================================
echo.

cd /d "%~dp0cmed-web"

REM Check if Node.js is available
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist "node_modules" (
    echo Installing dependencies...
    npm install
    if errorlevel 1 (
        echo ERROR: Failed to install npm dependencies
        pause
        exit /b 1
    )
)

echo Starting CMED Web...
npm run dev

pause
