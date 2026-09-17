$ErrorActionPreference = 'Stop'

$workbookPath = Join-Path $PSScriptRoot 'YouTube_Library_600_Tracks.xlsx'
$musicRoot = 'C:\Users\nhatt\Music\YouTube_Audio_Library_600'
$cacheRoot = Join-Path $env:TEMP 'youtube-audio-library-cache'
$catalogUri = 'https://raw.githubusercontent.com/Windows81/youtube-audio-library/refs/heads/master/music.csv'
$rawBaseUri = 'https://raw.githubusercontent.com/Windows81/youtube-audio-library/master/music'

function Get-SafeFileName([string]$name) {
    $invalid = [System.IO.Path]::GetInvalidFileNameChars()
    foreach ($char in $invalid) { $name = $name.Replace([string]$char, '_') }
    return $name.Trim().TrimEnd('.')
}

New-Item -ItemType Directory -Force -Path $musicRoot, $cacheRoot | Out-Null
$catalogPath = Join-Path $cacheRoot 'music.csv'
Invoke-WebRequest -UseBasicParsing -Uri $catalogUri -OutFile $catalogPath

$catalog = Import-Csv -LiteralPath $catalogPath
$byTitle = @{}
foreach ($entry in $catalog) {
    if (-not $byTitle.ContainsKey($entry.title)) { $byTitle[$entry.title] = @() }
    $byTitle[$entry.title] += $entry
}

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$book = $null
$downloaded = 0
$copied = 0
$unmatched = @()
$failedDownloads = [System.Collections.Generic.List[object]]::new()

try {
    $book = $excel.Workbooks.Open($workbookPath, $null, $true)
    foreach ($sheet in $book.Worksheets) {
        if ($sheet.Name -eq 'README') { continue }

        $sheetRoot = Join-Path $musicRoot $sheet.Name
        New-Item -ItemType Directory -Force -Path $sheetRoot | Out-Null

        $lastRow = $sheet.UsedRange.Rows.Count
        for ($row = 5; $row -le $lastRow; $row++) {
            $number = $sheet.Cells.Item($row, 1).Text
            $track = $sheet.Cells.Item($row, 2).Text
            $artist = $sheet.Cells.Item($row, 3).Text
            if ([string]::IsNullOrWhiteSpace($track) -or [string]::IsNullOrWhiteSpace($artist)) { continue }

            $catalogTitle = "$track - $artist"
            $matches = @($byTitle[$catalogTitle])
            if ($matches.Count -ne 1 -or $null -eq $matches[0] -or [string]::IsNullOrWhiteSpace($matches[0].num)) {
                $unmatched += [PSCustomObject]@{ Sheet = $sheet.Name; Track = $track; Artist = $artist; CatalogTitle = $catalogTitle; MatchCount = $matches.Count }
                continue
            }

            $id = $matches[0].id
            $sourceFile = Join-Path $cacheRoot ("{0}.mp3" -f $matches[0].num)
            if (-not (Test-Path -LiteralPath $sourceFile)) {
                $downloadUri = "$rawBaseUri/{0}.mp3" -f $matches[0].num
                $temporaryFile = "$sourceFile.download"
                try {
                    Write-Host "Downloading $downloadUri"
                    Invoke-WebRequest -UseBasicParsing -Uri $downloadUri -OutFile $temporaryFile
                    Move-Item -LiteralPath $temporaryFile -Destination $sourceFile
                }
                catch {
                    if (Test-Path -LiteralPath $temporaryFile) { Remove-Item -LiteralPath $temporaryFile -Force }
                    $failedDownloads.Add([PSCustomObject]@{ Sheet = $sheet.Name; Track = $track; Artist = $artist; CatalogTitle = $catalogTitle; Reason = $_.Exception.Message })
                    continue
                }
                $downloaded++
            }

            $prefix = ('{0:D3}' -f [int]$number)
            $destinationName = Get-SafeFileName ("$prefix - $track - $artist.mp3")
            $destination = Join-Path $sheetRoot $destinationName
            if (-not (Test-Path -LiteralPath $destination)) {
                Copy-Item -LiteralPath $sourceFile -Destination $destination
                $copied++
            }
        }
    }
}
finally {
    if ($book) { $book.Close($false) }
    if ($excel) { $excel.Quit() }
    if ($book) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book) }
    if ($excel) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

foreach ($item in $unmatched) {
    $failedDownloads.Add([PSCustomObject]@{ Sheet = $item.Sheet; Track = $item.Track; Artist = $item.Artist; CatalogTitle = $item.CatalogTitle; Reason = "No exact catalog match (matches: $($item.MatchCount))" })
}

$report = [PSCustomObject]@{
    DownloadedSourceFiles = $downloaded
    CopiedPlaylistFiles = $copied
    FailedRows = $failedDownloads.Count
    MusicRoot = $musicRoot
}
$report | ConvertTo-Json
if ($failedDownloads.Count -gt 0) {
    $failedDownloads | Export-Csv -LiteralPath (Join-Path $musicRoot 'failed_downloads.csv') -NoTypeInformation -Encoding utf8
}
