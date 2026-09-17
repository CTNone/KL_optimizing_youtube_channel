@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo BUILD Quick Music Video Builder V2
echo ============================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Tao virtual environment...
    py -3.14 -m venv .venv
)

echo [2/5] Update pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo [3/5] Cai PyInstaller...
".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller pyinstaller-hooks-contrib

if not exist "tools\ffmpeg.exe" (
    echo.
    echo LOI: Khong tim thay tools\ffmpeg.exe
    echo Copy ffmpeg.exe va ffprobe.exe vao tools truoc khi build.
    pause
    exit /b 1
)

if not exist "tools\ffprobe.exe" (
    echo.
    echo LOI: Khong tim thay tools\ffprobe.exe
    pause
    exit /b 1
)

echo [4/5] Xoa build cu...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist QuickMusicVideoBuilderV2.spec del /q QuickMusicVideoBuilderV2.spec

echo [5/5] Build one-file EXE...
".venv\Scripts\python.exe" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name QuickMusicVideoBuilderV2 ^
  --add-binary "tools\ffmpeg.exe;tools" ^
  --add-binary "tools\ffprobe.exe;tools" ^
  app.py

echo.
echo ============================================
echo XONG:
echo dist\QuickMusicVideoBuilderV2.exe
echo ============================================
pause
