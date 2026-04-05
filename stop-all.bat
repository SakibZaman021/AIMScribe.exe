@echo off
echo ============================================================
echo AIMScribe System - Stopping All Components
echo ============================================================
echo.

REM Stop Docker services
echo Stopping Docker services...
cd /d "D:\AIMS LAB REVIEW PAPER\aimscribe-backend\my_recorder_project"
docker-compose down

REM Kill Python processes (recorder, aimslab-server)
echo Stopping Python processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq AIMScribe*" >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE eq AIMS LAB*" >nul 2>&1

REM Kill Node processes (cmed-web)
echo Stopping Node processes...
taskkill /F /IM node.exe /FI "WINDOWTITLE eq CMED*" >nul 2>&1

echo.
echo ============================================================
echo All components stopped.
echo ============================================================
echo.

pause
