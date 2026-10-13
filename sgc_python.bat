@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERRO] Ambiente virtual nao encontrado: %PYTHON%
    echo Execute primeiro: setup_env.bat
    exit /b 1
)

"%PYTHON%" %*
