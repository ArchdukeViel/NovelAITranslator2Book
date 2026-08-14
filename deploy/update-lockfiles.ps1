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
        # Vercel lockfile keeps a single deterministic generator: uv only.
        # uv is the same solver that produces uv.lock, and `--locked` refuses
        # to re-lock, so a committed requirements-vercel.lock is reproducible
        # from the committed uv.lock. Fail if uv is unavailable rather than
        # silently switching to a second, conflicting solver (pip-tools).
        $uvExe = Get-Command "uv" -ErrorAction SilentlyContinue
        if (-not $uvExe) {
            throw "uv is required to regenerate requirements-vercel.lock. Install uv (https://docs.astral.sh/uv/) and re-run update-lockfiles.ps1."
        }
        & uv export `
            --locked `
            --extra db `
            --extra s3 `
            --extra auth `
            --no-emit-workspace `
            --output-file requirements-vercel.lock
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    if (-not $RuntimeOnly) {
        Invoke-Compile -Args ($commonArgs + @("--extra", "dev", "--output-file", "requirements-dev.lock"))
    }
}
finally {
    Pop-Location
}
