param(
    [string]$Destination=$PSScriptRoot,
    [ValidatePattern('^[a-p]{32}$')][string]$ExtensionId='ligfchdeobjmdgdojlmogfpjnjlibgnh',
    [ValidatePattern('^(Default|Profile \d+)$')][string]$Profile='Default'
)
$ErrorActionPreference='Stop'
$launcher=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'Start-FlowTXT.ps1')).Path
$destinationPath=(Resolve-Path -LiteralPath $Destination).Path
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut((Join-Path $destinationPath 'Flow TXT.lnk'))
$shortcut.TargetPath=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$command="& '"+$launcher.Replace("'","''")+"' -ExtensionId '$ExtensionId' -Profile '$Profile'"
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
$shortcut.Arguments="-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand $encoded"
$shortcut.WorkingDirectory=$PSScriptRoot
$shortcut.Description='Flow TXT — giao diện và dữ liệu dùng chung với extension Chrome'
$shortcut.WindowStyle=7
$shortcut.Save()
Write-Output (Join-Path $destinationPath 'Flow TXT.lnk')
