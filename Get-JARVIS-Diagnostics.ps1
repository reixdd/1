param([int]$Port = 8768)
$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:$Port"
Write-Host "=== PIPELINE ==="
Invoke-RestMethod "$base/api/pipeline" | ConvertTo-Json -Depth 20
Write-Host "`n=== OPERATOR / GMGN ==="
Invoke-RestMethod "$base/api/operator/gmgn/status" | ConvertTo-Json -Depth 20
Write-Host "`n=== MODELS ==="
Invoke-RestMethod "$base/api/models" | ConvertTo-Json -Depth 20
Write-Host "`n=== AGENTS ==="
Invoke-RestMethod "$base/api/agents" | ConvertTo-Json -Depth 20
