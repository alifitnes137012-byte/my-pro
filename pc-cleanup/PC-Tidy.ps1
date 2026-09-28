<#
  PC-Tidy.ps1  --  Safe organizer & performance report for Windows 10/11
  -----------------------------------------------------------------------
  * NEVER deletes anything.
  * By default runs in PREVIEW mode (only shows what it would do).
  * Every move is logged to a CSV so it can be undone with Undo-Tidy.ps1.

  Usage (PowerShell):
    Set-ExecutionPolicy -Scope Process Bypass
    .\PC-Tidy.ps1                 # preview + reports only
    .\PC-Tidy.ps1 -Apply          # actually move files into category folders
    .\PC-Tidy.ps1 -LargeFileMB 200
#>
param(
    [switch]$Apply,
    [int]$LargeFileMB = 500,
    [string[]]$Folders = @(
        [Environment]::GetFolderPath('Desktop'),
        (Join-Path $env:USERPROFILE 'Downloads'),
        [Environment]::GetFolderPath('MyDocuments')
    )
)

$ErrorActionPreference = 'SilentlyContinue'
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$outDir = Join-Path ([Environment]::GetFolderPath('Desktop')) "PC-Tidy-Report-$stamp"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

# ---------------------------------------------------------------- categories
$categories = [ordered]@{
    'Images'     = 'jpg','jpeg','png','gif','bmp','webp','heic','svg','tif','tiff','ico','raw'
    'Videos'     = 'mp4','mkv','avi','mov','wmv','flv','webm','m4v','3gp'
    'Music'      = 'mp3','wav','flac','aac','ogg','m4a','wma'
    'Documents'  = 'pdf','doc','docx','txt','rtf','odt','ppt','pptx','xls','xlsx','csv','md','epub'
    'Archives'   = 'zip','rar','7z','tar','gz','bz2','xz','iso'
    'Installers' = 'exe','msi','msix','appx','apk'
    'Code'       = 'py','js','ts','html','css','json','xml','ps1','bat','sh','java','c','cpp','cs','php','sql'
}
function Get-Category($ext) {
    $e = $ext.TrimStart('.').ToLower()
    foreach ($k in $categories.Keys) { if ($categories[$k] -contains $e) { return $k } }
    return 'Other'
}
function Get-UniquePath($path) {
    if (-not (Test-Path -LiteralPath $path)) { return $path }
    $dir = Split-Path $path; $base = [IO.Path]::GetFileNameWithoutExtension($path); $ext = [IO.Path]::GetExtension($path)
    $i = 1
    do { $p = Join-Path $dir "$base ($i)$ext"; $i++ } while (Test-Path -LiteralPath $p)
    return $p
}

# ------------------------------------------------------------ 1. organize
Write-Host "`n=== 1) Organizing folders ($(if($Apply){'APPLY'}else{'PREVIEW'})) ===" -ForegroundColor Cyan
$moves = @()
foreach ($folder in $Folders) {
    if (-not (Test-Path $folder)) { continue }
    Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Extension -notin '.lnk','.url','.ini' } | ForEach-Object {
        $cat    = Get-Category $_.Extension
        $target = Join-Path $folder $cat
        $dest   = Get-UniquePath (Join-Path $target $_.Name)
        $moves += [pscustomobject]@{ From = $_.FullName; To = $dest; SizeMB = [math]::Round($_.Length/1MB,2) }
        if ($Apply) {
            New-Item -ItemType Directory -Path $target -Force | Out-Null
            Move-Item -LiteralPath $_.FullName -Destination $dest
        }
    }
}
$moves | Export-Csv (Join-Path $outDir 'moves-log.csv') -NoTypeInformation -Encoding UTF8
Write-Host "$($moves.Count) files $(if($Apply){'moved'}else{'would be moved'}). Log: moves-log.csv"

# ------------------------------------------------------- 2. large files
Write-Host "`n=== 2) Large files (> $LargeFileMB MB) in your user folder ===" -ForegroundColor Cyan
$large = Get-ChildItem -Path $env:USERPROFILE -Recurse -File -Force |
    Where-Object { $_.Length -gt $LargeFileMB*1MB -and $_.FullName -notmatch '\\AppData\\Local\\Packages\\' } |
    Sort-Object Length -Descending |
    Select-Object @{n='SizeGB';e={[math]::Round($_.Length/1GB,2)}}, LastAccessTime, FullName
$large | Export-Csv (Join-Path $outDir 'large-files.csv') -NoTypeInformation -Encoding UTF8
$large | Select-Object -First 20 | Format-Table -AutoSize

# ---------------------------------------- 3. likely-unneeded items (report)
Write-Host "`n=== 3) Probably unneeded (review yourself, nothing deleted) ===" -ForegroundColor Cyan
function FolderSizeMB($p) { [math]::Round(((Get-ChildItem $p -Recurse -File -Force | Measure-Object Length -Sum).Sum)/1MB,1) }
$junk = @(
    [pscustomobject]@{ Item='User Temp';               Path=$env:TEMP }
    [pscustomobject]@{ Item='Windows Temp';            Path="$env:WINDIR\Temp" }
    [pscustomobject]@{ Item='Windows Update cache';    Path="$env:WINDIR\SoftwareDistribution\Download" }
    [pscustomobject]@{ Item='Chrome cache';            Path="$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache" }
    [pscustomobject]@{ Item='Edge cache';              Path="$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache" }
    [pscustomobject]@{ Item='Crash dumps';             Path="$env:LOCALAPPDATA\CrashDumps" }
    [pscustomobject]@{ Item='Recycle Bin (C:)';        Path='C:\$Recycle.Bin' }
) | ForEach-Object { $_ | Add-Member SizeMB (FolderSizeMB $_.Path) -PassThru }
$junk | Format-Table Item, SizeMB, Path -AutoSize

$oldInstallers = Get-ChildItem (Join-Path $env:USERPROFILE 'Downloads') -Recurse -File -Include *.exe,*.msi,*.iso,*.zip,*.rar |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } |
    Select-Object @{n='SizeMB';e={[math]::Round($_.Length/1MB,1)}}, LastWriteTime, FullName
$junk          | Export-Csv (Join-Path $outDir 'temp-cache-sizes.csv') -NoTypeInformation -Encoding UTF8
$oldInstallers | Export-Csv (Join-Path $outDir 'old-installers-archives.csv') -NoTypeInformation -Encoding UTF8
Write-Host "$($oldInstallers.Count) old installers/archives (>90 days) in Downloads -> old-installers-archives.csv"

# duplicates (same size + same hash) among files > 10 MB
$dups = Get-ChildItem $env:USERPROFILE -Recurse -File -Force |
    Where-Object { $_.Length -gt 10MB -and $_.FullName -notmatch '\\AppData\\' } |
    Group-Object Length | Where-Object Count -gt 1 | ForEach-Object { $_.Group } |
    ForEach-Object { [pscustomobject]@{ Hash=(Get-FileHash $_.FullName -Algorithm MD5).Hash; SizeMB=[math]::Round($_.Length/1MB,1); FullName=$_.FullName } } |
    Group-Object Hash | Where-Object Count -gt 1 | ForEach-Object { $_.Group }
$dups | Export-Csv (Join-Path $outDir 'duplicate-files.csv') -NoTypeInformation -Encoding UTF8
Write-Host "$(@($dups).Count) files are duplicates of each other -> duplicate-files.csv"

# ------------------------------------------------------- 4. speed report
Write-Host "`n=== 4) Performance check ===" -ForegroundColor Cyan
Get-PSDrive -PSProvider FileSystem | Where-Object Used |
    Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}, @{n='UsedGB';e={[math]::Round($_.Used/1GB,1)}},
                  @{n='Free%';e={[math]::Round(100*$_.Free/($_.Free+$_.Used),0)}} | Format-Table -AutoSize

$os = Get-CimInstance Win32_OperatingSystem
Write-Host ("RAM: {0:N1} GB total, {1:N1} GB free" -f ($os.TotalVisibleMemorySize/1MB), ($os.FreePhysicalMemory/1MB))
Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, @{n='SizeGB';e={[math]::Round($_.Size/1GB)}} | Format-Table -AutoSize

Write-Host "Top processes by memory:"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name,
    @{n='RAM_MB';e={[math]::Round($_.WorkingSet64/1MB)}}, @{n='CPU_s';e={[math]::Round($_.CPU)}} | Format-Table -AutoSize

$startup = Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location
$startup | Export-Csv (Join-Path $outDir 'startup-programs.csv') -NoTypeInformation -Encoding UTF8
Write-Host "$(@($startup).Count) programs start with Windows -> startup-programs.csv"

$plan = (powercfg /getactivescheme) -replace '.*\((.*)\).*','$1'
Write-Host "Power plan: $plan"

# ------------------------------------------------------- 5. safe speed tweaks (only with -Apply)
if ($Apply) {
    Write-Host "`n=== 5) Applying safe speed tweaks ===" -ForegroundColor Cyan
    # Balanced -> High performance (reversible from Control Panel > Power Options)
    powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null
    # Visual effects: "Adjust for best performance" is left to the user (see README).
    # Optimize (TRIM/defrag) each fixed drive - does not delete data
    Get-Volume | Where-Object { $_.DriveType -eq 'Fixed' -and $_.DriveLetter } |
        ForEach-Object { Optimize-Volume -DriveLetter $_.DriveLetter -Verbose }
}

Write-Host "`nDone. All reports are in: $outDir" -ForegroundColor Green
Invoke-Item $outDir
