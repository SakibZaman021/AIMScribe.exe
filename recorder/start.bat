@echo off
REM ================================================================
REM AIMScribe Recorder - Start Script
REM ================================================================

echo ============================================
echo    AIMScribe Recorder (System Tray)
echo ============================================
echo.

cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [1/3] Virtual environment found
)

REM Activate virtual environment
echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
if not exist "venv\Lib\site-packages\fastapi" (
    echo [3/3] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [WARNING] Some packages may have failed
    )
    echo [OK] Dependencies installed
) else (
    echo [3/3] Dependencies already installed
)

echo.
echo ============================================
echo    Starting AIMScribe Recorder...
echo    Trigger API: http://localhost:5050
echo ============================================
echo.

python main.py

pause
