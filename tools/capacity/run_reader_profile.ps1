<#
.SYNOPSIS
    Runs the bounded 1k reader profile or records explicit unavailable cells.

.DESCRIPTION
    This wrapper never auto-selects a fixture, never starts a worker, never
    enqueues translation, and never treats a process exit as a capacity pass.
    When a target and fixture are supplied it delegates read-only HTTP sampling
    to the existing phase-6 client. Cold-cache samples require the separately
    verified disposable reader/cache reset helper.
#>
[CmdletBinding()]
param(
    [switch]$ReadOnly,
    [ValidateSet(1000)]
    [int]$Profile = 1000,
    [string]$DirectBaseUrl,
    [string]$CaddyBaseUrl,
    [string]$CloudflareBaseUrl,
    [ValidateSet("caddy_loopback", "cloudflare_tunnel")]
    [string]$SloGateTopology = "cloudflare_tunnel",
    [string]$CaddyHostHeader,
    [string]$NovelSlug,
    [string]$ChapterId,
    [ValidateSet("unavailable", "disposable_reader_reset")]
    [string]$ColdCacheMode = "unavailable",
    [string]$ColdResetScript,
    [string]$ColdResetComposeProject,
    [string]$ColdResetComposeFile = "deploy/compose.yml",
    [string]$ColdResetComposeEnvFile,
    [string]$BaselinePath = "artifacts/operations/reader-capacity-follow-up/baseline.json",
    [string]$TelemetryPath = "artifacts/operations/reader-capacity-follow-up/hosted-telemetry.json",
    [string]$RunId,
    [string]$ReportDir = "artifacts/operations/reader-capacity-follow-up/reader-stage-1000",
    [ValidateRange(50, 10000)]
    [int]$WarmSamples = 50,
    [ValidateRange(50, 10000)]
    [int]$ColdSamples = 50,
    [ValidateRange(50, 10000)]
    [int]$MaxAttemptsPerCell = 100,
    [ValidateRange(1, 64)]
    [int]$Concurrency = 8,
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 20,
    [switch]$Insecure
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $ReadOnly) {
    Write-Error "This profile is read-only; pass -ReadOnly explicitly."
    exit 2
}

$RequiredRoutes = @("health_live", "catalog", "detail", "chapter", "search")
$DiagnosticRoutes = @("health_ready", "ranking_daily", "ranking_weekly", "ranking_monthly", "home")
$AllRoutes = $RequiredRoutes + $DiagnosticRoutes
$Budgets = [ordered]@{ health_live = 100; catalog = 500; detail = 300; chapter = 750; search = 500 }
$TargetParameters = [ordered]@{
    direct_service = @{ supplied = $DirectBaseUrl; env = "READER_DIRECT_BASE_URL" }
    caddy_loopback = @{ supplied = $CaddyBaseUrl; env = "READER_STAGE_BASE_URL" }
    cloudflare_tunnel = @{ supplied = $CloudflareBaseUrl; env = "READER_CLOUDFLARE_BASE_URL" }
}
$ColdResetProofs = @()

function Get-EnvValue([string]$Name) {
    $property = Get-Item -Path ("Env:" + $Name) -ErrorAction SilentlyContinue
    if ($null -eq $property) { return $null }
    $value = [string]$property.Value
    if ([string]::IsNullOrWhiteSpace($value)) { return $null }
    return $value.Trim()
}

function Get-PowerShellCommand() {
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($null -ne $pwsh) { return [string]$pwsh.Source }
    $powershell = Get-Command powershell -ErrorAction SilentlyContinue
    if ($null -ne $powershell) { return [string]$powershell.Source }
    return $null
}

function Resolve-Target([string]$Alias) {
    $config = $TargetParameters[$Alias]
    $value = [string]$config.supplied
    if ([string]::IsNullOrWhiteSpace($value)) { $value = [string](Get-EnvValue ([string]$config.env)) }
    if ([string]::IsNullOrWhiteSpace($value)) { return $null }
    $uri = $null
    if (-not [Uri]::TryCreate($value, [UriKind]::Absolute, [ref]$uri)) { throw "Target alias '$Alias' is not a valid absolute URI." }
    if ($null -ne $uri.UserInfo -and -not [string]::IsNullOrWhiteSpace($uri.UserInfo)) { throw "Target alias '$Alias' may not contain URI credentials." }
    if ($Alias -eq "cloudflare_tunnel" -and $uri.Scheme -ine "https" -and -not $Insecure) { throw "Target alias 'cloudflare_tunnel' requires an HTTPS URL unless -Insecure is explicitly supplied." }
    return $value.TrimEnd('/')
}

function Get-OpaqueFixtureId() {
    if ([string]::IsNullOrWhiteSpace($NovelSlug) -or [string]::IsNullOrWhiteSpace($ChapterId)) { return "not-supplied" }
    $bytes = [Text.Encoding]::UTF8.GetBytes("$NovelSlug|$ChapterId")
    $hash = [Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    return "fixture-" + (($hash | ForEach-Object { $_.ToString("x2") }) -join "").Substring(0, 16)
}

function Get-SafeErrorClass([string]$Name) {
    switch -Regex ($Name) {
        "timeout" { return "timeout" }
        "connect" { return "connect" }
        "read|write|protocol|network|remote" { return "transport" }
        "redirect" { return "redirect" }
        default { return "other" }
    }
}

function New-Blocker([string]$Id, [string]$Target, [string]$Reason, [string]$UnavailableReason, [Nullable[double]]$MeasuredValue, [Nullable[double]]$Budget, [string]$NextAction, [string]$RetryCondition) {
    return [ordered]@{
        blocker_id = $Id
        observed_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        affected_target = $Target
        measured_value = $MeasuredValue
        budget_ms = $Budget
        source_or_reason = "$Reason unavailable"
        unavailable_reason = $UnavailableReason
        owner_role = "project_owner"
        next_action = $NextAction
        retry_or_admission_condition = $RetryCondition
        safety_disposition = "keep_capacity_unadmitted"
    }
}

function New-Cell([string]$CampaignId, [string]$RunId, [string]$FixtureId, [string]$Revision, [string]$Topology, [string]$Route, [string]$CacheState, [string]$Status, [string]$Reason, [int]$SampleTarget, [object]$Summary, [string]$CacheControlMethod = "unavailable", [string]$CacheResetProofId = $null) {
    $start = [DateTime]::UtcNow
    $end = $start
    $expectedStatus = if ($Route -eq "health_ready") { 503 } else { 200 }
    $unavailable = $Status -eq "unavailable"
    $statusCounts = [ordered]@{}
    $sampleCount = 0
    $attempted = 0
    $completed = 0
    $valid = 0
    $errors = 0
    $timeouts = 0
    $transport = 0
    $errorClassCounts = [ordered]@{}
    $p50 = $null
    $p95 = $null
    $p99 = $null
    $bytes = $null
    $responseStatus = "unavailable"
    $bodyNonEmpty = $false
    $provenance = "unavailable"
    if (-not $unavailable) {
        $attempted = [int]$Summary.samples
        $sampleCount = $attempted
        $timeouts = [int]$Summary.timeouts
        $statusProperties = @($Summary.statuses.PSObject.Properties)
        foreach ($property in $statusProperties) {
            $statusCounts[[string]$property.Name] = [int]$property.Value
            if ([string]$property.Name -eq "error") {
                $errors += [int]$property.Value
                $transport += [int]$property.Value
            }
        }
        $errorProperty = $Summary.PSObject.Properties["errors"]
        if ($null -ne $errorProperty -and $null -ne $errorProperty.Value) {
            foreach ($property in @($errorProperty.Value.PSObject.Properties)) {
                $safeClass = Get-SafeErrorClass ([string]$property.Name)
                if (-not $errorClassCounts.Contains($safeClass)) { $errorClassCounts[$safeClass] = 0 }
                $errorClassCounts[$safeClass] += [int]$property.Value
            }
        }
        $completed = $attempted - $timeouts - $transport
        $valid = $completed
        $p50 = [double]$Summary.p50_ms
        $p95 = [double]$Summary.p95_ms
        $p99 = [double]$Summary.p99_ms
        $bytes = [double]$Summary.average_response_bytes
        $expectedCount = 0
        if ($statusCounts.Contains($expectedStatus.ToString())) { $expectedCount = [int]$statusCounts[$expectedStatus.ToString()] }
        $bodyNonEmpty = $expectedCount -eq $attempted -and $bytes -gt 0
        $responseStatus = if ($bodyNonEmpty) { "valid" } else { "invalid" }
        $provenance = "reader_http_sample"
        if ($valid -lt $SampleTarget -or $timeouts -gt 0 -or $transport -gt 0) {
            $Status = "unavailable"
            $unavailable = $true
            $Reason = "profile_runner_unavailable"
            $p50 = $null
            $p95 = $null
            $p99 = $null
            $bytes = $null
            $responseStatus = "unavailable"
            $provenance = "unavailable"
        }
        elseif (-not $bodyNonEmpty -or ($Budgets.Contains($Route) -and $p95 -gt [double]$Budgets[$Route])) {
            $Status = "failed"
        }
    }
    if ($unavailable) {
        # Preserve the attempted/completed/error/timeout counters as diagnostic
        # evidence, but never count an incomplete cell as valid samples.
        $sampleCount = 0
        $valid = 0
        $responseStatus = "unavailable"
        $provenance = "unavailable"
    }
    return [ordered]@{
        schema_version = 1
        campaign_id = $CampaignId
        run_id = $RunId
        fixture_binding_id = $FixtureId
        interval_start = $start.ToString("yyyy-MM-ddTHH:mm:ssZ")
        interval_end = $end.ToString("yyyy-MM-ddTHH:mm:ssZ")
        revision = $Revision
        topology = $Topology
        tls_verification_mode = if ($Insecure) { "approved_disposable_insecure" } else { "verified" }
        gate_role = if ($Topology -eq $SloGateTopology) { "slo_gate" } else { "diagnostic" }
        route = $Route
        cache_state = $CacheState
        cache_control_method = $CacheControlMethod
        cache_reset_proof_id = $CacheResetProofId
        max_attempts_per_cell = $MaxAttemptsPerCell
        sample_target = $SampleTarget
        attempted_count = $attempted
        sample_count = $sampleCount
        completed_count = $completed
        valid_latency_count = $valid
        error_count = $errors
        timeout_count = $timeouts
        transport_error_count = $transport
        error_class_counts = $errorClassCounts
        status_counts = $statusCounts
        expected_status = $expectedStatus
        response_contract_status = $responseStatus
        body_nonempty = $bodyNonEmpty
        percentile_method = "nearest_rank_completed_ms"
        p50_ms = $p50
        p95_ms = $p95
        p99_ms = $p99
        response_bytes_p95 = $bytes
        unavailable_fields = if ($unavailable) { @($Reason) } else { @() }
        provenance = $provenance
        status = $Status
    }
}

function Invoke-TargetSamples([string]$Alias, [string]$BaseUrl, [string]$HostHeader, [string]$CampaignId, [string]$RunId, [string]$FixtureId, [string]$Revision, [string]$Route = $null, [switch]$SkipWarmup) {
    $pythonPath = $null
    foreach ($candidate in @(
        (Join-Path (Get-Location) ".venv\Scripts\python.exe"),
        (Join-Path (Get-Location) ".venv/bin/python"),
        "python"
    )) {
        $available = if ($candidate -eq "python") {
            $null -ne (Get-Command python -ErrorAction SilentlyContinue)
        }
        else {
            Test-Path -LiteralPath $candidate -PathType Leaf
        }
        if ($available) {
            $pythonPath = $candidate
            break
        }
    }
    if ($null -eq $pythonPath) {
        return [ordered]@{ available = $false; reason = "profile_runner_unavailable"; summaries = @{} }
    }
    if ([string]::IsNullOrWhiteSpace($NovelSlug) -or [string]::IsNullOrWhiteSpace($ChapterId)) {
        return [ordered]@{ available = $false; reason = "fixture_not_configured"; summaries = @{} }
    }
    if ($Alias -eq "caddy_loopback" -and [string]::IsNullOrWhiteSpace($HostHeader)) {
        return [ordered]@{ available = $false; reason = "caddy_host_binding_unavailable"; summaries = @{} }
    }
    $tempRoot = Join-Path $ReportDir ".profile-$RunId-$Alias"
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    $rawPath = Join-Path $tempRoot "raw.json"
    $logPath = Join-Path $tempRoot "runner.log"
    try {
        $arguments = @(
            "backend/tests/run_phase6_acceptance.py", "workload",
            "--base-url", $BaseUrl,
            "--novel-slug", $NovelSlug,
            "--chapter-id", $ChapterId,
            "--samples", [string]$WarmSamples,
            "--concurrency", [string]$Concurrency,
            "--timeout-seconds", [string]$TimeoutSeconds,
            "--json-out", $rawPath
        )
        if (-not [string]::IsNullOrWhiteSpace($Route)) { $arguments += @("--route", $Route) }
        if ($SkipWarmup) { $arguments += "--skip-warmup" }
        if (-not [string]::IsNullOrWhiteSpace($HostHeader)) { $arguments += @("--host-header", $HostHeader) }
        if ($Insecure) { $arguments += "--insecure" }
        & $pythonPath @arguments *> $logPath
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0 -or -not (Test-Path -LiteralPath $rawPath -PathType Leaf)) {
            return [ordered]@{ available = $false; reason = "profile_runner_unavailable"; summaries = @{} }
        }
        $raw = Get-Content -LiteralPath $rawPath -Raw | ConvertFrom-Json
        return [ordered]@{
            available = $true
            reason = $null
            summaries = $raw.routes
            started_at = $raw.started_at_utc
            warmup_executed = [bool]$raw.warmup_executed
        }
    }
    finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-ColdReset([string]$Topology, [string]$Route) {
    $shell = Get-PowerShellCommand
    if ($null -eq $shell -or [string]::IsNullOrWhiteSpace($ColdResetScript)) {
        return [ordered]@{ available = $false; reason = "cold_cache_control_unavailable"; proof_id = $null }
    }
    $proofPath = Join-Path $ReportDir (".cold-reset-{0}-{1}-{2}.json" -f $RunId, $Topology, $Route)
    $logPath = Join-Path $ReportDir (".cold-reset-{0}-{1}-{2}.log" -f $RunId, $Topology, $Route)
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $ColdResetScript,
        "-ComposeProject",
        $ColdResetComposeProject,
        "-ComposeFile",
        $ColdResetComposeFile,
        "-ComposeEnvFile",
        $ColdResetComposeEnvFile,
        "-OutputPath",
        $proofPath
    )
    & $shell @arguments *> $logPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $proofPath -PathType Leaf)) {
        return [ordered]@{ available = $false; reason = "cold_cache_control_unavailable"; proof_id = $null }
    }
    try {
        $proof = Get-Content -LiteralPath $proofPath -Raw | ConvertFrom-Json
        $proofId = [string]$proof.proof_id
        if ([string]$proof.status -ne "reset" -or [string]::IsNullOrWhiteSpace($proofId)) {
            return [ordered]@{ available = $false; reason = "cold_cache_control_unavailable"; proof_id = $null }
        }
        return [ordered]@{ available = $true; reason = $null; proof_id = $proofId; observed_utc = [string]$proof.observed_utc }
    }
    catch {
        return [ordered]@{ available = $false; reason = "cold_cache_control_unavailable"; proof_id = $null }
    }
}

function New-Attribution([string]$CampaignId, [string]$RunId, [string]$Revision, [string]$FixtureId, [string]$ProfilePath) {
    $now = [DateTime]::UtcNow
    $layers = [ordered]@{}
    foreach ($name in @("proxy_connect", "proxy_upstream", "application", "db_checkout", "db_statement", "db_commit", "r2_exact_read", "serialization", "network_remainder")) {
        $layers[$name] = [ordered]@{ status = "unavailable"; unavailable_reason = "runtime_state_unavailable" }
    }
    $routes = @()
    foreach ($route in $RequiredRoutes) {
        $routes += [ordered]@{ route = $route; topology = $SloGateTopology; cache_state = "warm"; revision = $Revision; layers = $layers }
    }
    return [ordered]@{
        schema_version = 1
        campaign_id = $CampaignId
        run_id = $RunId
        interval_start = $now.AddMinutes(-1).ToString("yyyy-MM-ddTHH:mm:ssZ")
        interval_end = $now.ToString("yyyy-MM-ddTHH:mm:ssZ")
        revision = $Revision
        fixture_binding_id = $FixtureId
        source_profile = $ProfilePath
        classification = "mixed_or_unavailable"
        routes = $routes
        blockers = @([ordered]@{ blocker_id = "blk-layer-telemetry-unavailable"; observed_utc = $now.ToString("yyyy-MM-ddTHH:mm:ssZ"); affected_target = "reader_latency_layers"; measured_value = $null; budget_ms = $null; source_or_reason = "layer telemetry unavailable"; unavailable_reason = "runtime_state_unavailable"; owner_role = "project_owner"; next_action = "enable fixed-label layer telemetry in an approved window"; retry_or_admission_condition = "do not select a local remediation until non-overlapping layer evidence exists"; safety_disposition = "keep_capacity_unadmitted" })
    }
}

function Resolve-CaddyHostHeader() {
    $value = $CaddyHostHeader
    if ([string]::IsNullOrWhiteSpace($value)) { $value = Get-EnvValue "READER_CADDY_HOST_HEADER" }
    if ([string]::IsNullOrWhiteSpace($value)) { return $null }
    $value = $value.Trim()
    if ($value -match "[\r\n/\\@?#]") { throw "CaddyHostHeader contains an invalid header character." }
    return $value
}

$baseline = Get-Content -LiteralPath $BaselinePath -Raw | ConvertFrom-Json
$campaignId = [string]$baseline.campaign_id
$revision = [string]$baseline.baseline_revision
$fixtureId = Get-OpaqueFixtureId
$baselineFixtureId = [string]$baseline.fixture_binding_id
$caddyHostHeader = Resolve-CaddyHostHeader
$runId = if ([string]::IsNullOrWhiteSpace($RunId)) { [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ") } else { $RunId }
if ([string]$baseline.slo_gate_topology -ne $SloGateTopology) { throw "SloGateTopology must match the baseline selection." }
if ($baselineFixtureId -ne $fixtureId) { throw "The supplied fixture does not match the baseline fixture binding." }
if ($ColdCacheMode -eq "disposable_reader_reset") {
    if ([string]::IsNullOrWhiteSpace($ColdResetScript) -or -not (Test-Path -LiteralPath $ColdResetScript -PathType Leaf)) {
        throw "ColdCacheMode disposable_reader_reset requires an existing ColdResetScript."
    }
    if ([string]::IsNullOrWhiteSpace($ColdResetComposeProject) -or $ColdResetComposeProject -notmatch "^reader-capacity-test-[A-Za-z0-9_-]+$") {
        throw "ColdCacheMode disposable_reader_reset requires an isolated reader-capacity Compose project."
    }
}

if (-not (Test-Path -LiteralPath $ReportDir -PathType Container)) { New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null }
$cells = @()
$blockers = @()
$targetResults = @{}

foreach ($alias in @("direct_service", "caddy_loopback", "cloudflare_tunnel")) {
    $targetUrl = Resolve-Target $alias
    $targetResults[$alias] = if ($null -eq $targetUrl) { [ordered]@{ configured = $false; reason = if ($alias -eq "direct_service") { "direct_service_unavailable" } elseif ($alias -eq "cloudflare_tunnel") { "cloudflare_tunnel_unavailable" } else { "target_not_configured" } } } else { [ordered]@{ configured = $true; reason = $null; url = $targetUrl } }
    $warmResult = $null
    if ($null -ne $targetUrl) {
        $hostHeader = if ($alias -eq "caddy_loopback") { $caddyHostHeader } else { $null }
        $warmResult = Invoke-TargetSamples $alias $targetUrl $hostHeader $campaignId $runId $fixtureId $revision
    }
    foreach ($route in $AllRoutes) {
        $warmReason = if ($fixtureId -eq "not-supplied") { "fixture_not_configured" } elseif ($null -eq $targetUrl) { [string]$targetResults[$alias].reason } elseif ($null -eq $warmResult -or -not $warmResult.available) { [string]$warmResult.reason } else { $null }
        $summary = if ($null -ne $warmResult -and $warmResult.available -and $null -ne $warmResult.summaries.PSObject.Properties[$route]) { $warmResult.summaries.$route } else { $null }
        if ([string]::IsNullOrWhiteSpace($warmReason) -and $null -ne $summary) {
            $budget = if ($Budgets.Contains($route)) { [double]$Budgets[$route] } else { $null }
            $cell = New-Cell $campaignId $runId $fixtureId $revision $alias $route "warm" "passed" "" $WarmSamples $summary "warmup_only" $null
            if ($null -ne $budget -and $null -ne $cell.p95_ms -and [double]$cell.p95_ms -gt $budget) { $cell.status = "failed" }
        }
        else {
            $cell = New-Cell $campaignId $runId $fixtureId $revision $alias $route "warm" "unavailable" $warmReason $WarmSamples $null "warmup_only" $null
        }
        $cells += $cell

        $coldCell = $null
        if ($null -eq $targetUrl) {
            $coldCell = New-Cell $campaignId $runId $fixtureId $revision $alias $route "unknown" "unavailable" "cold_cache_control_unavailable" $ColdSamples $null "unavailable" $null
        }
        elseif ($ColdCacheMode -eq "unavailable") {
            $coldCell = New-Cell $campaignId $runId $fixtureId $revision $alias $route "unknown" "unavailable" "cold_cache_control_unavailable" $ColdSamples $null "unavailable" $null
        }
        else {
            $reset = Invoke-ColdReset $alias $route
            if (-not $reset.available) {
                $coldCell = New-Cell $campaignId $runId $fixtureId $revision $alias $route "unknown" "unavailable" ([string]$reset.reason) $ColdSamples $null "unavailable" $null
            }
            else {
                $hostHeader = if ($alias -eq "caddy_loopback") { $caddyHostHeader } else { $null }
                $coldResult = Invoke-TargetSamples $alias $targetUrl $hostHeader $campaignId $runId $fixtureId $revision $route -SkipWarmup
                $coldSummary = if ($coldResult.available -and $null -ne $coldResult.summaries.PSObject.Properties[$route]) { $coldResult.summaries.$route } else { $null }
                $proofId = [string]$reset.proof_id
                $proofObserved = [string]$reset.observed_utc
                if ([string]::IsNullOrWhiteSpace($proofObserved)) { $proofObserved = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ") }
                $ColdResetProofs += [ordered]@{
                    proof_id = $proofId
                    topology = $alias
                    route = $route
                    cache_state = "cold"
                    observed_utc = $proofObserved
                }
                if ($null -eq $coldSummary) {
                    $coldCell = New-Cell $campaignId $runId $fixtureId $revision $alias $route "cold" "unavailable" "profile_runner_unavailable" $ColdSamples $null "disposable_reader_reset" $proofId
                }
                else {
                    $budget = if ($Budgets.Contains($route)) { [double]$Budgets[$route] } else { $null }
                    $coldCell = New-Cell $campaignId $runId $fixtureId $revision $alias $route "cold" "passed" "" $ColdSamples $coldSummary "disposable_reader_reset" $proofId
                    if ($null -ne $budget -and $null -ne $coldCell.p95_ms -and [double]$coldCell.p95_ms -gt $budget) { $coldCell.status = "failed" }
                }
            }
        }
        $cells += $coldCell
        if ($route -in $RequiredRoutes) {
            $budgetValue = if ($Budgets.Contains($route)) { [Nullable[double]]$Budgets[$route] } else { $null }
            if ($cell.status -eq "unavailable") {
                $warmReason = [string](@($cell.unavailable_fields)[0])
                $blockers += New-Blocker "blk-$alias-$route-warm" "$alias`_$route`_warm" $warmReason $warmReason $null $budgetValue "supply the missing target or fixture and rerun the warm cell" "retry only after the named warm dimension is independently verified"
            }
            if ($coldCell.status -eq "unavailable") {
                $coldReason = [string](@($coldCell.unavailable_fields)[0])
                $blockers += New-Blocker "blk-$alias-$route-cold" "$alias`_$route`_cold" $coldReason $coldReason $null $budgetValue "supply an approved disposable cold-cache control and rerun the cold cell" "retry only after controlled cold-cache semantics are independently verified"
            }
        }
    }
}

$uniqueById = @{}
foreach ($blocker in $blockers) {
    $blockerId = [string]$blocker["blocker_id"]
    if (-not $uniqueById.ContainsKey($blockerId)) {
        $uniqueById[$blockerId] = $blocker
    }
}
$uniqueBlockers = @($uniqueById.Values)
$gateCells = @($cells | Where-Object { $_.topology -eq $SloGateTopology -and $_.route -in $RequiredRoutes })
$readerSlo = if (@($gateCells | Where-Object { $_.status -eq "unavailable" }).Count -gt 0) { "blocked" } elseif (@($gateCells | Where-Object { $_.status -eq "failed" }).Count -gt 0) { "failed" } else { "passed" }
$pathStatus = if (@($cells | Where-Object { $_.route -in $RequiredRoutes -and $_.status -eq "unavailable" }).Count -eq 0) { "complete" } elseif ($readerSlo -eq "blocked") { "blocked" } else { "partial" }
$telemetrySnapshotIds = @()
$telemetryStatus = "unavailable"
if (-not [string]::IsNullOrWhiteSpace($TelemetryPath) -and (Test-Path -LiteralPath $TelemetryPath -PathType Leaf)) {
    $telemetry = Get-Content -LiteralPath $TelemetryPath -Raw | ConvertFrom-Json
    $telemetrySnapshotIds = @($telemetry.snapshots | ForEach-Object { [string]$_.snapshot_id })
    if (@($telemetry.snapshots | Where-Object { $_.provenance -ne "unavailable" }).Count -gt 0) { $telemetryStatus = "partial" } else { $telemetryStatus = "unavailable" }
}
$profileModel = [ordered]@{ model = "1000_dau_equivalent"; dau = 1000; daily_requests = 8000; peak_rps = 0.444444; peak_window_seconds = 1800 }
$routeProfile = [ordered]@{
    schema_version = 1
    campaign_id = $campaignId
    baseline_revision = $revision
    candidate_revision = $revision
    fixture_binding_id = $fixtureId
    execution_status = if ($readerSlo -eq "blocked") { "complete_with_quantified_blocker" } else { "complete" }
    cold_cache_mode = $ColdCacheMode
    cells = $cells
}
$routeProfilePath = Join-Path (Get-Location) "artifacts/operations/reader-capacity-follow-up/route-profile.json"
$routeProfile | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $routeProfilePath -Encoding utf8

$stage = [ordered]@{
    schema_version = 1
    campaign_id = $campaignId
    run_id = $runId
    baseline_revision = $revision
    candidate_revision = $revision
    fixture_binding_id = $fixtureId
    profile = $profileModel
    slo_gate_topology = $SloGateTopology
    route_cells = $cells
    sample_targets = [ordered]@{ warm = $WarmSamples; cold = $ColdSamples; max_attempts_per_cell = $MaxAttemptsPerCell; concurrency = $Concurrency; timeout_seconds = $TimeoutSeconds; cold_cache_mode = $ColdCacheMode }
    cache_reset_proofs = @($ColdResetProofs)
    budgets = $Budgets
    telemetry_snapshot_ids = $telemetrySnapshotIds
    provenance = if ($readerSlo -eq "blocked") { "blocked_or_unavailable_reader_profile" } else { "reader_http_sample" }
    reader_slo_status = $readerSlo
    path_profile_status = $pathStatus
    telemetry_status = $telemetryStatus
    recovery_status = "not_assessed"
    overall_follow_up_disposition = if (@($uniqueBlockers).Count -gt 0) { "complete_with_quantified_blocker" } else { "complete" }
    production_capacity_claim = "not_established"
    blockers = $uniqueBlockers
}
$reportPath = Join-Path (Get-Location) (Join-Path $ReportDir ("reader-stage-{0}-{1}.json" -f $Profile, $runId))
$stage | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $reportPath -Encoding utf8

$attributionPath = Join-Path (Get-Location) "artifacts/operations/reader-capacity-follow-up/latency-attribution.json"
$attribution = New-Attribution $campaignId $runId $revision $fixtureId $routeProfilePath
$attribution | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $attributionPath -Encoding utf8

$validator = Join-Path $PSScriptRoot "validate_reader_follow_up.ps1"
$validatorShell = Get-PowerShellCommand
if ($null -eq $validatorShell) { throw "PowerShell runtime is required to validate the reader profile." }
& $validatorShell -NoProfile -ExecutionPolicy Bypass -File $validator -Kind route-profile -Path $routeProfilePath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $validatorShell -NoProfile -ExecutionPolicy Bypass -File $validator -Kind stage-1000 -Path $reportPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $validatorShell -NoProfile -ExecutionPolicy Bypass -File $validator -Kind latency-attribution -Path $attributionPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ("Profile artifact generated: {0}; reader_slo_status={1}; path_profile_status={2}; blockers={3}" -f $reportPath, $readerSlo, $pathStatus, @($uniqueBlockers).Count) -ForegroundColor Yellow
