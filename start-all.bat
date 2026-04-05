@echo off
echo ============================================================
echo AIMScribe System - Starting All Components
echo ============================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM 1. Start Backend (Docker)
echo [1/4] Starting Backend (Docker)...
start "AIMScribe Backend" cmd /c "start-backend.bat"
timeout /t 10 /nobreak >nul

REM 2. Start AIMS LAB Server
echo [2/4] Starting AIMS LAB Server...
start "AIMS LAB Server" cmd /c "start-aimslab-server.bat"
timeout /t 3 /nobreak >nul

REM 3. Start Recorder
echo [3/4] Starting Recorder...
start "AIMScribe Recorder" cmd /c "start-recorder.bat"
timeout /t 3 /nobreak >nul

REM 4. Start CMED Web
echo [4/4] Starting CMED Web...
start "CMED Web" cmd /c "start-cmed.bat"
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo All components started!
echo.
echo Components:
echo   - Backend API: http://localhost:6000
echo   - AIMS LAB Server: http://localhost:7000
echo   - Recorder API: http://localhost:5050
echo   - CMED Web: http://localhost:3000
echo.
echo To stop all components:
echo   - Use Ctrl+C in each window, or
echo   - Run stop-all.bat
echo ============================================================
echo.

pause
