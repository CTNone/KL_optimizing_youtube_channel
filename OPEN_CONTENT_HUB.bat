@echo off
cd /d "%~dp0CONTENT HUB"
rem Run the current source so the launcher cannot silently open an older packaged build.
py app.py
if errorlevel 1 pause
