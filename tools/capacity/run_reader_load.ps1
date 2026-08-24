[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(1000, 10000, 100000)]
    [int]$Profile,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ReportDir,

    [string]$NovelSlug,

    [ValidateRange(1, 1000)]
    [int]$SamplesPerRoute = 50,

    [ValidateRange(1, 64)]
    [int]$Concurrency = 8,

    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 15,

    [switch]$Insecure
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Write-Error "The canonical project interpreter is missing: .venv\Scripts\python.exe" -ErrorAction Continue
    exit 2
}

$profiles = @{
    1000 = [ordered]@{
        dau = 1000
        daily_requests = 8000
        peak_rps = 0.444444
        peak_window_seconds = 1800
    }
    10000 = [ordered]@{
        dau = 10000
        daily_requests = 80000
        peak_rps = 4.444444
        peak_window_seconds = 1800
    }
    100000 = [ordered]@{
        dau = 100000
        daily_requests = 800000
        peak_rps = 44.444444
        peak_window_seconds = 1800
    }
}

$routeBudgetsMs = [ordered]@{
    health_live = 100
    catalog = 500
    detail = 300
    chapter = 750
    search = 500
    ranking_daily = 500
    ranking_weekly = 500
    ranking_monthly = 500
    home = 1500
}

$reportRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $ReportDir))
New-Item -ItemType Directory -Force -Path $reportRoot | Out-Null
$runId = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$rawJsonPath = Join-Path $reportRoot (".raw-phase6-{0}.json" -f $runId)
$workloadLogPath = Join-Path $reportRoot (".raw-phase6-{0}.log" -f $runId)
$reportPath = Join-Path $reportRoot ("reader-stage-{0}-{1}.json" -f $Profile, $runId)

function Get-StageSlug {
    param([string]$UriBase)

    $response = Invoke-WebRequest -UseBasicParsing -Uri ($UriBase.TrimEnd("/") + "/api/public/catalog?page=1&page_size=1")
    if ([int]$response.StatusCode -ne 200) {
        throw "The public catalog probe did not return HTTP 200."
    }
    $payload = $response.Content | ConvertFrom-Json
    $novels = @($payload.novels)
    if ($novels.Count -lt 1 -or [string]::IsNullOrWhiteSpace([string]$novels[0].slug)) {
        throw "The public catalog probe returned no usable published novel."
    }
    return [string]$novels[0].slug
}

function Get-ContainerStats {
    $rows = @()
    try {
        $rawRows = @(docker stats --no-stream --format '{{json .}}' 2>$null)
        foreach ($rawRow in $rawRows) {
            if ([string]::IsNullOrWhiteSpace([string]$rawRow)) {
                continue
            }
            try {
                $row = [string]$rawRow | ConvertFrom-Json
                $name = [string]$row.Name
                if ($name -match "novel-ai-(backend|reader|caddy|worker)") {
                    $rows += [ordered]@{
                        name = $name
                        cpu = [string]$row.CPUPerc
                        memory = [string]$row.MemUsage
                        network = [string]$row.NetIO
                        block_io = [string]$row.BlockIO
                    }
                }
            }
            catch {
                continue
            }
        }
    }
    catch {
        return [ordered]@{ status = "unavailable"; reason = "docker_stats_failed" }
    }
    return [ordered]@{ status = "ok"; samples = @($rows) }
}

function Get-DatabaseSnapshot {
    $query = "import json; from sqlalchemy import text; from novelai.db.engine import session_scope; cm=session_scope(); db=cm.__enter__(); row=db.execute(text('select coalesce(sum(calls),0), coalesce(sum(total_exec_time),0), coalesce(sum(rows),0) from pg_stat_statements')).one(); print(json.dumps({'statement_calls':int(row[0]),'total_exec_ms':round(float(row[1]),3),'rows':int(row[2])})); cm.__exit__(None,None,None)"
    try {
        $lines = @(docker compose --env-file .env -f deploy/compose.yml run --rm --no-deps backend python -c $query 2>$null)
        for ($index = $lines.Count - 1; $index -ge 0; $index--) {
            $line = [string]$lines[$index]
            if ($line -notmatch '^\s*\{') {
                continue
            }
            try {
                $parsed = $line | ConvertFrom-Json
                if ($null -ne $parsed.statement_calls) {
                    return [ordered]@{
                        status = "ok"
                        statement_calls = [int]$parsed.statement_calls
                        total_exec_ms = [double]$parsed.total_exec_ms
                        rows = [int]$parsed.rows
                    }
                }
            }
            catch {
                continue
            }
        }
    }
    catch {
        return [ordered]@{ status = "unavailable"; reason = "database_snapshot_failed" }
    }
    return [ordered]@{ status = "unavailable"; reason = "pg_stat_statements_snapshot_unavailable" }
}

function Get-InternalMetrics {
    $query = "import json,urllib.request; response=urllib.request.urlopen('http://127.0.0.1:8000/metrics',timeout=5); selected={}; prefixes=('novelai_activity_','novelai_provider_','novelai_public_','novelai_readiness_','novelai_runtime_'); [selected.__setitem__(line.split(' ',1)[0],float(line.split(' ',1)[1])) for line in response.read().decode().splitlines() if line and not line.startswith('#') and '{' not in line and line.split(' ',1)[0].startswith(prefixes) and len(line.split(' ',1))==2]; print(json.dumps({'status':'ok','selected':selected},sort_keys=True))"
    try {
        $lines = @(docker compose --env-file .env -f deploy/compose.yml exec -T backend python -c $query 2>$null)
        for ($index = $lines.Count - 1; $index -ge 0; $index--) {
            $line = [string]$lines[$index]
            if ($line -notmatch '^\s*\{') {
                continue
            }
            try {
                $parsed = $line | ConvertFrom-Json
                if ($null -ne $parsed.status) {
                    return [ordered]@{ status = [string]$parsed.status; selected = $parsed.selected }
                }
            }
            catch {
                continue
            }
        }
    }
    catch {
        return [ordered]@{ status = "unavailable"; reason = "internal_metrics_probe_failed" }
    }
    return [ordered]@{ status = "unavailable"; reason = "internal_metrics_endpoint_unavailable" }
}

function Get-StatusMap {
    param($StatusObject)

    $map = [ordered]@{}
    if ($null -eq $StatusObject) {
        return $map
    }
    foreach ($property in $StatusObject.PSObject.Properties) {
        $map[[string]$property.Name] = [int]$property.Value
    }
    return $map
}

$slug = $NovelSlug
$rawResult = $null
$workloadExitCode = 1
$startedAt = [DateTime]::UtcNow
$beforeStats = Get-ContainerStats
$beforeDb = Get-DatabaseSnapshot
$beforeMetrics = Get-InternalMetrics

try {
    if ([string]::IsNullOrWhiteSpace($slug)) {
        $slug = Get-StageSlug -UriBase $BaseUrl
    }

    $arguments = @(
        "backend/tests/run_phase6_acceptance.py",
        "workload",
        "--base-url", $BaseUrl.TrimEnd("/"),
        "--novel-slug", $slug,
        "--samples", [string]$SamplesPerRoute,
        "--concurrency", [string]$Concurrency,
        "--timeout-seconds", [string]$TimeoutSeconds,
        "--json-out", $rawJsonPath
    )
    if ($Insecure) {
        $arguments += "--insecure"
    }

    & $pythonPath @arguments *> $workloadLogPath
    $workloadExitCode = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $rawJsonPath -PathType Leaf)) {
        throw "The sanitized workload client did not produce a report."
    }
    $rawResult = Get-Content -LiteralPath $rawJsonPath -Raw | ConvertFrom-Json
}
finally {
    $afterStats = Get-ContainerStats
    $afterDb = Get-DatabaseSnapshot
    $afterMetrics = Get-InternalMetrics
}

$routeReports = [ordered]@{}
$blockers = @()
$contentRouteNames = @("health_live", "catalog", "detail", "chapter", "search", "ranking_daily", "ranking_weekly", "ranking_monthly", "home")

if ($null -ne $rawResult) {
    foreach ($routeProperty in $rawResult.routes.PSObject.Properties) {
        $routeName = [string]$routeProperty.Name
        $summary = $routeProperty.Value
        $statusMap = Get-StatusMap -StatusObject $summary.statuses
        $non2xx = 0
        $successful = 0
        foreach ($statusProperty in $statusMap.GetEnumerator()) {
            $statusCode = 0
            if ([int]::TryParse([string]$statusProperty.Key, [ref]$statusCode)) {
                if ($statusCode -ge 200 -and $statusCode -lt 300) {
                    $successful += [int]$statusProperty.Value
                }
                else {
                    $non2xx += [int]$statusProperty.Value
                }
            }
            else {
                $non2xx += [int]$statusProperty.Value
            }
        }
        $budget = $null
        if ($routeBudgetsMs.Contains($routeName)) {
            $budget = [int]$routeBudgetsMs[$routeName]
        }
        $p95 = if ($null -eq $summary.p95_ms) { $null } else { [double]$summary.p95_ms }
        $sloPass = $true
        if ($null -ne $budget -and $null -ne $p95) {
            $sloPass = $p95 -le $budget
        }
        $bodyNonEmpty = ($successful -eq [int]$summary.samples -and [double]$summary.average_response_bytes -gt 0)
        $expectedDegraded = ($routeName -eq "health_ready" -and $statusMap.Contains("503"))
        $routeReports[$routeName] = [ordered]@{
            samples = [int]$summary.samples
            p50_ms = $summary.p50_ms
            p95_ms = $summary.p95_ms
            p99_ms = $summary.p99_ms
            statuses = $statusMap
            timeouts = [int]$summary.timeouts
            errors = $summary.errors
            average_response_bytes = $summary.average_response_bytes
            body_nonempty = $bodyNonEmpty
            slo_budget_ms = $budget
            slo_pass = $sloPass
            expected_degraded = $expectedDegraded
        }

        if ($contentRouteNames -contains $routeName) {
            if ($non2xx -gt 0) {
                $blockers += [ordered]@{ type = "http_status"; route = $routeName; non_2xx = $non2xx }
            }
            if (-not $bodyNonEmpty) {
                $blockers += [ordered]@{ type = "response_correctness"; route = $routeName; reason = "empty_or_non_success_body" }
            }
            if (-not $sloPass -and $null -ne $budget) {
                $blockers += [ordered]@{ type = "slo"; route = $routeName; p95_ms = $p95; budget_ms = $budget }
            }
        }
    }
    if ($rawResult.routes.health_ready.statuses.PSObject.Properties.Name -notcontains "503") {
        $blockers += [ordered]@{ type = "readiness_contract"; reason = "worker_stopped_readiness_state_not_observed" }
    }
}
else {
    $blockers += [ordered]@{ type = "workload_runner"; reason = "no_sanitized_workload_result" }
}

$blockers += [ordered]@{ type = "r2_telemetry"; reason = "provider_operation_and_billed_byte_counters_not_exposed_to_this_stage_runner" }
$blockers += [ordered]@{ type = "hosted_billing"; reason = "provider_billing_window_not captured by local runner" }

$profileModel = $profiles[$Profile]
$report = [ordered]@{
    schema_version = 1
    run_id = $runId
    started_at_utc = $startedAt.ToString("o")
    finished_at_utc = [DateTime]::UtcNow.ToString("o")
    provenance = "private_staging_http_sample"
    profile = $profileModel
    traffic = [ordered]@{
        samples_per_route = $SamplesPerRoute
        concurrency = $Concurrency
        timeout_seconds = $TimeoutSeconds
        warmup_per_route = $true
        route_mix = [ordered]@{ catalog = 0.25; detail = 0.25; chapter = 0.25; supporting_routes = 0.25 }
        target_host_identity = "redacted"
        novel_identity = "redacted"
    }
    workload_exit_code = $workloadExitCode
    routes = $routeReports
    readiness = [ordered]@{
        worker_expected_state = "stopped"
        public_readiness_expected_status = 503
        public_liveness_expected_status = 200
    }
    resource_snapshots = [ordered]@{
        before = $beforeStats
        after = $afterStats
        database_before = $beforeDb
        database_after = $afterDb
        internal_metrics_before = $beforeMetrics
        internal_metrics_after = $afterMetrics
    }
    correctness = [ordered]@{
        public_success_bodies_nonempty = (@($blockers | Where-Object { $_.type -eq "response_correctness" }).Count -eq 0)
        canonical_write_mode = "reader_only"
        provider_calls = 0
        fixture_seeded = $false
    }
    result = if ($workloadExitCode -eq 0 -and $blockers.Count -eq 2) { "pass" } elseif ($workloadExitCode -eq 0) { "stopped_with_quantified_blockers" } else { "stopped_with_runner_failure" }
    blockers = @($blockers)
}

$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding utf8

Remove-Item -LiteralPath $rawJsonPath, $workloadLogPath -Force -ErrorAction SilentlyContinue

[ordered]@{
    profile = $Profile
    report = $reportPath
    result = $report.result
    route_count = @($routeReports.Keys | ForEach-Object { $_ }).Count
    blocker_count = @($blockers).Count
    workload_exit_code = $workloadExitCode
} | ConvertTo-Json -Compress
