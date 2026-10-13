' Encerra processos SGC (worker main.py e uvicorn) sem janela.
Option Explicit
Dim sh, ps
Set sh = CreateObject("WScript.Shell")
ps = "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn app\.main|\\main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
sh.Run "powershell -NoProfile -WindowStyle Hidden -Command """ & ps & """", 0, True
