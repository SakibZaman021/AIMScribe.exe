@echo off
REM ================================================================
REM AIMScribe Client Demo - Quick Start
REM Starts Recorder + CMED Web for cloud backend demo
REM ================================================================

echo ============================================
echo    AIMScribe Demo - Quick Start
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.11+
    pause
    exit /b 1
)

REM Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found! Please install Node.js 18+
    pause
    exit /b 1
)

REM Check cloud config
if not exist "recorder\cloud_config.env" (
    echo [ERROR] recorder\cloud_config.env not found!
    echo Please configure the backend URL first.
    pause
    exit /b 1
)

echo [1/3] Reading configuration...
cd recorder
for /f "tokens=1,2 delims==" %%a in (cloud_config.env) do (
    if "%%a"=="AIMSCRIBE_BACKEND_URL" set "BACKEND_URL=%%b"
)
cd ..

echo    Backend: %BACKEND_URL%
echo.

echo [2/3] Starting Recorder (system tray)...
start "AIMScribe Recorder" cmd /k "cd recorder && python main.py"
timeout /t 3 /nobreak >nul

echo [3/3] Starting CMED Web Dashboard...
start "CMED Web" cmd /k "cd cmed-web && set NEXT_PUBLIC_BACKEND_URL=%BACKEND_URL% && npm run dev"

echo.
echo ============================================
echo    Demo Started Successfully!
echo ============================================
echo.
echo    CMED Dashboard: http://localhost:3000
echo    Recorder: Running in system tray
echo    Backend: %BACKEND_URL%
echo.
echo    Close this window to stop the demo.
echo    (Also close the Recorder and CMED windows)
echo ============================================
echo.

pause
