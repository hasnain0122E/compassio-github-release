# Start the existing Next.js frontend against the local API (Windows PowerShell 5.1+):
#
#   powershell -ExecutionPolicy Bypass -File scripts\start_web.ps1             # dev server on :3000
#   powershell -ExecutionPolicy Bypass -File scripts\start_web.ps1 -ApiPort 8001
param([int] $ApiPort = 8000)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path (Split-Path -Parent $PSScriptRoot) "apps\web")
$env:NEXT_PUBLIC_COMPASSIO_API_URL = "http://127.0.0.1:$ApiPort"
pnpm install --frozen-lockfile
if ($LASTEXITCODE -ne 0) { throw "pnpm install failed" }
pnpm dev --hostname 127.0.0.1 --port 3000
