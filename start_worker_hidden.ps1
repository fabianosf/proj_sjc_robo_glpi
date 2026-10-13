# Sobe o worker SGC sem janela (pythonw + SGC_HEADLESS).
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Pyw = Join-Path $Root 'venv\Scripts\pythonw.exe'
if (-not (Test-Path $Pyw)) { $Pyw = Join-Path $Root 'venv\Scripts\python.exe' }
if (-not (Test-Path $Pyw)) { exit 1 }

$LogDir = Join-Path $Root 'log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$env:SGC_HEADLESS = '1'
$env:PYTHONWARNINGS = 'ignore'

Start-Process -FilePath $Pyw `
  -ArgumentList (Join-Path $Root 'main.py') `
  -WorkingDirectory $Root `
  -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $LogDir 'worker_stdout.log') `
  -RedirectStandardError (Join-Path $LogDir 'worker_stderr.log')
