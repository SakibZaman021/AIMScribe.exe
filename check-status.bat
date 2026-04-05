@echo off
echo ============================================================
echo AIMScribe System - Status Check
echo ============================================================
echo.

echo [Recorder Status]
curl -s http://localhost:5050/status 2>nul
if errorlevel 1 (
    echo   Recorder: NOT RUNNING
) else (
    echo.
)

echo.
echo [AIMS LAB Server Status]
curl -s http://localhost:7000/health 2>nul
if errorlevel 1 (
    echo   AIMS LAB Server: NOT RUNNING
) else (
    echo.
)

echo.
echo [Backend API Status]
curl -s http://localhost:6000/health 2>nul
if errorlevel 1 (
    echo   Backend API: NOT RUNNING
) else (
    echo.
)

echo.
echo ============================================================
echo.

pause
