@echo off
title AIMScribe Recorder - Uninstall from Windows Startup
echo ============================================================
echo AIMScribe Recorder - Uninstall from Windows Startup
echo ============================================================
echo.

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT=%STARTUP_FOLDER%\AIMScribe Recorder.lnk

echo Checking for AIMScribe Recorder in Windows Startup...
echo.

if exist "%SHORTCUT%" (
    echo Found: %SHORTCUT%
    echo.
    echo Removing from Windows Startup...
    del "%SHORTCUT%"
    echo.
    echo SUCCESS! AIMScribe Recorder removed from Windows Startup.
) else (
    echo AIMScribe Recorder was not found in Windows Startup.
)

echo.
echo Stopping any running instances...
taskkill /IM AIMScribe_Recorder.exe /F 2>nul
if %errorlevel% equ 0 (
    echo AIMScribe Recorder process stopped.
) else (
    echo No running instance found.
)

echo.
echo ============================================================
echo Uninstall complete.
echo ============================================================
echo.
echo Note: The executable file was NOT deleted.
echo Location: %~dp0dist\AIMScribe_Recorder.exe
echo.
echo You can delete it manually if you no longer need it.
echo.
pause
