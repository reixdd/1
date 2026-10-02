param([string]$LegacyRoot = "$env:USERPROFILE\gmgn-demos\aitrader", [int]$Port = 8768)
$ErrorActionPreference="Stop"
Write-Host "JARVIS LEGACY RETIREMENT AUDIT (READ ONLY)"
Write-Host "Legacy root: $LegacyRoot"
if(Test-Path -LiteralPath $LegacyRoot){
  $files=(Get-ChildItem -LiteralPath $LegacyRoot -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
  $bytes=(Get-ChildItem -LiteralPath $LegacyRoot -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  Write-Host "Legacy files: $files"
  Write-Host ("Legacy bytes: {0:N0}" -f $bytes)
  $launchers=Get-ChildItem -LiteralPath $LegacyRoot -Recurse -File -Include *.ps1,*.cmd -ErrorAction SilentlyContinue | Where-Object {$_.Name -match 'Start|Run|Launch'} | Select-Object -First 40 FullName
  Write-Host "Potential old launchers (first 40):"; $launchers | Format-Table -AutoSize
}else{Write-Host "Legacy root not present."}
$conn=Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.LocalPort -in @(8000,8764,8768,8769)}
Write-Host "Known project ports:"; $conn | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize
Write-Host "No files/processes were modified."
