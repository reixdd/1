param([string]$InstallRoot = "$env:USERPROFILE\JARVIS")
$ErrorActionPreference = "Stop"

$entry = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -eq 'JARVIS Market Intelligence' } |
    Select-Object -First 1

$candidates = @()

if ($entry -and $entry.InstallLocation) {
    $installLocation = ([string]$entry.InstallLocation).Trim().Trim('"')

    if ($installLocation) {
        $candidates += Join-Path $installLocation 'jarvis-desktop.exe'
    }
}

$candidates += Join-Path $env:LOCALAPPDATA 'JARVIS Market Intelligence\jarvis-desktop.exe'
$candidates += Join-Path $env:LOCALAPPDATA 'Programs\JARVIS Market Intelligence\jarvis-desktop.exe'

$exe = $candidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1

if (-not $exe) {
    $setup = Join-Path $InstallRoot 'dist\JARVIS-Market-Intelligence-0.4.0-x64-setup.exe'

    if (Test-Path -LiteralPath $setup) {
        Write-Host "Desktop is built but not installed yet."
        Write-Host "Starting installer: $setup"
        Start-Process -FilePath $setup
        exit
    }

    throw "JARVIS desktop executable and NSIS installer were not found. Stage 4 did not finish building."
}

Write-Host "Starting JARVIS Desktop:"
Write-Host $exe
Start-Process -FilePath $exe
