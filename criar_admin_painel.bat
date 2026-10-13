@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERRO] venv nao encontrado. Execute setup_env.bat
    exit /b 1
)

echo.
echo [AVISO] Login do painel = Active Directory + allowlist (59817 / equipe N3).
echo         Senha local NAO autentica. Configure SGC_AD_DOMAIN em backend\.env
echo.

if "%~1"=="" (
    echo Uso excepcional ^(somente registro local / auditoria^):
    echo   criar_admin_painel.bat --username 59817 --nome "Seu Nome"
    echo.
    echo Acesso real ao painel:
    echo   - Matricula 59817 OU tecnico ativo Equipe=N3 em Tb_Atrib
    echo   - Senha = senha do Windows / Active Directory
    exit /b 1
)

"%PYTHON%" backend\scripts\criar_admin.py %*
exit /b %ERRORLEVEL%
