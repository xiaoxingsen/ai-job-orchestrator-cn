$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot ".jobflow.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "No recorded JobFlow CN process."
    exit 0
}

$servicePid = [int](Get-Content -LiteralPath $pidFile -Raw)
$process = Get-Process -Id $servicePid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $servicePid
}
Remove-Item -LiteralPath $pidFile -Force
Write-Host "JobFlow CN stopped."

