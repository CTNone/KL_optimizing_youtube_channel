@echo off
cd /d "%~dp0"
title Quick Music Video Builder V2

echo ====================================================
echo  Quick Music Video Builder V2
echo  Thu muc: %CD%
echo ====================================================
echo.

if not exist "app.py" goto :noapp
goto :findpy

:noapp
  echo [LOI] Thieu app.py trong %CD%
  pause
  exit /b 1

:findpy
rem Uu tien moi truong da co trong project, nhung bo qua .venv bi hong.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version >nul 2>&1
  if not errorlevel 1 goto :usevenv
  echo [!] .venv khong dung duoc, dung Python he thong.
)

echo Dang tim Python...
echo ----------------------------------------------------
echo Thu lenh: py
py --version
if not errorlevel 1 goto :usepy
echo [x] khong co lenh py
echo ----------------------------------------------------
echo Thu lenh: python
python --version
if not errorlevel 1 goto :usepython
echo [x] khong co lenh python
echo ----------------------------------------------------
echo Thu lenh: python3
python3 --version
if not errorlevel 1 goto :usepython3
echo [x] khong co lenh python3

echo [LOI] Khong tim thay Python.
echo Cai Python 3.10+ tu https://www.python.org/downloads/
echo Nho tick "Add python.exe to PATH".
pause
exit /b 1

:usepy
echo Chay: py app.py
py app.py
set EXITCODE=%ERRORLEVEL%
goto :done

:usevenv
echo Chay bang Python trong .venv
".venv\Scripts\python.exe" app.py
set EXITCODE=%ERRORLEVEL%
goto :done

:usepython
echo Chay: python app.py
python app.py
set EXITCODE=%ERRORLEVEL%
goto :done

:usepython3
echo Chay: python3 app.py
python3 app.py
set EXITCODE=%ERRORLEVEL%
goto :done

:done
echo.
echo Thoat voi ma: %EXITCODE%
pause
exit /b %EXITCODE%
