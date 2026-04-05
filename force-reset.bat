@echo off
echo ============================================================
echo AIMScribe Recorder - Force Reset
echo ============================================================
echo.
echo This will forcefully reset the recorder state.
echo Use this if CMED crashed and you cannot stop/start recording.
echo.
echo ============================================================
echo.

REM Call the force-reset endpoint
curl -X POST http://localhost:5050/force-reset

echo.
echo.
echo ============================================================
echo Force reset completed.
echo You can now trigger a new recording from CMED.
echo ============================================================
echo.

pause
