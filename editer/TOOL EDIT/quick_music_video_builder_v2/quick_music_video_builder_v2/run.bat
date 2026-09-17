@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Tao Python virtual environment...
    py -3.14 -m venv .venv
)

".venv\Scripts\python.exe" app.py
pause
