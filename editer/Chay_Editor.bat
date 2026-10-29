@echo off
setlocal
pushd "%~dp0TOOL EDIT\v3\v3"
call run.bat
set "EDITOR_EXIT=%ERRORLEVEL%"
popd
exit /b %EDITOR_EXIT%
