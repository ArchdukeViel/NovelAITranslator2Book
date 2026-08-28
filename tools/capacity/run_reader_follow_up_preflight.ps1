<#
.SYNOPSIS
    Captures a sanitized, fail-closed safety baseline for the follow-up.

.DESCRIPTION
    Runtime state is observed where the local Compose daemon exposes it. Queue
    and writer states that cannot be independently observed are recorded as
    unknown with a quantified blocker; they are never hardcoded as paused.
#>
[CmdletBinding()]
param(
    [switch]$ReadOnly,
    [string]$OutputPath = "artifacts/operations/reader-capacity-follow-up/baseline.json",
    [ValidateSet("caddy_loopback", "private_network")]
    [string]$SloGateTopology = "private_network",
    [ValidateSet(1000)]
    [int]$Profile = 1000,
    # Accept only the already-opaque binding produced by the reader runner;
    # never pass a raw slug or chapter identifier through this parameter.
    [string]$FixtureBindingId
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $ReadOnly) {
    Write-Error "This preflight is read-only; pass -ReadOnly explicitly."
    exit 2
}

function Get-EnvValue([string]$Name) {
    $property = Get-Item -Path ("Env:" + $Name) -ErrorAction SilentlyContinue
    if ($null -eq $property) { return $null }
    $value = [string]$property.Value
    if ([string]::IsNullOrWhiteSpace($value)) { return $null }
    return $value.Trim()
}

function Get-ComposeSnapshot() {
    $rows = @()
    $raw = @(docker compose -f deploy/compose.yml ps --format json 2>$null)
    if ($LASTEXITCODE -ne 0) {
        return [ordered]@{ status = "unavailable"; reason = "runtime_state_unavailable"; services = @() }
    }
    foreach ($line in $raw) {
        try {
            $row = [string]$line | ConvertFrom-Json
            $rows += [ordered]@{
                service = [string]$row.Service
                state = [string]$row.State
                health = [string]$row.Health
            }
        }
        catch {
            continue
        }
    }
    return [ordered]@{ status = "observed"; services = @($rows) }
}

function Get-ServiceState($Snapshot, [string]$Service) {
    $row = @($Snapshot.services | Where-Object { $_.service -eq $Service }) | Select-Object -First 1
    if ($null -eq $row) { return "stopped" }
    if ([string]$row.state -eq "running") { return "running" }
    return "stopped"
}

function New-Blocker([string]$Id, [string]$Target, [string]$Reason, [string]$UnavailableReason, [string]$NextAction, [string]$RetryCondition) {
    return [ordered]@{
        blocker_id = $Id
        observed_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        affected_target = $Target
        measured_value = $null
        budget_ms = $null
        source_or_reason = "$Reason unavailable"
        unavailable_reason = $UnavailableReason
        owner_role = "project_owner"
        next_action = $NextAction
        retry_or_admission_condition = $RetryCondition
        safety_disposition = "keep_capacity_unadmitted"
    }
}

$started = [DateTime]::UtcNow
$campaignId = "camp-" + $started.ToString("yyyyMMddTHHmmssZ")
$revision = ((git rev-parse HEAD 2>$null) -join "").Trim()
if ([string]::IsNullOrWhiteSpace($revision)) { $revision = "unavailable" }
$worktreeLines = @(git status --porcelain 2>$null)
$snapshot = Get-ComposeSnapshot
$workerState = Get-ServiceState $snapshot "worker"
$queueState = Get-EnvValue "READER_ORIGINAL_QUEUE_STATE"
if ([string]::IsNullOrWhiteSpace($queueState)) { $queueState = "unknown" }
$writersState = Get-EnvValue "READER_OTHER_WRITERS_STATE"
if ([string]::IsNullOrWhiteSpace($writersState)) { $writersState = "unknown" }
$fixtureId = if ([string]::IsNullOrWhiteSpace($FixtureBindingId)) {
    "not-supplied"
}
elseif ($FixtureBindingId -notmatch "^fixture-[0-9a-f]{16}$") {
    throw "FixtureBindingId must be the opaque fixture-<16 lowercase hex> value produced by the reader runner."
}
else {
    $FixtureBindingId.ToLowerInvariant()
}

$blockers = @()
if ($workerState -eq "running") {
    $blockers += New-Blocker "blk-worker-running" "translation_worker" "worker is running" "runtime_state_unavailable" "stop worker and recapture baseline" "do not profile while worker is running"
}
if ($queueState -eq "unknown") {
    $blockers += New-Blocker "blk-queue-state-unknown" "original_translation_queue" "original queue state was not independently observed" "runtime_state_unavailable" "record the queue state through an approved operator/runtime probe" "do not admit reader or translation capacity"
}
if ($writersState -eq "unknown") {
    $blockers += New-Blocker "blk-writer-state-unknown" "other_writers" "other writer state was not independently observed" "runtime_state_unavailable" "record all writer states through an approved operator/runtime probe" "do not admit reader or translation capacity"
}
if ($fixtureId -eq "not-supplied") {
    $blockers += New-Blocker "blk-fixture-not-supplied" "reader_fixture" "explicit fixture binding was not supplied" "fixture_not_configured" "supply one approved opaque fixture binding" "do not run fixture-dependent routes"
}
if ($snapshot.status -ne "observed") {
    $blockers += New-Blocker "blk-compose-state-unavailable" "compose_runtime" "Compose service state was not observed" "runtime_state_unavailable" "restore local runtime observation and recapture baseline" "do not run the profile"
}

$outputDir = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDir) -and -not (Test-Path -LiteralPath $outputDir -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

$baseline = [ordered]@{
    schema_version = 1
    campaign_id = $campaignId
    interval_start = $started.ToString("yyyy-MM-ddTHH:mm:ssZ")
    interval_end = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    baseline_revision = $revision
    topology = "split"
    worktree_state = if ($worktreeLines.Count -eq 0) { "clean" } else { "dirty_preserved" }
    target_aliases = @("direct_service", "caddy_loopback", "private_network")
    slo_gate_topology = $SloGateTopology
    fixture_binding_method = if ($fixtureId -eq "not-supplied") { "explicit_binding_missing" } else { "explicit_runtime_binding" }
    fixture_binding_id = $fixtureId
    cache_control_method = "disposable_reader_reset_or_explicit_unavailable"
    worker_state = if ($workerState -eq "running") { "unknown" } else { "stopped" }
    original_queue_state = $queueState
    other_writers_state = $writersState
    recovery_owner_role = "project_owner"
    recovery_escalation_role = "infrastructure_lead"
    required_routes = @("health_live", "catalog", "detail", "chapter", "search")
    diagnostic_routes = @("health_ready", "ranking_daily", "ranking_weekly", "ranking_monthly", "home")
    stop_thresholds = [ordered]@{
        max_transport_errors = 0
        max_timeouts = 0
        max_p95_liveness_ms = 100
        max_p95_catalog_ms = 500
        max_p95_detail_ms = 300
        max_p95_chapter_ms = 750
        max_p95_search_ms = 500
    }
    configuration_keys = @("APP_ENV", "DATABASE_URL", "REDIS_URL", "R2_BUCKET", "HEALTH_PROBE_TIMEOUT_MS", "HEALTH_TOTAL_TIMEOUT_MS", "READER_CADDY_HOST_HEADER")
    target_binding_contract = [ordered]@{
        direct_service = "diagnostic_only; host-published reader service or approved internal source"
        caddy_loopback = "diagnostic_only; requires an explicit Host binding"
        private_network = "selected_reader_slo_gate; private Caddy-routed entry point"
    }
    authorized_profile = [ordered]@{
        model = "1000_dau_equivalent"
        profile = $Profile
        concurrency = 8
        timeout_seconds = 20
        traffic_mode = "read_only_gets"
    }
    protected_surface_boundaries = [ordered]@{
        writes = "forbidden"
        provider_traffic = "forbidden"
        worker_resume = "forbidden"
        secrets = "not_recorded"
        canonical_content_mutation = "forbidden"
    }
    safety_state_source = if ($snapshot.status -eq "observed") { "docker_compose_ps_plus_operator_declarations" } else { "runtime_state_unavailable" }
    runtime_service_snapshot = $snapshot
    safety_blockers = @($blockers)
}

$json = $baseline | ConvertTo-Json -Depth 12
[System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.Encoding]::UTF8)

$validator = Join-Path $PSScriptRoot "validate_reader_follow_up.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $validator -Kind baseline -Path $OutputPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Baseline created with $(@($blockers).Count) explicit blocker(s): $OutputPath" -ForegroundColor Yellow
