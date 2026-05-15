@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "scripts\backup_database.ps1"
pause
