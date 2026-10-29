@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv_flow\Scripts\python.exe" py -3.11 -m venv .venv_flow
if errorlevel 1 goto :failed

".venv_flow\Scripts\python.exe" -m pip install --upgrade pyinstaller
if errorlevel 1 goto :failed

if not exist "tools\ffmpeg.exe" goto :missing_ffmpeg
if not exist "tools\ffprobe.exe" goto :missing_ffprobe

rem Build and self-check in a staging folder; keep existing builds untouched until it passes.
if exist "build\tool_edit_candidate" rmdir /s /q "build\tool_edit_candidate"
mkdir "build\tool_edit_candidate"
if errorlevel 1 goto :failed

".venv_flow\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name ToolEdit ^
  --distpath "build\tool_edit_candidate\dist" ^
  --workpath "build\tool_edit_candidate\work" ^
  --specpath "build\tool_edit_candidate\spec" ^
  --add-binary "tools\ffmpeg.exe;tools" ^
  --add-binary "tools\ffprobe.exe;tools" ^
  --add-data "presets;presets" ^
  app.py
if errorlevel 1 goto :failed

set "CHECK_FILE=%TEMP%\tool_edit_candidate_selfcheck.json"
"build\tool_edit_candidate\dist\ToolEdit\ToolEdit.exe" --self-check "%CHECK_FILE%"
if errorlevel 1 goto :candidate_failed
if not exist "%CHECK_FILE%" goto :candidate_failed
del /q "%CHECK_FILE%"

rem Replace only ToolEdit; sibling tool builds and output folders remain untouched.
if exist "dist\ToolEdit" rmdir /s /q "dist\ToolEdit"
move "build\tool_edit_candidate\dist\ToolEdit" "dist\ToolEdit"
if errorlevel 1 goto :failed
echo Tool Edit da duoc cap nhat: dist\ToolEdit\ToolEdit.exe
pause
exit /b 0

:missing_ffmpeg
echo Thieu tools\ffmpeg.exe.
goto :failed

:missing_ffprobe
echo Thieu tools\ffprobe.exe.
goto :failed

:candidate_failed
echo Ban build moi chua qua self-check. Ban ToolEdit cu van duoc giu nguyen.
goto :failed

:failed
echo Build that bai. Ban ToolEdit hien tai khong bi thay the.
pause
exit /b 1
