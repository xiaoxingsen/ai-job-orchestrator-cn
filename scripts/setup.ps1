$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -3.12 -m venv (Join-Path $projectRoot ".venv")
    } else {
        python -m venv (Join-Path $projectRoot ".venv")
    }
}

& $venvPython -m pip install -e "${projectRoot}[dev,windows]"
& $venvPython -m pip install -e (Join-Path $projectRoot "third_party\resume_engine")
npm install --prefix $projectRoot
npm run build --prefix $projectRoot

Write-Host "Setup complete. Run scripts\start.ps1, then load apps\extension\dist in Chrome or Edge."
