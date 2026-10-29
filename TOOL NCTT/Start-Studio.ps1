$ErrorActionPreference = 'Stop'
try {
    $taskPython = (Get-Command python -ErrorAction Stop).Source
    & $taskPython -c 'import tkinter, requests, openpyxl, playwright; from PIL import Image'
    if ($LASTEXITCODE -ne 0) { throw 'Thieu thu vien. Hay chay run.bat trong TOOL NCTT truoc.' }
    $taskPythonw = Join-Path (Split-Path $taskPython) 'pythonw.exe'
    $taskEntry = Join-Path $PSScriptRoot 'studio.py'
    if (!(Test-Path -LiteralPath $taskEntry)) { throw 'Khong tim thay studio.py.' }
    Start-Process -FilePath $taskPythonw -ArgumentList ('"' + $taskEntry + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Normal
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'NCTT + Thumbnail') | Out-Null
    exit 1
}
