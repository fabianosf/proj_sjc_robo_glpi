@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Removendo tarefas SGC-Worker e SGC-API...
schtasks /Delete /TN "SGC-Worker" /F >nul 2>&1
schtasks /Delete /TN "SGC-API" /F >nul 2>&1
echo [OK] Autostart removido.
echo Se quiser parar processos ja em execucao, encerre python.exe do worker/API no Gerenciador de Tarefas.
exit /b 0
