@echo off
REM Delega para Iniciar_SGC.vbs (sem janela preta).
REM Para ver logs no console em desenvolvimento, use: run_api.bat / python main.py
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [ERRO] Ambiente virtual nao encontrado: venv\Scripts\python.exe
  echo Execute primeiro: setup_env.bat
  pause
  exit /b 1
)

if not exist "Iniciar_SGC.vbs" (
  echo [ERRO] Iniciar_SGC.vbs nao encontrado.
  pause
  exit /b 1
)

REM start + wscript evita manter este .bat aberto; o app sobe oculto
start "" wscript.exe //B "%~dp0Iniciar_SGC.vbs"
exit /b 0
