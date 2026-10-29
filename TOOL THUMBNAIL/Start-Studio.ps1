$ErrorActionPreference='Stop'
try {
    $python=(Get-Command python -ErrorAction Stop).Source
    & $python -c 'import tkinter, requests, openpyxl, playwright; from PIL import Image'
    if($LASTEXITCODE -ne 0){throw 'Python thiếu thư viện. Cài requests, openpyxl, Pillow và playwright trước khi mở Studio.'}
    $pythonw=Join-Path (Split-Path $python) 'pythonw.exe'
    $app=Join-Path $PSScriptRoot 'integrated_app.py'
    Start-Process -FilePath $pythonw -ArgumentList ('"'+$app+'"') -WorkingDirectory $PSScriptRoot -WindowStyle Normal
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'NCTT + Thumbnail') | Out-Null
}
