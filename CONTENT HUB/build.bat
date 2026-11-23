@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
if not exist ".venv_build\Scripts\python.exe" py -m venv .venv_build
if errorlevel 1 goto :failed
".venv_build\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto :failed
for /f "delims=" %%i in ('py -c "import sys; print(sys.base_prefix)"') do set "PY_BASE=%%i"
if not exist "%PY_BASE%\tcl\tcl8.6\init.tcl" (
    echo Tcl/Tk not found under %PY_BASE%. Install Python with tkinter and rebuild.
    goto :failed
)
set "TCL_LIBRARY=%PY_BASE%\tcl\tcl8.6"
set "TK_LIBRARY=%PY_BASE%\tcl\tk8.6"
".venv_build\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name YouTubeContentHub app.py
if errorlevel 1 goto :failed
echo EXE: dist\YouTubeContentHub\YouTubeContentHub.exe
pause
exit /b 0
:failed
echo Build failed. See error above.
pause
exit /b 1
