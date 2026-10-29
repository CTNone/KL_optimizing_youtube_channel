$ErrorActionPreference = 'Stop'
try {
    $python = (Get-Command python -ErrorAction Stop).Source
    $pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
    Start-Process -FilePath $pythonw -ArgumentList ('"' + (Join-Path $PSScriptRoot 'launcher.py') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'YouTube Music Studio') | Out-Null
}

