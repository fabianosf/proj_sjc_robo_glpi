@echo off
:: Execute como Administrador (botao direito) para liberar o celular na rede.
net session >nul 2>&1
if errorlevel 1 (
  echo Solicita UAC...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

netsh advfirewall firewall delete rule name="SGC API Mobile 8001" >nul 2>&1
netsh advfirewall firewall add rule name="SGC API Mobile 8001" dir=in action=allow protocol=TCP localport=8001 profile=any
if errorlevel 1 (
  echo [ERRO] Falha ao criar regra.
  pause
  exit /b 1
)
echo.
echo OK — porta 8001 liberada no Firewall.
echo No celular (mesma Wi-Fi): http://IP_DO_PC:8001/
echo.
pause
