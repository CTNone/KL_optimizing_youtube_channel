param(
    [ValidatePattern('^[a-p]{32}$')][string]$ExtensionId='ligfchdeobjmdgdojlmogfpjnjlibgnh',
    [ValidatePattern('^(Default|Profile \d+)$')][string]$Profile='Default'
)
$ErrorActionPreference='Stop'
try {
    $candidates=@(
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
    )
    $chrome=$candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if(-not $chrome){throw 'Không tìm thấy Google Chrome trên máy tính.'}
    $url="chrome-extension://$ExtensionId/popup.html?desktop=1"
    Start-Process -FilePath $chrome -ArgumentList @("--profile-directory=`"$Profile`"","--app=`"$url`"") -WindowStyle Normal
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Flow TXT') | Out-Null
    exit 1
}
