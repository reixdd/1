param([int]$Port = 8768)
$ErrorActionPreference = "Stop"
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $conn) { Write-Host "Nothing is listening on port $Port."; exit 0 }
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
if (-not $proc -or $proc.CommandLine -notmatch '(?i)(-m\s+jarvis|jarvis-core)') {
    throw "Refusing to stop PID $($conn.OwningProcess): it is not recognized as clean JARVIS."
}
Stop-Process -Id $proc.ProcessId -Force
Write-Host "Stopped JARVIS Core PID $($proc.ProcessId)."
