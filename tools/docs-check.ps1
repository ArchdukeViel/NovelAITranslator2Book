#!/usr/bin/env pwsh
# tools/docs-check.ps1 - canonical documentation contract entry point.

param(
    [switch]$SelfTest,
    [switch]$MigrationMode
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$checker = Join-Path $repoRoot "tools\docs_check.py"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Error "Project virtualenv not found at $venvPython."
    exit 2
}

$checkerArgs = @("--root", $repoRoot)
if ($SelfTest) {
    $checkerArgs += "--self-test"
}
if ($MigrationMode) {
    $checkerArgs += "--migration-mode"
}

& $venvPython $checker @checkerArgs
exit $LASTEXITCODE
