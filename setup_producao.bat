@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo SGC — setup producao (worker + API)
echo ============================================================

call "%~dp0setup_env.bat"
if errorlevel 1 exit /b 1

echo.
echo [API] Instalando requirements-api.txt ...
venv\Scripts\python.exe -m pip install -r requirements-api.txt
if errorlevel 1 (
  echo [ERRO] Falha ao instalar requirements-api.txt
  exit /b 1
)

echo.
echo [OK] Ambiente worker+API pronto.
echo.
echo Proximos passos:
echo   1^) Copie conf\  ^(chave.key, sgc.dat, glpi.dat^)
echo   2^) copy backend\.env.example backend\.env  e preencha
echo   3^) run.bat
echo   4^) set SGC_SERVE_FRONTEND=1 ^&^& set SGC_API_PORT=8001 ^&^& run_api.bat
echo.
echo Guia: INSTALAR.txt  ou  docs\DEPLOY-WINDOWS.md
echo ============================================================
exit /b 0
