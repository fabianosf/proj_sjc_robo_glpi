@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%~dp0"
set "OUT=%ROOT%dist-windows\SGC"
set "FE=%ROOT%frontend"

echo ============================================================
echo SGC — pacote Windows (sem PyInstaller)
echo Saida: dist-windows\SGC\
echo ============================================================
echo.

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERRO] npm nao encontrado. Instale Node.js LTS para gerar o frontend.
  exit /b 1
)

echo [1/4] Build do frontend...
pushd "%FE%"
call npm run build
if errorlevel 1 (
  popd
  echo [ERRO] Falha no npm run build
  exit /b 1
)
popd
if not exist "%FE%\dist\index.html" (
  echo [ERRO] frontend\dist nao gerado
  exit /b 1
)

echo.
echo [2/4] Limpando pasta de saida...
if exist "%ROOT%dist-windows" rmdir /s /q "%ROOT%dist-windows"
mkdir "%OUT%" 2>nul
mkdir "%OUT%\conf" 2>nul
mkdir "%OUT%\log" 2>nul
mkdir "%OUT%\relatorios" 2>nul
mkdir "%OUT%\frontend" 2>nul

echo.
echo [3/4] Copiando arquivos (sem venv, node_modules, conf secreta, dumps)...

REM --- raiz ---
for %%F in (
  main.py
  arqaux.txt
  requirements.txt
  requirements-api.txt
  run.bat
  run.sh
  run_api.bat
  run_api_dev.bat
  setup_env.bat
  setup_env.sh
  sgc_python.bat
  sgc_python.sh
  criar_admin_painel.bat
  build_frontend.bat
  setup_producao.bat
  proj_sgc.service
  README.md
) do (
  if exist "%ROOT%%%F" copy /Y "%ROOT%%%F" "%OUT%\" >nul
)

REM --- codigo ---
robocopy "%ROOT%python" "%OUT%\python" /E /XD __pycache__ /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%ROOT%backend" "%OUT%\backend" /E /XD __pycache__ .pytest_cache /XF .env /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%ROOT%sql" "%OUT%\sql" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%ROOT%docs" "%OUT%\docs" /E /XF _removed_list.tmp.txt /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%ROOT%deploy" "%OUT%\deploy" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%ROOT%Modelo" "%OUT%\Modelo" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
if exist "%ROOT%drivers" robocopy "%ROOT%drivers" "%OUT%\drivers" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul

REM frontend so o dist (+ example env)
robocopy "%FE%\dist" "%OUT%\frontend\dist" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
if exist "%FE%\.env.example" copy /Y "%FE%\.env.example" "%OUT%\frontend\" >nul

REM conf: apenas instrucao (NAO copia .dat / chave.key)
(
  echo Coloque aqui os arquivos de configuracao da maquina de DESTINO:
  echo   chave.key
  echo   sgc.dat
  echo   glpi.dat
  echo.
  echo NAO versionar / NAO compartilhar estes arquivos publicamente.
) > "%OUT%\conf\LEIA-ME.txt"

copy /Y "%ROOT%docs\INSTALAR-WINDOWS.txt" "%OUT%\INSTALAR.txt" >nul

echo.
echo [4/4] Pacote pronto.
echo.
echo   Pasta: %OUT%
echo   Proximo: leia INSTALAR.txt ou docs\DEPLOY-WINDOWS.md
echo ============================================================
dir /b "%OUT%"
echo.
exit /b 0
