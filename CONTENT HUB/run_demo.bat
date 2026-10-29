@echo off
cd /d "%~dp0"
py app.py --demo
if errorlevel 1 pause
