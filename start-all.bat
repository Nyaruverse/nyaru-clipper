@echo off
rem Nyaru Clipper single-process launcher (upstream architecture).
rem One window = one uvicorn process serving both API and Web UI on port 8787.
rem Closing this window stops the service. PYTHONDONTWRITEBYTECODE ensures latest code is loaded.

cd /d "%~dp0"

set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=

rem Open the Companion page after the server has a moment to bind the port.
start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8787/'"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev_companion.ps1"
pause
