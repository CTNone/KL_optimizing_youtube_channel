@echo off
setlocal
set "HUB_DIR=%~dp0CONTENT HUB"
cd /d "%HUB_DIR%"
py app.py
if errorlevel 1 pause
