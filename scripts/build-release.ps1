param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$releaseRoot = Join-Path $projectRoot "release\v$Version"
$extensionDist = Join-Path $projectRoot "apps\extension\dist"

if (Test-Path -LiteralPath $releaseRoot) {
    throw "Release directory already exists: $releaseRoot"
}

npm ci --prefix $projectRoot
npm run build --prefix $projectRoot
& $venvPython -m pip install -e "${projectRoot}[windows]"
& $venvPython -m pip install -e (Join-Path $projectRoot "third_party\resume_engine")
& $venvPython -m PyInstaller (Join-Path $projectRoot "installer\windows\jobflow.spec") --noconfirm

New-Item -ItemType Directory -Path $releaseRoot | Out-Null
Compress-Archive -Path (Join-Path $extensionDist "*") `
    -DestinationPath (Join-Path $releaseRoot "jobflow-extension-v$Version.zip")
Copy-Item -LiteralPath (Join-Path $projectRoot "dist\JobFlowCN") `
    -Destination (Join-Path $releaseRoot "JobFlowCN") -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination $releaseRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") -Destination $releaseRoot

Write-Host "Release payload ready at $releaseRoot"
