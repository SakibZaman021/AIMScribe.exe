@echo off
title AIMScribe Recorder - Install to Windows Startup
echo ============================================================
echo AIMScribe Recorder - Install to Windows Startup
echo ============================================================
echo.

cd /d "%~dp0"

set EXE_NAME=AIMScribe_Recorder.exe
set EXE_PATH=%~dp0dist\%EXE_NAME%
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

echo Checking executable...
if not exist "%EXE_PATH%" (
    echo.
    echo ERROR: %EXE_NAME% not found!
    echo.
    echo Please build the executable first by running:
    echo   BUILD.bat
    echo.
    pause
    exit /b 1
)

echo Found: %EXE_PATH%
echo.
echo Installing to Windows Startup...
echo Target: %STARTUP_FOLDER%
echo.

REM Create shortcut in Startup folder using PowerShell
powershell -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; ^
     $Shortcut = $WshShell.CreateShortcut('%STARTUP_FOLDER%\AIMScribe Recorder.lnk'); ^
     $Shortcut.TargetPath = '%EXE_PATH%'; ^
     $Shortcut.WorkingDirectory = '%~dp0dist'; ^
     $Shortcut.Description = 'AIMScribe Audio Recorder - System Tray Application'; ^
     $Shortcut.Save()"

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo SUCCESS!
    echo ============================================================
    echo.
    echo AIMScribe Recorder will now start automatically when Windows boots.
    echo.
    echo Shortcut created at:
    echo   %STARTUP_FOLDER%\AIMScribe Recorder.lnk
    echo.
    echo Starting AIMScribe Recorder now...
    start "" "%EXE_PATH%"
    echo.
    echo You should see a green icon in your system tray.
    echo The recorder is now listening on http://localhost:5050
    echo.
) else (
    echo.
    echo ERROR: Failed to create startup shortcut.
    echo Please try running this script as Administrator.
    echo.
)

pause
