@echo off
cd /d "%~dp0"
python -m finanzas.app
if errorlevel 1 pause
