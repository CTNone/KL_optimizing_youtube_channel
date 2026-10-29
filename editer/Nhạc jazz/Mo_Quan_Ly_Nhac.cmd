@echo off
cd /d "%~dp0"
if exist "%LocalAppData%\Programs\Python\Python311\pythonw.exe" (
  start "" "%LocalAppData%\Programs\Python\Python311\pythonw.exe" "%~dp0Music_Manager\app.py"
  exit /b
)
python "%~dp0Music_Manager\app.py"
if errorlevel 1 pause
