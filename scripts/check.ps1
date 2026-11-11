# Runs every Phase 0 quality gate. Usage (from the repository root):
#   powershell -ExecutionPolicy Bypass -File scripts\check.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\check.ps1 -SkipWeb
param([switch]$SkipWeb)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Name (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Invoke-Step 'uv sync --locked' { uv sync --locked }
Invoke-Step 'ruff check' { uv run ruff check . }
Invoke-Step 'ruff format --check' { uv run ruff format --check . }
Invoke-Step 'mypy' { uv run mypy }
Invoke-Step 'pytest' { uv run pytest }

if (-not $SkipWeb) {
    Push-Location apps\web
    try {
        Invoke-Step 'pnpm install --frozen-lockfile' { pnpm install --frozen-lockfile }
        Invoke-Step 'pnpm lint' { pnpm lint }
        Invoke-Step 'pnpm typecheck' { pnpm typecheck }
        Invoke-Step 'pnpm build' { pnpm build }
    }
    finally {
        Pop-Location
    }
}

Write-Host 'All checks passed.' -ForegroundColor Green
