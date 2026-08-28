<#
.SYNOPSIS
    Validates sanitized evidence for the reader-capacity and recovery follow-up.

.DESCRIPTION
    This validator is deliberately semantic. A schema-shaped JSON document is
    not sufficient evidence: campaign/run joins, interval ordering, required
    route/cache cells, unavailable dimensions, percentile counts, recovery
    fields, and quantified blocker postconditions are checked here.
#>
[CmdletBinding()]
param(
    [string]$Kind,
    [string]$Path,
    [switch]$SelfTest
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RequiredRoutes = @("health_live", "catalog", "detail", "chapter", "search")
$DiagnosticRoutes = @("health_ready", "ranking_daily", "ranking_weekly", "ranking_monthly", "home")
$Topologies = @("direct_service", "caddy_loopback", "private_network")
$CacheStates = @("warm", "cold", "unknown")
$AllowedUnavailableReasons = @(
    "target_not_configured",
    "caddy_host_binding_unavailable",
    "private_network_unavailable",
    "direct_service_unavailable",
    "tls_verification_unavailable",
    "cold_cache_control_unavailable",
    "provider_metric_unavailable",
    "pooler_metric_unavailable",
    "r2_metric_unavailable",
    "alert_delivery_unavailable",
    "fixture_not_configured",
    "profile_runner_unavailable",
    "workflow_test_path_missing",
    "runtime_state_unavailable",
    "restore_target_not_authorized"
    "quality_gate_failed"
)
$AllowedProvenance = @(
    "hosted_billing_actual",
    "database_cumulative",
    "application_interval",
    "reader_http_sample",
    "provider_dashboard",
    "local_synthetic",
    "unavailable"
)
$AllowedMetrics = @(
    "reader_http_rps",
    "translation_provider_rps",
    "db_pool_wait_ms",
    "db_statement_ms",
    "db_pool_occupancy",
    "r2_read_count",
    "r2_read_bytes",
    "r2_read_ms",
    "r2_operation_count",
    "r2_billed_bytes",
    "provider_quota_remaining",
    "caddy_upstream_errors",
    "caddy_upstream_retries",
    "application_request_count",
    "container_cpu",
    "container_memory",
    "container_network_bytes",
    "redis_queue_depth",
    "worker_state"
)
$LayerNames = @(
    "proxy_connect",
    "proxy_upstream",
    "application",
    "db_checkout",
    "db_statement",
    "db_commit",
    "r2_exact_read",
    "serialization",
    "network_remainder"
)

function Fail([string]$Message) {
    throw $Message
}

function Has-Property($Object, [string]$Name) {
    if ($Object -is [System.Collections.IDictionary]) {
        return $Object.Contains($Name)
    }
    return $null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name]
}

function Value-Of($Object, [string]$Name) {
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    if (Has-Property $Object $Name) {
        return $Object.PSObject.Properties[$Name].Value
    }
    return $null
}

function Require-Property($Object, [string]$Name, [string]$Context) {
    if (-not (Has-Property $Object $Name)) {
        Fail "$Context missing required property '$Name'"
    }
}

function Require-Text($Object, [string]$Name, [string]$Context) {
    Require-Property $Object $Name $Context
    if ([string]::IsNullOrWhiteSpace([string](Value-Of $Object $Name))) {
        Fail "$Context property '$Name' must be non-empty"
    }
}

function Validate-FixtureBinding($Object, [string]$Context) {
    Require-Text $Object "fixture_binding_id" $Context
    $fixtureId = [string](Value-Of $Object "fixture_binding_id")
    if ($fixtureId -ne "not-supplied" -and $fixtureId -notmatch "^fixture-[0-9a-f]{16}$") {
        Fail "$Context.fixture_binding_id must be not-supplied or fixture-<16 lowercase hex>"
    }
}

function As-Array($Value) {
    if ($null -eq $Value) {
        return @()
    }
    return @($Value)
}

function Parse-Utc([object]$Value, [string]$Context) {
    $parsed = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse([string]$Value, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal, [ref]$parsed)) {
        Fail "$Context is not a parseable UTC timestamp"
    }
    return $parsed.ToUniversalTime()
}

function Validate-Interval($Object, [string]$Context) {
    Require-Text $Object "interval_start" $Context
    Require-Text $Object "interval_end" $Context
    $start = Parse-Utc (Value-Of $Object "interval_start") "$Context.interval_start"
    $end = Parse-Utc (Value-Of $Object "interval_end") "$Context.interval_end"
    if ($end -lt $start) {
        Fail "$Context interval_end precedes interval_start"
    }
}

function Test-SecretExposure([string]$Text) {
    $patterns = @(
        'eyJ[A-Za-z0-9-_=]{20,}',
        '(?i)(password|secret|token|api[_-]?key|bearer)\s*[:=]\s*["''][^"'']{8,}["'']',
        '(?i)postgresql(\+psycopg)?:\/\/[^@\s]+:[^@\s]+@',
        'https:\/\/[^:\/\s]+:[^@\/\s]+@',
        '\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    )
    foreach ($pattern in $patterns) {
        if ($Text -match $pattern) {
            return $true
        }
    }
    return $false
}

function Validate-Redaction([string]$Text, [string]$Context) {
    if (Test-SecretExposure $Text) {
        Fail "$Context contains an unmasked secret, credential, or raw IP"
    }
}

function Validate-Enum([object]$Value, [string[]]$Allowed, [string]$Context) {
    if ($Allowed -notcontains [string]$Value) {
        Fail "$Context has unsupported value '$Value'"
    }
}

function Validate-QuantifiedBlocker($Blocker, [string]$Context) {
    foreach ($field in @("blocker_id", "observed_utc", "affected_target", "source_or_reason", "owner_role", "next_action", "retry_or_admission_condition", "safety_disposition")) {
        Require-Text $Blocker $field $Context
    }
    Parse-Utc (Value-Of $Blocker "observed_utc") "$Context.observed_utc" | Out-Null
    Require-Property $Blocker "measured_value" $Context
    Require-Property $Blocker "budget_ms" $Context
    $reason = [string](Value-Of $Blocker "source_or_reason")
    if ($reason -match "unavailable") {
        $candidate = [string](Value-Of $Blocker "unavailable_reason")
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            Fail "$Context unavailable blocker must include unavailable_reason"
        }
        Validate-Enum $candidate $AllowedUnavailableReasons "$Context.unavailable_reason"
    }
}

function Validate-Baseline($Data, [string]$RawText) {
    Validate-Redaction $RawText "Baseline"
    foreach ($field in @(
        "schema_version", "campaign_id", "baseline_revision", "topology",
        "target_aliases", "slo_gate_topology", "fixture_binding_method",
        "fixture_binding_id",
        "cache_control_method", "worker_state", "original_queue_state",
        "other_writers_state", "recovery_owner_role", "required_routes",
        "diagnostic_routes", "stop_thresholds", "configuration_keys",
        "authorized_profile", "protected_surface_boundaries", "safety_state_source"
    )) {
        Require-Property $Data $field "Baseline"
    }
    if ([int](Value-Of $Data "schema_version") -ne 1) { Fail "Baseline schema_version must be 1" }
    Validate-Interval $Data "Baseline"
    Require-Text $Data "campaign_id" "Baseline"
    Require-Text $Data "baseline_revision" "Baseline"
    Validate-FixtureBinding $Data "Baseline"
    Validate-Enum ([string](Value-Of $Data "slo_gate_topology")) @("caddy_loopback", "private_network") "Baseline.slo_gate_topology"
    Validate-Enum ([string](Value-Of $Data "fixture_binding_method")) @("explicit_binding_missing", "explicit_runtime_binding") "Baseline.fixture_binding_method"
    $fixtureMissing = [string](Value-Of $Data "fixture_binding_id") -eq "not-supplied"
    $methodMissing = [string](Value-Of $Data "fixture_binding_method") -eq "explicit_binding_missing"
    if ($fixtureMissing -ne $methodMissing) { Fail "Baseline fixture_binding_method does not match fixture_binding_id" }
    foreach ($stateName in @("worker_state", "original_queue_state", "other_writers_state")) {
        Validate-Enum ([string](Value-Of $Data $stateName)) @("stopped", "paused", "unknown") "Baseline.$stateName"
    }
    $declaredRoutes = @(Value-Of $Data "required_routes") | ForEach-Object { [string]$_ }
    if ($declaredRoutes.Count -ne $RequiredRoutes.Count) { Fail "Baseline.required_routes must contain exactly the five required route families" }
    foreach ($route in $RequiredRoutes) {
        if ($declaredRoutes -notcontains $route) { Fail "Baseline.required_routes missing '$route'" }
    }
    foreach ($route in As-Array (Value-Of $Data "diagnostic_routes")) {
        if ($DiagnosticRoutes -notcontains [string]$route) { Fail "Baseline contains invalid diagnostic route '$route'" }
    }
    $aliases = @(Value-Of $Data "target_aliases") | ForEach-Object { [string]$_ }
    foreach ($alias in $Topologies) {
        if ($aliases -notcontains $alias) { Fail "Baseline.target_aliases missing '$alias'" }
    }
    $profile = Value-Of $Data "authorized_profile"
    Require-Text $profile "model" "Baseline.authorized_profile"
    Require-Property $profile "profile" "Baseline.authorized_profile"
    if ([int](Value-Of $profile "profile") -ne 1000) { Fail "Baseline authorized profile must be 1000" }
    $boundaries = Value-Of $Data "protected_surface_boundaries"
    foreach ($boundary in @("writes", "provider_traffic", "worker_resume", "secrets")) {
        Require-Text $boundaries $boundary "Baseline.protected_surface_boundaries"
    }
    if ((Value-Of $Data "worker_state") -eq "unknown" -or (Value-Of $Data "original_queue_state") -eq "unknown" -or (Value-Of $Data "other_writers_state") -eq "unknown") {
        Require-Property $Data "safety_blockers" "Baseline"
        if (@(Value-Of $Data "safety_blockers").Count -eq 0) { Fail "Unknown safety state requires safety_blockers" }
        foreach ($blocker in As-Array (Value-Of $Data "safety_blockers")) { Validate-QuantifiedBlocker $blocker "Baseline.safety_blocker" }
    }
}

function Validate-Cell($Cell, [string]$Context, [string]$CampaignId) {
    foreach ($field in @(
        "schema_version", "campaign_id", "run_id", "fixture_binding_id", "interval_start", "interval_end",
        "revision", "topology", "tls_verification_mode", "gate_role", "route", "cache_state",
        "cache_control_method", "max_attempts_per_cell", "sample_target", "attempted_count", "sample_count",
        "completed_count", "valid_latency_count", "error_count", "timeout_count", "transport_error_count",
        "status_counts", "expected_status", "response_contract_status", "body_nonempty", "percentile_method",
        "p50_ms", "p95_ms", "p99_ms", "response_bytes_p95", "unavailable_fields", "provenance", "status"
    )) {
        Require-Property $Cell $field $Context
    }
    if ([int](Value-Of $Cell "schema_version") -ne 1) { Fail "$Context schema_version must be 1" }
    if ([string](Value-Of $Cell "campaign_id") -ne $CampaignId) { Fail "$Context campaign_id does not join the campaign" }
    Validate-FixtureBinding $Cell $Context
    Validate-Interval $Cell $Context
    Validate-Enum ([string](Value-Of $Cell "topology")) $Topologies "$Context.topology"
    Validate-Enum ([string](Value-Of $Cell "cache_state")) $CacheStates "$Context.cache_state"
    Validate-Enum ([string](Value-Of $Cell "route")) ($RequiredRoutes + $DiagnosticRoutes) "$Context.route"
    Validate-Enum ([string](Value-Of $Cell "provenance")) $AllowedProvenance "$Context.provenance"
    Validate-Enum ([string](Value-Of $Cell "status")) @("passed", "failed", "unavailable") "$Context.status"
    if ([int](Value-Of $Cell "max_attempts_per_cell") -lt 1 -or [int](Value-Of $Cell "max_attempts_per_cell") -gt 10000) { Fail "$Context max_attempts_per_cell is outside the finite bound" }
    if ([int](Value-Of $Cell "attempted_count") -gt [int](Value-Of $Cell "max_attempts_per_cell")) { Fail "$Context attempted_count exceeds max_attempts_per_cell" }
    $isUnavailable = [string](Value-Of $Cell "status") -eq "unavailable"
    if ($isUnavailable) {
        if (@(Value-Of $Cell "unavailable_fields").Count -eq 0) { Fail "$Context unavailable cell must name unavailable_fields" }
        if ([int](Value-Of $Cell "sample_count") -ne 0 -or [int](Value-Of $Cell "valid_latency_count") -ne 0) { Fail "$Context unavailable cell cannot claim samples" }
        foreach ($percentile in @("p50_ms", "p95_ms", "p99_ms")) {
            if ($null -ne (Value-Of $Cell $percentile)) { Fail "$Context unavailable cell cannot contain $percentile" }
        }
        if ([string](Value-Of $Cell "provenance") -ne "unavailable") { Fail "$Context unavailable cell must use unavailable provenance" }
    }
    else {
        if ([int](Value-Of $Cell "sample_target") -lt 50) { Fail "$Context sample_target must be at least 50" }
        if ([int](Value-Of $Cell "attempted_count") -lt 50 -or [int](Value-Of $Cell "sample_count") -lt 50 -or [int](Value-Of $Cell "valid_latency_count") -lt 50) { Fail "$Context must contain at least 50 attempted and valid samples" }
        foreach ($percentile in @("p50_ms", "p95_ms", "p99_ms", "response_bytes_p95")) {
            if ($null -eq (Value-Of $Cell $percentile) -or [double](Value-Of $Cell $percentile) -lt 0) { Fail "$Context $percentile must be a non-negative number" }
        }
        if ([string](Value-Of $Cell "cache_state") -eq "unknown") { Fail "$Context cannot call an unknown cache state a valid cell" }
        if ([string](Value-Of $Cell "status") -eq "passed" -and [string](Value-Of $Cell "response_contract_status") -ne "valid") { Fail "$Context passed cell must have a valid response contract" }
        if ([string](Value-Of $Cell "provenance") -eq "unavailable") { Fail "$Context valid cell cannot use unavailable provenance" }
    }
}

function Validate-RouteProfile($Data, [string]$RawText) {
    Validate-Redaction $RawText "Route profile"
    foreach ($field in @("schema_version", "campaign_id", "cells", "baseline_revision", "fixture_binding_id")) { Require-Property $Data $field "Route profile" }
    if ([int](Value-Of $Data "schema_version") -ne 1) { Fail "Route profile schema_version must be 1" }
    Validate-FixtureBinding $Data "Route profile"
    Require-Text $Data "campaign_id" "Route profile"
    $cells = @(As-Array (Value-Of $Data "cells"))
    if ($cells.Count -eq 0) { Fail "Route profile must contain cells" }
    $seen = @{}
    foreach ($cell in $cells) {
        $key = "$(Value-Of $cell 'topology')|$(Value-Of $cell 'route')|$(Value-Of $cell 'cache_state')"
        if ($seen.ContainsKey($key)) { Fail "Route profile contains duplicate cell '$key'" }
        $seen[$key] = $true
        Validate-Cell $cell "Route profile cell $key" ([string](Value-Of $Data "campaign_id"))
    }
    foreach ($topology in $Topologies) {
        foreach ($route in $RequiredRoutes) {
            $warm = @($cells | Where-Object { (Value-Of $_ "topology") -eq $topology -and (Value-Of $_ "route") -eq $route -and (Value-Of $_ "cache_state") -eq "warm" })
            $cold = @($cells | Where-Object { (Value-Of $_ "topology") -eq $topology -and (Value-Of $_ "route") -eq $route -and ((Value-Of $_ "cache_state") -eq "cold" -or (Value-Of $_ "cache_state") -eq "unknown") })
            if ($warm.Count -ne 1) { Fail "Route profile missing exactly one warm cell for $topology/$route" }
            if ($cold.Count -ne 1) { Fail "Route profile missing exactly one cold or explicit unavailable cell for $topology/$route" }
        }
    }
}

function Validate-Layer($Layer, [string]$Context) {
    Require-Property $Layer "status" $Context
    Validate-Enum ([string](Value-Of $Layer "status")) @("observed", "unavailable") "$Context.status"
    if ([string](Value-Of $Layer "status") -eq "observed") {
        foreach ($field in @("p50_ms", "p95_ms", "p99_ms", "count", "aggregation", "clock_boundary")) { Require-Property $Layer $field $Context }
        if ([int](Value-Of $Layer "count") -lt 1) { Fail "$Context observed count must be positive" }
    }
    else {
        Require-Text $Layer "unavailable_reason" $Context
        Validate-Enum ([string](Value-Of $Layer "unavailable_reason")) $AllowedUnavailableReasons "$Context.unavailable_reason"
    }
}

function Validate-LatencyAttribution($Data, [string]$RawText) {
    Validate-Redaction $RawText "Latency attribution"
    foreach ($field in @("schema_version", "campaign_id", "run_id", "interval_start", "interval_end", "revision", "classification", "routes")) { Require-Property $Data $field "Latency attribution" }
    if ([int](Value-Of $Data "schema_version") -ne 1) { Fail "Latency attribution schema_version must be 1" }
    Validate-Interval $Data "Latency attribution"
    Validate-Enum ([string](Value-Of $Data "classification")) @("local_application", "proxy_or_deployment", "hosted_dependency", "mixed_or_unavailable") "Latency attribution.classification"
    $routes = @(As-Array (Value-Of $Data "routes"))
    if ($routes.Count -eq 0) { Fail "Latency attribution must contain route records" }
    foreach ($route in $routes) {
        foreach ($field in @("route", "topology", "cache_state", "revision", "layers")) { Require-Property $route $field "Latency attribution route" }
        Validate-Enum ([string](Value-Of $route "route")) $RequiredRoutes "Latency attribution route.route"
        Validate-Enum ([string](Value-Of $route "topology")) $Topologies "Latency attribution route.topology"
        Validate-Enum ([string](Value-Of $route "cache_state")) $CacheStates "Latency attribution route.cache_state"
        foreach ($layerName in $LayerNames) {
            $layer = Value-Of (Value-Of $route "layers") $layerName
            if ($null -eq $layer) { Fail "Latency attribution route missing layer '$layerName'" }
            Validate-Layer $layer "Latency attribution $($route.route).$layerName"
        }
    }
}

function Validate-HostedTelemetry($Data, [string]$RawText) {
    Validate-Redaction $RawText "Hosted telemetry"
    foreach ($field in @("schema_version", "campaign_id", "snapshots")) { Require-Property $Data $field "Hosted telemetry" }
    if ([int](Value-Of $Data "schema_version") -ne 1) { Fail "Hosted telemetry schema_version must be 1" }
    $snapshots = @(As-Array (Value-Of $Data "snapshots"))
    if ($snapshots.Count -eq 0) { Fail "Hosted telemetry must contain snapshots" }
    $snapshotIds = @{}
    foreach ($snapshot in $snapshots) {
        foreach ($field in @("snapshot_id", "campaign_id", "reader_run_id", "phase", "source", "source_timestamp", "interval_start", "interval_end", "revision", "topology", "workload", "metric_name", "sample_count", "aggregation", "collection_status", "provenance")) { Require-Property $snapshot $field "Hosted telemetry snapshot" }
        $snapshotId = [string](Value-Of $snapshot "snapshot_id")
        if ([string]::IsNullOrWhiteSpace($snapshotId)) { Fail "Hosted telemetry snapshot_id must be non-empty" }
        if ($snapshotIds.ContainsKey($snapshotId)) { Fail "Hosted telemetry contains duplicate snapshot_id '$snapshotId'" }
        $snapshotIds[$snapshotId] = $true
        if ([string](Value-Of $snapshot "campaign_id") -ne [string](Value-Of $Data "campaign_id")) { Fail "Hosted telemetry snapshot campaign_id does not join top-level campaign" }
        Validate-Enum ([string](Value-Of $snapshot "phase")) @("pre_remediation", "stage_1000") "Hosted telemetry phase"
        Validate-Enum ([string](Value-Of $snapshot "metric_name")) $AllowedMetrics "Hosted telemetry metric_name"
        Validate-Enum ([string](Value-Of $snapshot "provenance")) $AllowedProvenance "Hosted telemetry provenance"
        Validate-Interval $snapshot "Hosted telemetry snapshot"
        Parse-Utc (Value-Of $snapshot "source_timestamp") "Hosted telemetry source_timestamp" | Out-Null
        $hasValue = Has-Property $snapshot "value" -and $null -ne (Value-Of $snapshot "value")
        $hasReason = Has-Property $snapshot "unavailable_reason" -and -not [string]::IsNullOrWhiteSpace([string](Value-Of $snapshot "unavailable_reason"))
        if ($hasValue -eq $hasReason) { Fail "Hosted telemetry snapshot must contain exactly one value or unavailable_reason" }
        if (-not $hasValue) { Validate-Enum ([string](Value-Of $snapshot "unavailable_reason")) $AllowedUnavailableReasons "Hosted telemetry unavailable_reason" }
        if ([string](Value-Of $snapshot "provenance") -eq "unavailable" -and $hasValue) { Fail "Unavailable telemetry cannot contain a value" }
    }
}

function Validate-BackupControls($Data, [string]$RawText) {
    Validate-Redaction $RawText "Backup controls"
    foreach ($field in @("schema_version", "controls")) { Require-Property $Data $field "Backup controls" }
    if ([int](Value-Of $Data "schema_version") -ne 1) { Fail "Backup controls schema_version must be 1" }
    $controls = @(As-Array (Value-Of $Data "controls"))
    if ($controls.Count -lt 2) { Fail "Backup controls must cover database_backup and r2_snapshot" }
    foreach ($control in $controls) {
        foreach ($field in @("control_class", "observed_at", "schedule_source", "schedule_timezone", "freshness_max_age_seconds", "last_success_at", "next_due_at", "freshness_status", "manifest_verified", "checksum_verified", "referenced_objects_verified", "retention_status", "last_restore_verified_at", "alert_failure_threshold", "alert_cooldown_seconds", "alert_status", "alert_delivery_status", "owner_role", "credential_scope_review", "cleanup_status", "unavailable_reason")) { Require-Property $control $field "Backup control" }
        Validate-Enum ([string](Value-Of $control "control_class")) @("database_backup", "r2_snapshot", "database_restore_verification") "Backup control.control_class"
        Parse-Utc (Value-Of $control "observed_at") "Backup control.observed_at" | Out-Null
        Require-Text $control "schedule_source" "Backup control"
        Require-Text $control "schedule_timezone" "Backup control"
        Require-Text $control "owner_role" "Backup control"
        if ([string](Value-Of $control "freshness_status") -eq "verified") {
            foreach ($field in @("last_success_at", "next_due_at", "retention_status", "last_restore_verified_at", "alert_status", "alert_delivery_status", "credential_scope_review", "cleanup_status")) {
                Require-Text $control $field "Verified backup control"
            }
        }
        else {
            Require-Text $control "unavailable_reason" "Unavailable backup control"
            Validate-Enum ([string](Value-Of $control "unavailable_reason")) $AllowedUnavailableReasons "Backup control.unavailable_reason"
        }
    }
}

function Validate-Stage1000($Data, [string]$RawText) {
    Validate-Redaction $RawText "Stage 1000"
    foreach ($field in @("schema_version", "campaign_id", "run_id", "baseline_revision", "candidate_revision", "fixture_binding_id", "profile", "slo_gate_topology", "route_cells", "sample_targets", "budgets", "telemetry_snapshot_ids", "provenance", "reader_slo_status", "path_profile_status", "telemetry_status", "recovery_status", "overall_follow_up_disposition", "production_capacity_claim", "blockers")) { Require-Property $Data $field "Stage 1000" }
    if ([int](Value-Of $Data "schema_version") -ne 1) { Fail "Stage 1000 schema_version must be 1" }
    Validate-FixtureBinding $Data "Stage 1000"
    Validate-Enum ([string](Value-Of $Data "slo_gate_topology")) @("caddy_loopback", "private_network") "Stage 1000.slo_gate_topology"
    Validate-Enum ([string](Value-Of $Data "reader_slo_status")) @("passed", "failed", "blocked") "Stage 1000.reader_slo_status"
    Validate-Enum ([string](Value-Of $Data "path_profile_status")) @("complete", "partial", "blocked") "Stage 1000.path_profile_status"
    Validate-Enum ([string](Value-Of $Data "telemetry_status")) @("complete", "partial", "unavailable") "Stage 1000.telemetry_status"
    Validate-Enum ([string](Value-Of $Data "recovery_status")) @("complete", "partial", "blocked", "not_assessed") "Stage 1000.recovery_status"
    Validate-Enum ([string](Value-Of $Data "overall_follow_up_disposition")) @("complete", "complete_with_quantified_blocker", "blocked") "Stage 1000.overall_follow_up_disposition"
    if ([string](Value-Of $Data "production_capacity_claim") -ne "not_established") { Fail "Stage 1000 production_capacity_claim must be not_established" }
    $cells = @(As-Array (Value-Of $Data "route_cells"))
    if ($cells.Count -eq 0) { Fail "Stage 1000 route_cells cannot be empty" }
    foreach ($cell in $cells) { Validate-Cell $cell "Stage 1000 route cell" ([string](Value-Of $Data "campaign_id")) }
    $blockers = @(As-Array (Value-Of $Data "blockers"))
    if ([string](Value-Of $Data "reader_slo_status") -eq "blocked" -or [string](Value-Of $Data "overall_follow_up_disposition") -ne "complete") {
        if ($blockers.Count -eq 0) { Fail "Blocked stage disposition requires quantified blockers" }
        foreach ($blocker in $blockers) { Validate-QuantifiedBlocker $blocker "Stage 1000 blocker" }
    }
    if ([string](Value-Of $Data "recovery_status") -eq "not_assessed" -and [string](Value-Of $Data "overall_follow_up_disposition") -eq "complete") {
        Fail "Stage 1000 cannot claim overall complete before recovery is assessed"
    }
}

function Validate-MarkdownDocument([string]$DocKind, [string]$RawText) {
    Validate-Redaction $RawText $DocKind
    if ([string]::IsNullOrWhiteSpace($RawText)) { Fail "$DocKind markdown is empty" }
    switch ($DocKind) {
        "remediation-decision" {
            if ($RawText -notmatch "(?i)classification|largest actionable contributor") { Fail "Remediation decision missing classification" }
            if ($RawText -notmatch "(?i)rollback|no-op|blocked") { Fail "Remediation decision missing rollback or blocker decision" }
        }
        "restore-verification" {
            if ($RawText -notmatch "(?i)isolated|disposable") { Fail "Restore verification missing isolation" }
            if ($RawText -notmatch "(?i)cleanup") { Fail "Restore verification missing cleanup status" }
            if ($RawText -notmatch "(?i)workflow|test path|blocked") { Fail "Restore verification missing workflow/path disposition" }
        }
        "recovery-owner" {
            if ($RawText -notmatch "(?i)recovery owner|owner role") { Fail "Recovery record missing owner" }
            if ($RawText -notmatch "(?i)least-privilege|rotation") { Fail "Recovery record missing least-privilege/rotation procedure" }
        }
        "validation" {
            if ($RawText -notmatch "(?i)quality gates|verification log") { Fail "Validation record missing quality-gate heading" }
            if ($RawText -notmatch "(?i)exit code") { Fail "Validation record must record exit codes" }
        }
        "handoff" {
            foreach ($field in @("reader_slo_status", "path_profile_status", "telemetry_status", "recovery_status", "overall_follow_up_disposition", "production_capacity_claim")) {
                if ($RawText -notmatch [regex]::Escape($field)) { Fail "Handoff missing $field" }
            }
        }
    }
}

function Run-Validation([string]$TargetKind, [string]$FilePath) {
    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) { Fail "Target artifact does not exist: $FilePath" }
    $raw = Get-Content -LiteralPath $FilePath -Raw -Encoding UTF8
    if ([System.IO.Path]::GetExtension($FilePath) -eq ".json") {
        $data = $raw | ConvertFrom-Json
        switch ($TargetKind) {
            "baseline" { Validate-Baseline $data $raw }
            "route-profile" { Validate-RouteProfile $data $raw }
            "latency-attribution" { Validate-LatencyAttribution $data $raw }
            "hosted-telemetry" { Validate-HostedTelemetry $data $raw }
            "backup-controls" { Validate-BackupControls $data $raw }
            "stage-1000" { Validate-Stage1000 $data $raw }
            default { Fail "Unknown JSON validation kind '$TargetKind'" }
        }
    }
    else {
        Validate-MarkdownDocument $TargetKind $raw
    }
    Write-Host "VALIDATION PASSED: [$TargetKind] $FilePath" -ForegroundColor Green
}

function New-SelfTestCell([string]$Campaign, [string]$Topology, [string]$Route, [string]$CacheState, [string]$Status) {
    $now = "2026-08-25T12:00:00Z"
    $isUnavailable = $Status -eq "unavailable"
    return [ordered]@{
        schema_version = 1
        campaign_id = $Campaign
        run_id = "run-test"
        fixture_binding_id = "fixture-0000000000000000"
        interval_start = $now
        interval_end = "2026-08-25T12:01:00Z"
        revision = "revision-test"
        topology = $Topology
        tls_verification_mode = "not_applicable"
        gate_role = if ($Topology -eq "private_network") { "slo_gate" } else { "diagnostic" }
        route = $Route
        cache_state = $CacheState
        cache_control_method = if ($CacheState -eq "warm") { "warmup_only" } else { "unavailable" }
        max_attempts_per_cell = 100
        sample_target = 50
        attempted_count = if ($isUnavailable) { 0 } else { 50 }
        sample_count = if ($isUnavailable) { 0 } else { 50 }
        completed_count = if ($isUnavailable) { 0 } else { 50 }
        valid_latency_count = if ($isUnavailable) { 0 } else { 50 }
        error_count = 0
        timeout_count = 0
        transport_error_count = 0
        status_counts = if ($isUnavailable) { [ordered]@{} } else { [ordered]@{"200" = 50} }
        expected_status = 200
        response_contract_status = if ($isUnavailable) { "unavailable" } else { "valid" }
        body_nonempty = -not $isUnavailable
        percentile_method = "nearest_rank_completed_ms"
        p50_ms = if ($isUnavailable) { $null } else { 10.0 }
        p95_ms = if ($isUnavailable) { $null } else { 20.0 }
        p99_ms = if ($isUnavailable) { $null } else { 30.0 }
        response_bytes_p95 = if ($isUnavailable) { $null } else { 100.0 }
        unavailable_fields = if ($isUnavailable) { @("target_not_configured") } else { @() }
        provenance = if ($isUnavailable) { "unavailable" } else { "reader_http_sample" }
        status = $Status
    }
}

function New-SelfTestBaseline() {
    return [ordered]@{
        schema_version = 1
        campaign_id = "camp-test"
        interval_start = "2026-08-25T12:00:00Z"
        interval_end = "2026-08-25T12:01:00Z"
        baseline_revision = "revision-test"
        topology = "split"
        target_aliases = $Topologies
        slo_gate_topology = "private_network"
        fixture_binding_method = "explicit_runtime_binding"
        fixture_binding_id = "fixture-0000000000000000"
        cache_control_method = "disposable_reader_reset_or_explicit_unavailable"
        worker_state = "stopped"
        original_queue_state = "paused"
        other_writers_state = "stopped"
        recovery_owner_role = "project_owner"
        recovery_escalation_role = "infrastructure_lead"
        required_routes = $RequiredRoutes
        diagnostic_routes = $DiagnosticRoutes
        stop_thresholds = [ordered]@{ max_transport_errors = 0; max_timeouts = 0 }
        configuration_keys = @("READER_STAGE_BASE_URL")
        authorized_profile = [ordered]@{ model = "1000_dau_equivalent"; profile = 1000; concurrency = 8; timeout_seconds = 20 }
        protected_surface_boundaries = [ordered]@{ writes = "forbidden"; provider_traffic = "forbidden"; worker_resume = "forbidden"; secrets = "not_recorded" }
        safety_state_source = "self_test"
    }
}

function Run-SelfTest() {
    $baseline = New-SelfTestBaseline
    Validate-Baseline ([PSCustomObject]$baseline) ($baseline | ConvertTo-Json -Depth 8)
    $cells = @()
    foreach ($topology in $Topologies) {
        foreach ($route in $RequiredRoutes) {
            $cells += New-SelfTestCell "camp-test" $topology $route "warm" "unavailable"
            $cells += New-SelfTestCell "camp-test" $topology $route "unknown" "unavailable"
        }
    }
    $routeProfile = [ordered]@{ schema_version = 1; campaign_id = "camp-test"; baseline_revision = "revision-test"; fixture_binding_id = "fixture-0000000000000000"; cells = $cells }
    Validate-RouteProfile ([PSCustomObject]$routeProfile) ($routeProfile | ConvertTo-Json -Depth 8)
    $badProfile = [ordered]@{ schema_version = 1; campaign_id = "camp-test"; baseline_revision = "revision-test"; fixture_binding_id = "fixture-0000000000000000"; cells = @($cells | Select-Object -Skip 1) }
    $rejected = $false
    try { Validate-RouteProfile ([PSCustomObject]$badProfile) ($badProfile | ConvertTo-Json -Depth 8) } catch { $rejected = $true }
    if (-not $rejected) { Fail "Self-test did not reject a missing matrix cell" }
    $blocker = [ordered]@{ blocker_id = "blk-test"; observed_utc = "2026-08-25T12:00:00Z"; affected_target = "caddy_detail"; measured_value = $null; budget_ms = 300; source_or_reason = "target_not_configured unavailable"; unavailable_reason = "target_not_configured"; owner_role = "project_owner"; next_action = "supply_stage_target"; retry_or_admission_condition = "retry only after target and fixture are authorized"; safety_disposition = "keep_capacity_unadmitted" }
    $stage = [ordered]@{ schema_version = 1; campaign_id = "camp-test"; run_id = "run-test"; baseline_revision = "revision-test"; candidate_revision = "revision-test"; fixture_binding_id = "fixture-0000000000000000"; profile = [ordered]@{ model = "1000_dau_equivalent"; dau = 1000 }; slo_gate_topology = "private_network"; route_cells = $cells; sample_targets = [ordered]@{ warm = 50; cold = 50 }; budgets = [ordered]@{ health_live = 100; catalog = 500; detail = 300; chapter = 750; search = 500 }; telemetry_snapshot_ids = @("telemetry-test"); provenance = "blocked_before_target_execution"; reader_slo_status = "blocked"; path_profile_status = "blocked"; telemetry_status = "unavailable"; recovery_status = "not_assessed"; overall_follow_up_disposition = "complete_with_quantified_blocker"; production_capacity_claim = "not_established"; blockers = @($blocker) }
    Validate-Stage1000 ([PSCustomObject]$stage) ($stage | ConvertTo-Json -Depth 10)
    Write-Host "ALL SELF-TESTS PASSED." -ForegroundColor Green
}

if ($SelfTest) {
    Run-SelfTest
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Kind) -or [string]::IsNullOrWhiteSpace($Path)) {
    Write-Error "Usage: validate_reader_follow_up.ps1 -Kind <baseline|route-profile|latency-attribution|hosted-telemetry|backup-controls|stage-1000|remediation-decision|restore-verification|recovery-owner|validation|handoff> -Path <path>"
    exit 1
}

Run-Validation $Kind $Path
