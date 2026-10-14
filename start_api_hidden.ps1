# Sobe a API SGC sem janela (pythonw + logs).
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Pyw = Join-Path $Root 'venv\Scripts\pythonw.exe'
if (-not (Test-Path $Pyw)) { $Pyw = Join-Path $Root 'venv\Scripts\python.exe' }
if (-not (Test-Path $Pyw)) { exit 1 }

$LogDir = Join-Path $Root 'log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$env:SGC_SERVE_FRONTEND = '1'
# 0.0.0.0 = acessível na rede local (outro PC: http://IP_DO_PC:8001)
$env:SGC_API_HOST = '0.0.0.0'
$env:SGC_API_PORT = '8001'
$env:SGC_API_RELOAD = '0'
$env:SGC_API_DOCS = '0'
$env:SGC_HEADLESS = '1'
$env:PYTHONWARNINGS = 'ignore'
$env:PYTHONPATH = "$(Join-Path $Root 'backend');$(Join-Path $Root 'python')"

Start-Process -FilePath $Pyw `
  -ArgumentList '-m','uvicorn','app.main:app','--app-dir','backend','--host','0.0.0.0','--port','8001' `
  -WorkingDirectory $Root `
  -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $LogDir 'api_stdout.log') `
  -RedirectStandardError (Join-Path $LogDir 'api_stderr.log')
