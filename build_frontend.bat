@echo off
setlocal
cd /d "%~dp0frontend"
if not exist "package.json" (
  echo [ERRO] Pasta frontend nao encontrada
  exit /b 1
)
echo Building frontend...
call npm run build
if errorlevel 1 exit /b 1
echo.
echo Build OK: frontend\dist
echo Para servir via API: set SGC_SERVE_FRONTEND=1 ^&^& run_api.bat
echo Ou: npm run preview  (na pasta frontend)
