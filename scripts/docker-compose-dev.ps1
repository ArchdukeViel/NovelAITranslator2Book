[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env"
$composeFile = Join-Path $repoRoot "deploy\compose.yml"

if ($Help -or $ComposeArgs.Count -eq 0) {
    Write-Output "Usage: .\scripts\docker-compose-dev.ps1 <docker compose args>"
    Write-Output ""
    Write-Output "Runs: docker compose --env-file .env -f deploy/compose.yml <args>"
    Write-Output ""
    Write-Output "Examples:"
    Write-Output "  .\scripts\docker-compose-dev.ps1 up -d postgres redis backend"
    Write-Output "  .\scripts\docker-compose-dev.ps1 run --rm migrate"
    Write-Output "  .\scripts\docker-compose-dev.ps1 logs -f backend"
    Write-Output "  .\scripts\docker-compose-dev.ps1 stop backend"
    exit 0
}

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing root .env. Copy .env.example to .env and set required local values before running Docker Compose."
}

if (-not (Test-Path -LiteralPath $composeFile)) {
    throw "Compose file not found: $composeFile"
}

Push-Location $repoRoot
try {
    & docker compose --env-file .env -f deploy/compose.yml @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
