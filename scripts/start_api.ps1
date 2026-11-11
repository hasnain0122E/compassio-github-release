# Start the Compassio API for the local demo (Windows PowerShell 5.1+). Run from anywhere:
#
#   powershell -ExecutionPolicy Bypass -File scripts\start_api.ps1                 # event mode, ML v2 demo
#   powershell -ExecutionPolicy Bypass -File scripts\start_api.ps1 -Mode local     # local_development
#   powershell -ExecutionPolicy Bypass -File scripts\start_api.ps1 -NoMlV2         # ML v1 only
#   powershell -ExecutionPolicy Bypass -File scripts\start_api.ps1 -Port 8001 -NoPreload
#
# Always binds 127.0.0.1 (never 0.0.0.0), one worker. See docs/hackathon/local_demo_runbook.md.
param(
    [ValidateSet("event", "local")] [string] $Mode = "event",
    [int] $Port = 8000,
    [switch] $NoMlV2,
    [switch] $NoPreload,
    [switch] $C09,
    [switch] $C11,
    [switch] $SkipPreflight
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not $SkipPreflight) {
    uv run python scripts/demo_preflight.py
    if ($LASTEXITCODE -ne 0) { throw "Preflight failed: see docs/hackathon/local_demo_runbook.md section 2" }
}

$env:COMPASSIO_ENVIRONMENT = "development"
if ($Mode -eq "event") {
    $env:COMPASSIO_SOURCE_DATA_ACCESS = "hackathon_event"
    $env:COMPASSIO_EVENT_AUTHORIZATION = "battleverse_2026"
} else {
    $env:COMPASSIO_SOURCE_DATA_ACCESS = "local_development"
    Remove-Item Env:COMPASSIO_EVENT_AUTHORIZATION -ErrorAction SilentlyContinue
}
$env:COMPASSIO_ML_V2_LOCAL_DEMO = if ($NoMlV2) { "false" } else { "true" }
$env:COMPASSIO_PRELOAD_MODELS = if ($NoPreload) { "false" } else { "true" }
$env:COMPASSIO_C09_ENABLED = if ($C09) { "true" } else { "false" }
$env:COMPASSIO_C11_ENABLED = if ($C11) { "true" } else { "false" }

Write-Host "Compassio API: mode=$($env:COMPASSIO_SOURCE_DATA_ACCESS) ml_v2_demo=$($env:COMPASSIO_ML_V2_LOCAL_DEMO) preload=$($env:COMPASSIO_PRELOAD_MODELS) url=http://127.0.0.1:$Port"
uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port $Port --workers 1 --no-proxy-headers
