$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$webRoot = Join-Path $projectRoot "apps\web\dist"
$pidFile = Join-Path $projectRoot ".jobflow.pid"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment missing. Run scripts\setup.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $webRoot "index.html"))) {
    throw "Web build missing. Run npm run build first."
}

$env:JOBFLOW_WEB_ROOT = $webRoot
$env:JOBFLOW_NO_TRAY = "1"
$service = Start-Process -FilePath $venvPython `
    -ArgumentList "-m", "job_orchestrator" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -PassThru
$service.Id | Set-Content -LiteralPath $pidFile -Encoding ascii

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -TimeoutSec 1
        if ($health.status -eq "ok") {
            Start-Process "http://127.0.0.1:8765"
            Write-Host "JobFlow CN started (PID $($service.Id))."
            exit 0
        }
    } catch {
        Start-Sleep -Milliseconds 300
    }
}

throw "JobFlow CN did not become healthy within 9 seconds."
