param(
    [string]$InstallRoot = "$env:USERPROFILE\JARVIS",
    [string]$LegacyRoot = "$env:USERPROFILE\gmgn-demos\aitrader",
    [int]$Port = 8768,
    [switch]$Confirm
)
$ErrorActionPreference="Stop"
if(-not $Confirm){throw "This script never deletes legacy data. Rerun with -Confirm only after the final Chrome workbench is verified; it will rename the legacy root OFFLINE."}
if(-not(Test-Path -LiteralPath $LegacyRoot)){Write-Host "Legacy root already absent/offline: $LegacyRoot";exit 0}
$health=Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 3
$page=Invoke-WebRequest "http://127.0.0.1:$Port/workbench" -UseBasicParsing -TimeoutSec 5
$radar=Invoke-RestMethod "http://127.0.0.1:$Port/api/operator/radar?limit=1" -TimeoutSec 5
if(-not $health.ok -or $page.StatusCode -ne 200){throw "Clean JARVIS workbench is not healthy; refusing to retire legacy root."}
$python=Join-Path $InstallRoot ".venv\Scripts\python.exe"
$version=& $python -c "import jarvis; print(jarvis.__version__)"
if($version -ne '0.3.1'){throw "Unexpected clean Core version '$version'."}
$legacyProcesses=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($LegacyRoot,[System.StringComparison]::OrdinalIgnoreCase) -ge 0 }
if($legacyProcesses){$legacyProcesses | Select-Object ProcessId,Name,CommandLine | Format-Table -AutoSize;throw "A process is still using the legacy root. Stop it before retirement."}
$legacySecrets=Join-Path $LegacyRoot "data\v4-secrets.env"
if(Test-Path -LiteralPath $legacySecrets){
  $hadKey=[bool](Select-String -LiteralPath $legacySecrets -Pattern '^\s*GMGN_API_KEY\s*=\s*\S+' -Quiet)
  if($hadKey){
    $global=Join-Path $env:USERPROFILE ".config\gmgn\.env"
    $hasGlobal=(Test-Path -LiteralPath $global) -and [bool](Select-String -LiteralPath $global -Pattern '^\s*GMGN_API_KEY\s*=\s*\S+' -Quiet)
    if(-not $hasGlobal){throw "Legacy has a GMGN API key but the official global GMGN config does not. Run the final installer first; refusing retirement."}
  }
}
$parent=Split-Path -Parent $LegacyRoot
$name=Split-Path -Leaf $LegacyRoot
$offline=Join-Path $parent ("$name-OFFLINE-LEGACY-"+(Get-Date -Format 'yyyyMMdd-HHmmss'))
Rename-Item -LiteralPath $LegacyRoot -NewName (Split-Path -Leaf $offline)
Write-Host "Legacy runtime is now offline (not deleted):" -ForegroundColor Green
Write-Host $offline
Write-Host "Clean Core and Chrome workbench remained healthy before retirement."
Write-Host "Rollback if ever needed: Rename-Item -LiteralPath '$offline' -NewName '$name'"
