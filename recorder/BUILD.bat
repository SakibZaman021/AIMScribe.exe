@echo off
title AIMScribe Recorder - Build
echo ============================================================
echo AIMScribe Recorder - Build Windows Executable
echo ============================================================
echo.

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [2/4] Installing PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller
    pause
    exit /b 1
)

echo.
echo [3/4] Cleaning previous builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo.
echo [4/4] Building executable...
echo This may take a few minutes...
echo.

pyinstaller ^
    --name=AIMScribe_Recorder ^
    --onefile ^
    --windowed ^
    --hidden-import=pystray._win32 ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=uvicorn.logging ^
    --hidden-import=uvicorn.loops ^
    --hidden-import=uvicorn.loops.auto ^
    --hidden-import=uvicorn.protocols ^
    --hidden-import=uvicorn.protocols.http ^
    --hidden-import=uvicorn.protocols.http.auto ^
    --hidden-import=uvicorn.protocols.websockets ^
    --hidden-import=uvicorn.protocols.websockets.auto ^
    --hidden-import=uvicorn.protocols.websockets.wsproto_impl ^
    --hidden-import=uvicorn.protocols.websockets.websockets_impl ^
    --hidden-import=uvicorn.lifespan ^
    --hidden-import=uvicorn.lifespan.on ^
    --hidden-import=asyncio ^
    --hidden-import=aiohttp ^
    --hidden-import=fastapi ^
    --hidden-import=pydantic ^
    --hidden-import=pyaudio ^
    --hidden-import=websockets ^
    --hidden-import=wsproto ^
    --hidden-import=starlette.websockets ^
    --exclude-module=PyQt5 ^
    --exclude-module=PyQt6 ^
    --exclude-module=matplotlib ^
    --exclude-module=IPython ^
    --exclude-module=tkinter ^
    --collect-all=pystray ^
    --collect-all=PIL ^
    main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo BUILD SUCCESSFUL!
echo ============================================================
echo.
echo Executable created at:
echo   %~dp0dist\AIMScribe_Recorder.exe
echo.
echo Next steps:
echo   1. Run: install_autostart.bat (to auto-start with Windows)
echo   2. Or run the .exe directly
echo.
pause
