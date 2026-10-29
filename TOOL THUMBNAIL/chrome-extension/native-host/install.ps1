param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-p]{32}$')][string]$ExtensionId,
    [string]$PythonPath
)
$ErrorActionPreference = 'Stop'
if (-not $PythonPath) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $PythonPath = $bundledPython }
    else { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
& $PythonPath -c 'import tkinter; from PIL import Image'
if ($LASTEXITCODE -ne 0) { throw 'Python cần tkinter và Pillow để chọn thư mục và xác minh ảnh 2K. Có thể dùng Python đi kèm Codex.' }
$hostScript = Join-Path $PSScriptRoot 'host.py'
$launcher = Join-Path $PSScriptRoot 'launch.cmd'
$hostManifest = Join-Path $PSScriptRoot 'com.flowtxt.files.json'
$launchText = "@echo off`r`nchcp 65001 >nul`r`n`"$PythonPath`" -u `"$hostScript`" %*`r`n"
[IO.File]::WriteAllText($launcher, $launchText, [Text.UTF8Encoding]::new($false))
$manifest = @{name='com.flowtxt.files';description='Flow TXT Windows folder writer';path=$launcher;type='stdio';allowed_origins=@("chrome-extension://$ExtensionId/")}
[IO.File]::WriteAllText($hostManifest, ($manifest | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
$registryPath = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.flowtxt.files'
New-Item -Path $registryPath -Force | Out-Null
Set-Item -Path $registryPath -Value $hostManifest
Write-Output "Đã đăng ký bộ lưu Windows cho extension $ExtensionId. Tải lại extension rồi chọn Thư mục Windows."
