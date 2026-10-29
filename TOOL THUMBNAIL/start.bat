@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto error
.venv\Scripts\python.exe flow_tool.py
if errorlevel 1 goto error
exit /b 0
:error
echo Khong khoi dong duoc. Xem loi ben tren.
pause
