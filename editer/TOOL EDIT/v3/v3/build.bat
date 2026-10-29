@echo off
setlocal
cd /d "%~dp0"
call build_flow.bat
exit /b %ERRORLEVEL%
