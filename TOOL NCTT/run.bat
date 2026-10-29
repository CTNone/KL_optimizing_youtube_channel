@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo ==================================================
  echo KHONG TIM THAY PYTHON.
  echo Cai Python 3.11+ tu python.org, sau do chay lai.
  echo ==================================================
  pause
  exit /b 1
)
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Khong cai duoc thu vien. Kiem tra Internet va thu lai.
  pause
  exit /b 1
)
%PY% app.py
pause
