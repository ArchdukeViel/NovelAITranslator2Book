<#
.SYNOPSIS
    Writes a complete, sanitized telemetry matrix with explicit unavailable values.

.DESCRIPTION
    This local runner does not have provider dashboards or hosted billing
    counters. It records that boundary honestly instead of turning zeros or
    cumulative local counters into billing evidence.
#>
[CmdletBinding()]
param(
    [string]$BaselinePath = "artifacts/operations/reader-capacity-follow-up/baseline.json",
    [string]$OutputPath = "artifacts/operations/reader-capacity-follow-up/hosted-telemetry.json",
    [ValidateSet("pre_remediation", "stage_1000")]
    [string]$Phase = "pre_remediation",
    [string]$ReaderRunId,
    [string]$Revision,
    [ValidateSet("direct_service", "caddy_loopback", "private_network")]
    [string]$Topology = "caddy_loopback"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$baseline = Get-Content -LiteralPath $BaselinePath -Raw | ConvertFrom-Json
$now = [DateTime]::UtcNow
$campaignId = [string]$baseline.campaign_id
if ([string]::IsNullOrWhiteSpace($ReaderRunId)) { $ReaderRunId = "telemetry-$Phase" }
if ([string]::IsNullOrWhiteSpace($Revision)) { $Revision = [string]$baseline.baseline_revision }
$metrics = @(
    "reader_http_rps", "translation_provider_rps", "db_pool_wait_ms", "db_statement_ms",
    "db_pool_occupancy", "r2_read_count", "r2_read_bytes", "r2_read_ms",
    "r2_operation_count", "r2_billed_bytes", "provider_quota_remaining",
    "caddy_upstream_errors", "caddy_upstream_retries", "application_request_count",
    "container_cpu", "container_memory", "container_network_bytes", "redis_queue_depth", "worker_state"
)

function Get-UnavailableReason([string]$Metric) {
    if ($Metric -like "r2_*") { return "r2_metric_unavailable" }
    if ($Metric -like "provider_*") { return "provider_metric_unavailable" }
    if ($Metric -like "db_*") { return "pooler_metric_unavailable" }
    if ($Metric -eq "worker_state" -or $Metric -eq "redis_queue_depth") { return "runtime_state_unavailable" }
    if ($Metric -like "caddy_*") { return "target_not_configured" }
    return "provider_metric_unavailable"
}

$snapshots = @()
if ($Phase -eq "stage_1000" -and (Test-Path -LiteralPath $OutputPath -PathType Leaf)) {
    $existing = Get-Content -LiteralPath $OutputPath -Raw | ConvertFrom-Json
    if ([string]$existing.campaign_id -ne $campaignId) {
        throw "Existing telemetry campaign does not match the baseline campaign."
    }
    $snapshots = @($existing.snapshots)
}
foreach ($metric in $metrics) {
    $snapshots += [ordered]@{
        snapshot_id = "snap-$Phase-$ReaderRunId-$metric"
        campaign_id = $campaignId
        reader_run_id = $ReaderRunId
        phase = $Phase
        source = if ($metric -like "r2_*") { "r2_provider" } elseif ($metric -like "db_*") { "supabase_pooler" } elseif ($metric -like "caddy_*") { "caddy" } elseif ($metric -like "container_*") { "container_runtime" } elseif ($metric -eq "worker_state" -or $metric -eq "redis_queue_depth") { "local_runtime" } elseif ($metric -eq "translation_provider_rps" -or $metric -eq "provider_quota_remaining") { "provider_dashboard" } else { "reader_service" }
        source_timestamp = $now.ToString("yyyy-MM-ddTHH:mm:ssZ")
        interval_start = $now.AddMinutes(-1).ToString("yyyy-MM-ddTHH:mm:ssZ")
        interval_end = $now.ToString("yyyy-MM-ddTHH:mm:ssZ")
        revision = $Revision
        topology = $Topology
        workload = "reader_1000_dau_equivalent_read_only"
        metric_name = $metric
        sample_count = 0
        aggregation = "none"
        collection_status = "unavailable"
        provenance = "unavailable"
        unavailable_reason = Get-UnavailableReason $metric
    }
}

$outputDir = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDir) -and -not (Test-Path -LiteralPath $outputDir -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}
$payload = [ordered]@{ schema_version = 1; campaign_id = $campaignId; snapshots = $snapshots }
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding utf8

$validator = Join-Path $PSScriptRoot "validate_reader_follow_up.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $validator -Kind hosted-telemetry -Path $OutputPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Telemetry matrix recorded as explicit unavailable evidence: $OutputPath" -ForegroundColor Yellow
