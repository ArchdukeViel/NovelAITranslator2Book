<#
.SYNOPSIS
    Reset the cache state of an isolated reader-capacity Compose runtime.

.DESCRIPTION
    This helper is intentionally limited to a Compose project whose name is
    generated for the disposable reader-capacity run. It flushes that
    project's Redis database, restarts only its reader service, waits for the
    reader health state, and emits a sanitized reset proof. It cannot target
    the canonical local Compose project.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ComposeProject,
    [string]$ComposeFile = "deploy/compose.yml",
    [string]$ComposeEnvFile,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($ComposeProject -notmatch "^reader-capacity-test-[A-Za-z0-9_-]+$") {
    throw "Only an isolated reader-capacity Compose project may be reset."
}
if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
    throw "Compose file does not exist."
}
if (-not [string]::IsNullOrWhiteSpace($ComposeEnvFile) -and -not (Test-Path -LiteralPath $ComposeEnvFile -PathType Leaf)) {
    throw "Compose environment file does not exist."
}

$composeArgs = @("--project-name", $ComposeProject, "--file", $ComposeFile)
if (-not [string]::IsNullOrWhiteSpace($ComposeEnvFile)) {
    $composeArgs += @("--env-file", $ComposeEnvFile)
}

& docker compose @composeArgs exec -T redis redis-cli FLUSHDB *> $null
if ($LASTEXITCODE -ne 0) {
    throw "The isolated Redis cache could not be flushed."
}

& docker compose @composeArgs restart reader *> $null
if ($LASTEXITCODE -ne 0) {
    throw "The isolated reader service could not be restarted."
}

$health = ""
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $rows = @(& docker compose @composeArgs ps reader --format json 2>$null)
    if ($LASTEXITCODE -eq 0) {
        foreach ($line in $rows) {
            try {
                $row = [string]$line | ConvertFrom-Json
                if ([string]$row.Service -eq "reader") {
                    $health = [string]$row.Health
                }
            }
            catch {
                continue
            }
        }
    }
    if ($health -eq "healthy") { break }
    Start-Sleep -Seconds 1
}
if ($health -ne "healthy") {
    throw "The isolated reader did not return to a healthy state after reset."
}

$proof = [ordered]@{
    schema_version = 1
    status = "reset"
    proof_id = "reset-" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ")
    observed_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    cache_reset = "redis_flushdb"
    reader_restart = "completed"
    reader_health = "healthy"
    target_class = "isolated_non_production_reader_runtime"
}

$parent = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}
[System.IO.File]::WriteAllText($OutputPath, ($proof | ConvertTo-Json -Depth 5), [System.Text.Encoding]::UTF8)
Write-Output ($proof | ConvertTo-Json -Compress -Depth 5)
