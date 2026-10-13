@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON=venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERRO] venv nao encontrado. Rode setup_env.bat
    pause
    exit /b 1
)

REM --- IP da LAN (primeiro IPv4 nao-loopback) ---
set "LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Sort-Object -Property InterfaceMetric | Select-Object -ExpandProperty IPAddress -First 1"`) do set "LAN_IP=%%I"
if not defined LAN_IP set "LAN_IP=SEU_IP"

set "SGC_API_HOST=0.0.0.0"
if not defined SGC_API_PORT set "SGC_API_PORT=8001"
set "SGC_API_RELOAD=0"
set "SGC_API_DOCS=1"
set "SGC_SERVE_FRONTEND=1"
set "PYTHONPATH=%CD%\backend;%CD%\python;%PYTHONPATH%"

echo.
echo ============================================================
echo  SGC no celular (mesma Wi-Fi do PC)
echo ============================================================
echo.

where npm >nul 2>&1
if errorlevel 1 (
    echo [AVISO] npm nao encontrado — usando frontend\dist atual (se existir).
    goto after_build
)

echo [1/3] Build do frontend (API na mesma origem^)...
pushd frontend
call npm run build
if errorlevel 1 (
    popd
    echo [ERRO] npm run build falhou.
    pause
    exit /b 1
)
popd

:after_build
if not exist "frontend\dist\index.html" (
    echo [ERRO] frontend\dist ausente. Instale Node.js e rode: cd frontend ^&^& npm run build
    pause
    exit /b 1
)

echo [2/3] Se o celular nao abrir, rode como Administrador:
echo         abrir_firewall_mobile.bat
echo.

echo [3/3] Subindo API em 0.0.0.0:%SGC_API_PORT% com frontend...
echo.
echo   No celular, abra o navegador:
echo.
echo      http://%LAN_IP%:%SGC_API_PORT%/
echo.
echo   PC e celular na MESMA Wi-Fi. Login = matricula + senha Windows.
echo   CTRL+C para parar.
echo ============================================================
echo.

"%PYTHON%" -m uvicorn app.main:app --app-dir backend --host %SGC_API_HOST% --port %SGC_API_PORT%
if errorlevel 1 (
    echo [ERRO] API encerrou com falha.
    pause
    exit /b 1
)
exit /b 0
