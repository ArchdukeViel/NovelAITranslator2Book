#!/usr/bin/env pwsh
# tools/pytest.ps1 - run pytest inside the project virtualenv.
#
# Always resolves to <repo>/.venv/Scripts/python.exe so shell PATH order
# cannot accidentally run a different interpreter. Bails out with a
# clear message when the venv is missing.

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Project virtualenv not found at $venvPython. Run 'py -3.14 -m venv .venv' and install the project extras first."
    exit 2
}

# Normalize positional/path arguments for Windows while preserving pytest
# options and expressions such as ``-k`` values exactly as provided.
$normalizedArgs = @(
    foreach ($argument in $args) {
        if ($argument -is [string] -and -not $argument.StartsWith("-") -and $argument.Contains("/")) {
            $argument.Replace("/", "\")
        } else {
            $argument
        }
    }
)

& $venvPython -m pytest @normalizedArgs
exit $LASTEXITCODE
