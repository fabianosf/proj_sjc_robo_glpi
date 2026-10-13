@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo SGC — instalar autostart (Agendador de Tarefas)
echo ============================================================
echo.
echo Cria duas tarefas no logon do usuario atual:
echo   SGC-Worker  - robô (atribui Novos)
echo   SGC-API     - painel em http://127.0.0.1:8001
echo.
echo Prefira rodar este .bat uma vez. Depois use so o navegador.
echo.

if not exist "venv\Scripts\python.exe" (
  echo [ERRO] venv nao encontrado. Rode setup_env.bat / setup_producao.bat primeiro.
  exit /b 1
)
if not exist "start_worker_hidden.vbs" (
  echo [ERRO] start_worker_hidden.vbs ausente.
  exit /b 1
)
if not exist "start_api_hidden.vbs" (
  echo [ERRO] start_api_hidden.vbs ausente.
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo [AVISO] frontend\dist nao encontrado.
  echo         Rode: cd frontend ^&^& npm run build
  echo         A API sobe mesmo assim; o painel pode ficar sem UI estatica.
  echo.
)

set "ROOT=%CD%"

schtasks /Delete /TN "SGC-Worker" /F >nul 2>&1
schtasks /Delete /TN "SGC-API" /F >nul 2>&1

schtasks /Create /TN "SGC-Worker" /SC ONLOGON /RL LIMITED /F /TR "wscript.exe \"%ROOT%\start_worker_hidden.vbs\""
if errorlevel 1 (
  echo [ERRO] Falha ao criar SGC-Worker.
  exit /b 1
)

schtasks /Create /TN "SGC-API" /SC ONLOGON /RL LIMITED /F /TR "wscript.exe \"%ROOT%\start_api_hidden.vbs\""
if errorlevel 1 (
  echo [ERRO] Falha ao criar SGC-API.
  exit /b 1
)

echo.
echo [OK] Tarefas criadas. Iniciando agora...
schtasks /Run /TN "SGC-Worker"
schtasks /Run /TN "SGC-API"

echo.
echo Painel: http://127.0.0.1:8001
echo Remover: uninstall_autostart_windows.bat
echo.
exit /b 0
