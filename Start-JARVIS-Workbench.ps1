param(
    [string]$InstallRoot = "$env:USERPROFILE\JARVIS",
    [int]$Port = 8768,
    [switch]$AppMode
)
$ErrorActionPreference = "Stop"
$python = Join-Path $InstallRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "JARVIS venv not found: $python" }

function Test-JarvisHealth {
    param([int]$P)
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:$P/health" -TimeoutSec 2
        return [bool]$h.ok
    } catch { return $false }
}

$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
    if (-not $proc -or $proc.CommandLine -notmatch '(?i)(-m\s+jarvis|jarvis-core)') {
        $detail = if ($proc) { "$($proc.Name) PID $($proc.ProcessId) :: $($proc.CommandLine)" } else { "PID $($conn.OwningProcess)" }
        throw "Port $Port is occupied by something other than clean JARVIS: $detail"
    }
}
elseif (-not (Test-JarvisHealth $Port)) {
    $env:JARVIS_DATA_DIR = Join-Path $InstallRoot "data"
    $env:JARVIS_HISTORY_DIR = Join-Path $InstallRoot "history"
    $env:JARVIS_PORT = "$Port"
    Start-Process -FilePath $python -ArgumentList @("-m", "jarvis") -WorkingDirectory $InstallRoot -WindowStyle Hidden | Out-Null
    $ready = $false
    for ($i=0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-JarvisHealth $Port) { $ready = $true; break }
    }
    if (-not $ready) { throw "JARVIS Core did not become healthy on port $Port within 30 seconds." }
}

if (-not (Test-JarvisHealth $Port)) {
    throw "A JARVIS-looking process owns port $Port but /health is not responding."
}

$url = "http://localhost:$Port/workbench"
$chromeCandidates = @()
if ($env:ProgramFiles) { $chromeCandidates += (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe") }
if (${env:ProgramFiles(x86)}) { $chromeCandidates += (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe") }
if ($env:LOCALAPPDATA) { $chromeCandidates += (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe") }
$chromeCandidates = $chromeCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$chrome = $chromeCandidates | Select-Object -First 1
if (-not $chrome) {
    $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if ($cmd) { $chrome = $cmd.Source }
}
if ($chrome) {
    $args = if ($AppMode) { @("--app=$url") } else { @("--new-window", $url) }
    Start-Process -FilePath $chrome -ArgumentList $args | Out-Null
    Write-Host "JARVIS Workbench opened in Chrome: $url"
} else {
    Start-Process $url | Out-Null
    Write-Host "Chrome was not found in standard locations; opened JARVIS in the default browser: $url"
}
Write-Host "Core continues in the background when the browser closes."
