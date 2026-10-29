@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv_build\Scripts\python.exe" py -m venv .venv_build
if errorlevel 1 goto :failed
".venv_build\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto :failed
".venv_build\Scripts\python.exe" -m PyInstaller --noconfirm --onedir --windowed --name YouTubeContentHub --paths "..\editer\TOOL EDIT\v3\v3" --add-binary "..\editer\TOOL EDIT\v3\v3\tools\ffmpeg.exe;tools" --add-binary "..\editer\TOOL EDIT\v3\v3\tools\ffprobe.exe;tools" app.py
if errorlevel 1 goto :failed
echo EXE: dist\YouTubeContentHub\YouTubeContentHub.exe
pause
exit /b 0
:failed
echo Build failed. See error above.
pause
exit /b 1
