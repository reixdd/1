param(
    [string]$InstallRoot = "$env:USERPROFILE\JARVIS",
    [int]$Port = 8768
)
$ErrorActionPreference = "Stop"
$python = Join-Path $InstallRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "JARVIS clean install not found: $InstallRoot" }

$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
    $detail = if ($proc) { "$($proc.Name) PID $($proc.ProcessId) :: $($proc.CommandLine)" } else { "PID $($conn.OwningProcess)" }
    throw "Port $Port is already in use by $detail. Stop that process or run this script with -Port 8769 for a side-by-side smoke check."
}

$env:JARVIS_DATA_DIR = Join-Path $InstallRoot "data"
$env:JARVIS_HISTORY_DIR = Join-Path $InstallRoot "history"
$env:JARVIS_PORT = "$Port"
& $python -m jarvis
