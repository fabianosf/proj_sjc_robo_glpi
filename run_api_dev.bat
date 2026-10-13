@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Desenvolvimento: reload + docs abertos
set "SGC_API_RELOAD=1"
set "SGC_API_DOCS=1"
if not defined SGC_API_PORT set "SGC_API_PORT=8001"
call "%~dp0run_api.bat"
