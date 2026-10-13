@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON=venv\Scripts\python.exe"
if not exist "%PYTHON%" goto no_venv

if not defined SGC_API_PORT set "SGC_API_PORT=8000"
if not defined SGC_API_HOST set "SGC_API_HOST=127.0.0.1"
if not defined SGC_API_RELOAD set "SGC_API_RELOAD=0"
if not defined SGC_API_DOCS set "SGC_API_DOCS=0"

if not defined SGC_JWT_SECRET goto check_env
goto after_env_check

:check_env
if exist "backend\.env" (
    echo [INFO] Carregando backend\.env via python-dotenv na API.
) else (
    echo [AVISO] SGC_JWT_SECRET nao definido.
    echo         Copie backend\.env.example para backend\.env e gere o segredo.
    echo.
)

:after_env_check
set "PYTHONPATH=%CD%\backend;%CD%\python;%PYTHONPATH%"

netstat -ano | findstr /R /C:":%SGC_API_PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 goto port_busy
goto after_port

:port_busy
echo [AVISO] Porta %SGC_API_PORT% ja esta em uso.
echo         Defina outra: set SGC_API_PORT=8001
echo.

:after_port
echo ============================================================
echo SGC API  http://%SGC_API_HOST%:%SGC_API_PORT%
echo Reload=%SGC_API_RELOAD%  Docs=%SGC_API_DOCS%
echo ============================================================
echo.

if "%SGC_API_RELOAD%"=="1" goto run_reload
"%PYTHON%" -m uvicorn app.main:app --app-dir backend --host %SGC_API_HOST% --port %SGC_API_PORT%
goto after_run

:run_reload
"%PYTHON%" -m uvicorn app.main:app --app-dir backend --host %SGC_API_HOST% --port %SGC_API_PORT% --reload

:after_run
if errorlevel 1 goto api_fail
exit /b 0

:no_venv
echo [ERRO] Ambiente virtual nao encontrado: venv\Scripts\python.exe
echo Execute primeiro: setup_env.bat
echo Depois: venv\Scripts\python.exe -m pip install -r requirements-api.txt
pause
exit /b 1

:api_fail
echo.
echo [ERRO] A API encerrou com falha.
echo Verifique: venv\Scripts\python.exe -m pip install -r requirements-api.txt
pause
exit /b 1
