[CmdletBinding()]
param(
    [string]$Python = ".venv\Scripts\python.exe",
    [switch]$RuntimeOnly,
    [switch]$DevOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($RuntimeOnly -and $DevOnly) {
    throw "Use only one of -RuntimeOnly or -DevOnly."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = if ([System.IO.Path]::IsPathRooted($Python)) {
    $Python
} else {
    Join-Path $repoRoot $Python
}

if (-not (Test-Path $pythonPath)) {
    throw "Python executable not found: $pythonPath"
}

# Keep pip/pip-tools temporary files inside the repo to avoid Windows temp-dir permission issues.
$tempRoot = Join-Path $repoRoot ".tmp\pip-temp"
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
$env:TMP = $tempRoot
$env:TEMP = $tempRoot

$commonArgs = @(
    "-m", "piptools", "compile",
    "pyproject.toml",
    "--strip-extras",
    "--allow-unsafe",
    "--resolver=backtracking",
    "--generate-hashes"
)

function Invoke-Compile {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    & $pythonPath @Args
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Push-Location $repoRoot
try {
    if (-not $DevOnly) {
        Invoke-Compile -Args ($commonArgs + @("--output-file", "requirements.lock"))
    }

    if (-not $RuntimeOnly) {
        Invoke-Compile -Args ($commonArgs + @("--extra", "dev", "--output-file", "requirements-dev.lock"))
    }
}
finally {
    Pop-Location
}
