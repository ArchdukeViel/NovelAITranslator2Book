#!/usr/bin/env pwsh
# tools/pyright.ps1 - run pyright inside the project virtualenv.

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Project virtualenv not found at $venvPython. Run 'py -3.14 -m venv .venv' and install the project extras first."
    exit 2
}

& $venvPython -m pyright @args
exit $LASTEXITCODE
