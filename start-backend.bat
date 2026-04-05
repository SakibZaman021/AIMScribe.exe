@echo off
title AIMScribe Backend (Docker)
echo ============================================================
echo AIMScribe Backend - Docker Services
echo ============================================================
echo.
echo Starting: PostgreSQL, Redis, MinIO, API, Worker
echo API will be available at: http://localhost:6000
echo.
echo ============================================================
echo.

cd /d "D:\AIMS LAB REVIEW PAPER\aimscribe-backend\my_recorder_project"

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed or not in PATH
    pause
    exit /b 1
)

echo Starting Docker services...
docker-compose up -d

if errorlevel 1 (
    echo ERROR: Failed to start Docker services
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Backend services started successfully!
echo.
echo Services:
echo   - PostgreSQL: localhost:5432
echo   - Redis: localhost:6379
echo   - MinIO: localhost:9000 (Console: localhost:9001)
echo   - API: http://localhost:6000
echo ============================================================
echo.

pause
