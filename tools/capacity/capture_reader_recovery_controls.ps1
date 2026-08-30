<#
.SYNOPSIS
    Records the current recovery-control evidence boundary.

.DESCRIPTION
    Local unit tests do not prove current hosted backup freshness, alert
    delivery, or restore freshness. This artifact records those dimensions as
    unavailable instead of promoting test success to an operational pass.
#>
[CmdletBinding()]
param(
    [string]$BaselinePath = "artifacts/operations/reader-capacity-follow-up/baseline.json",
    [string]$OutputPath = "artifacts/operations/reader-capacity-follow-up/backup-controls.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$baseline = Get-Content -LiteralPath $BaselinePath -Raw | ConvertFrom-Json
$now = [DateTime]::UtcNow
$controls = @()
foreach ($class in @("database_backup", "r2_snapshot")) {
    $controls += [ordered]@{
        control_class = $class
        observed_at = $now.ToString("yyyy-MM-ddTHH:mm:ssZ")
        schedule_source = "scheduler_schedule_not_observed_in_read_only_runner"
        schedule_timezone = "unavailable"
        freshness_max_age_seconds = $null
        last_success_at = $null
        next_due_at = $null
        freshness_status = "unavailable"
        manifest_verified = $false
        checksum_verified = $false
        referenced_objects_verified = $false
        retention_status = "unavailable"
        last_restore_verified_at = $null
        alert_failure_threshold = $null
        alert_cooldown_seconds = $null
        alert_status = "unavailable"
        alert_delivery_status = "unavailable"
        owner_role = [string]$baseline.recovery_owner_role
        credential_scope_review = "procedure_recorded;live_scope_not_observed"
        cleanup_status = "not_applicable_without_isolated_target"
        unavailable_reason = "runtime_state_unavailable"
        evidence_scope = "local_read_only_inspection_and_unit_tests"
    }
}

$outputDir = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDir) -and -not (Test-Path -LiteralPath $outputDir -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}
$payload = [ordered]@{ schema_version = 1; campaign_id = [string]$baseline.campaign_id; controls = $controls }
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding utf8

$validator = Join-Path $PSScriptRoot "validate_reader_follow_up.ps1"
$validatorShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $validatorShell) { $validatorShell = Get-Command powershell -ErrorAction SilentlyContinue }
if ($null -eq $validatorShell) { throw "PowerShell runtime is required to validate recovery controls." }
& $validatorShell.Source -NoProfile -ExecutionPolicy Bypass -File $validator -Kind backup-controls -Path $OutputPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Recovery controls recorded with explicit unavailable status: $OutputPath" -ForegroundColor Yellow
