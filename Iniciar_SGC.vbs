' Inicia SGC (worker + API/painel) sem nenhuma janela de prompt.
' Abre o painel no navegador: http://127.0.0.1:8001
Option Explicit
Dim sh, fso, root
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root

If Not fso.FileExists(root & "\venv\Scripts\python.exe") Then
  MsgBox "venv nao encontrado. Rode setup_env.bat ou setup_producao.bat primeiro.", vbExclamation, "SGC"
  WScript.Quit 1
End If

If Not fso.FileExists(root & "\frontend\dist\index.html") Then
  MsgBox "frontend\dist nao encontrado. Rode: cd frontend && npm run build", vbExclamation, "SGC"
  WScript.Quit 1
End If

' Worker + API (pythonw — sem console)
sh.Run "wscript.exe //B """ & root & "\start_worker_hidden.vbs""", 0, False
WScript.Sleep 1000
sh.Run "wscript.exe //B """ & root & "\start_api_hidden.vbs""", 0, False
WScript.Sleep 4000
' Painel no navegador (sem prompt)
sh.Run "http://127.0.0.1:8001", 1, False
