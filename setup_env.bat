@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo SGC - criacao/atualizacao do ambiente virtual (Windows)
echo ============================================================

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    set "PY_BOOT=py -3"
) else (
    set "PY_BOOT=python"
)

if not exist "venv\Scripts\python.exe" (
    echo.
    echo [1/3] Criando venv...
    %PY_BOOT% -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar venv. Instale Python 3.10+ e tente novamente.
        exit /b 1
    )
) else (
    echo.
    echo [1/3] venv ja existe — reutilizando.
)

set "PYTHON=venv\Scripts\python.exe"
set "PIP=venv\Scripts\pip.exe"

echo.
echo [2/3] Atualizando pip...
"%PYTHON%" -m pip install --upgrade pip

echo.
echo [3/3] Instalando dependencias (requirements.txt)...
"%PIP%" install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    exit /b 1
)

echo.
echo [OK] Ambiente pronto. Inicie com: run.bat
echo      Ou execute scripts: sgc_python.bat python\VerificarFase2Local.py
echo ============================================================
