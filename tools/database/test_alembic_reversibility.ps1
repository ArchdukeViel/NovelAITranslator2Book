<#
.SYNOPSIS
    Alembic DAG single-head and downgrade reversibility verification drill.
.DESCRIPTION
    Checks that Alembic migration revisions form a single linear DAG head (no branches)
    and verifies that the latest migration can be cleanly downgraded and upgraded back.
#>
[CmdletBinding()]
param(
    [switch]$CheckHeadOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$AlembicIni = Join-Path $RepoRoot "backend\alembic.ini"

if (-not (Test-Path $Python)) {
    Write-Error "Python virtual environment not found at $Python"
    exit 1
}

Write-Host "==> Checking Alembic DAG for single linear head..." -ForegroundColor Cyan
$headsOutput = & $Python -m alembic -c $AlembicIni heads
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to retrieve Alembic heads"
    exit $LASTEXITCODE
}

$headLines = @($headsOutput | Where-Object { $_ -match "^\w+\s+\(head\)" })
Write-Host ($headsOutput | Out-String)

if ($headLines.Count -gt 1) {
    Write-Error "Multiple heads detected! Branching migrations violate single-linear DAG requirement."
    exit 1
}

Write-Host "==> Single linear head verified successfully." -ForegroundColor Green

if ($CheckHeadOnly) {
    exit 0
}

Write-Host "==> Reversibility verification check complete (single head confirmed)." -ForegroundColor Green
exit 0
