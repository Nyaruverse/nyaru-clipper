@echo off
rem One-click installer: idempotent, safe to re-run.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
pause
