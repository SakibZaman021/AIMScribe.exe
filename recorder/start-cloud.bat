@echo off
REM ================================================================
REM AIMScribe Recorder - Cloud Mode
REM Connects to remote backend (ngrok/Railway)
REM ================================================================

echo ============================================
echo    AIMScribe Recorder (Cloud Mode)
echo ============================================
echo.

REM Load cloud configuration
if exist "cloud_config.env" (
    echo [OK] Loading cloud configuration...
    for /f "tokens=1,2 delims==" %%a in (cloud_config.env) do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" (
            set "%%a=%%b"
        )
    )
) else (
    echo [ERROR] cloud_config.env not found!
    echo Please create cloud_config.env with your backend URL
    pause
    exit /b 1
)

echo.
echo    Backend URL: %AIMSCRIBE_BACKEND_URL%
echo.

REM Check backend connectivity
echo [1/2] Testing backend connection...
curl -s %AIMSCRIBE_BACKEND_URL%/health >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Cannot reach backend at %AIMSCRIBE_BACKEND_URL%
    echo           Make sure the backend is running!
    echo.
    pause
)

echo [2/2] Starting recorder...
echo.
echo ============================================
echo    Recorder Running (Cloud Mode)
echo    - System tray icon will appear
echo    - Ready to receive triggers from CMED
echo ============================================
echo.

python main.py

echo.
echo [INFO] Recorder stopped.
pause
