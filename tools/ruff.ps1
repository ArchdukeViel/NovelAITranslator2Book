#!/usr/bin/env pwsh
# tools/ruff.ps1 - run ruff inside the project virtualenv.

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Project virtualenv not found at $venvPython. Run 'py -3.14 -m venv .venv' and install the project extras first." -ErrorAction Continue
    exit 2
}

$normalizedArgs = @(
    foreach ($argument in $args) {
        if ($argument -is [string] -and -not $argument.StartsWith("-") -and $argument.Contains("/")) {
            $argument.Replace("/", "\")
        } else {
            $argument
        }
    }
)

& $venvPython -m ruff @normalizedArgs
exit $LASTEXITCODE
