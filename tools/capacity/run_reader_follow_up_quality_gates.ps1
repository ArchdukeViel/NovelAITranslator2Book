<#
.SYNOPSIS
    Runs the affected quality gates with checked native exit codes and evidence.

.DESCRIPTION
    A green artifact validator does not erase an operational blocker. The
    report records command exit codes, result counts, workflow-reference
    blockers, and the final evidence disposition separately.
#>
[CmdletBinding()]
param(
    [string]$SpecPath = ".agents/specs/reader-capacity-and-recovery-follow-up",
    [string]$ArtifactPath = "artifacts/operations/reader-capacity-follow-up"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$records = @()
$blockers = @()
$qualityFailure = $false
$validationPath = Join-Path $ArtifactPath "validation.md"
$tempRoot = Join-Path $ArtifactPath ".quality-gates"
if (-not (Test-Path -LiteralPath $tempRoot -PathType Container)) { New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null }

function Add-Record([string]$Label, [string]$Command, [int]$ExitCode, [string]$ResultCount, [double]$DurationSeconds, [string]$Result) {
    $script:records += [ordered]@{
        label = $Label
        command = $Command
        exit_code = $ExitCode
        result_count = $ResultCount
        duration_seconds = [math]::Round($DurationSeconds, 3)
        result = $Result
    }
}

function Invoke-Checked([string]$Label, [string]$Command, [scriptblock]$Action) {
    $started = [DateTime]::UtcNow
    $logPath = Join-Path $tempRoot (([Guid]::NewGuid().ToString("N")) + ".log")
    $exitCode = 0
    $resultCount = "not parsed"
    $result = "passed"
    try {
        & $Action *> $logPath
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
        $log = if (Test-Path -LiteralPath $logPath) { [string](Get-Content -LiteralPath $logPath -Raw) } else { "" }
        $match = [regex]::Match($log, "(?m)(\d+)\s+(passed|failed|errors|warnings|skipped|informations?)")
        if ($match.Success) { $resultCount = $match.Value.Trim() }
        if ($exitCode -ne 0) { $result = "failed" }
    }
    catch {
        $exitCode = 1
        $result = "failed"
        $resultCount = "exception: $($_.Exception.Message)"
    }
    finally {
        $duration = ([DateTime]::UtcNow - $started).TotalSeconds
        Add-Record $Label $Command $exitCode $resultCount $duration $result
        Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
    }
    if ($exitCode -ne 0) {
        $script:qualityFailure = $true
        Add-OperationalBlocker "blk-quality-$Label" $Label "quality gate failed with exit code $exitCode" "rerun the failed command after the local defect is repaired" "quality_gate_failed" "do not close the handoff while a quality gate command fails"
    }
}

function Add-OperationalBlocker([string]$Id, [string]$Target, [string]$Reason, [string]$NextAction, [string]$UnavailableReason = "workflow_test_path_missing", [string]$RetryCondition = "do not rely on hosted recovery evidence until the path exists at the candidate revision") {
    $script:blockers += [ordered]@{
        blocker_id = $Id
        observed_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        affected_target = $Target
        measured_value = $null
        budget_ms = $null
        source_or_reason = $Reason
        unavailable_reason = $UnavailableReason
        owner_role = "project_owner"
        next_action = $NextAction
        retry_or_admission_condition = $RetryCondition
        safety_disposition = "keep_capacity_unadmitted"
    }
}

function Test-WorkflowReferences() {
    $workflowFiles = @(Get-ChildItem .github/workflows -Filter *.yml -File -ErrorAction SilentlyContinue) + @(Get-ChildItem .github/workflows -Filter *.yaml -File -ErrorAction SilentlyContinue)
    foreach ($file in $workflowFiles) {
        $content = Get-Content -LiteralPath $file.FullName -Raw
        $matches = [regex]::Matches($content, "backend/tests/[A-Za-z0-9_./-]+\.py")
        foreach ($match in $matches) {
            $relativePath = $match.Value
            if (-not (Test-Path -LiteralPath $relativePath -PathType Leaf)) {
                Add-OperationalBlocker "blk-workflow-path-$([IO.Path]::GetFileNameWithoutExtension($relativePath))" $relativePath "workflow references a missing test path" "repair the workflow path or record an owner-approved replacement"
            }
        }
    }
}

function Invoke-GraphifyChecked() {
    $started = [DateTime]::UtcNow
    $exitCode = 0
    $result = "passed"
    try {
        & graphify update . --no-cluster
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
        if ($exitCode -ne 0) { $result = "failed" }
    }
    catch {
        $exitCode = 1
        $result = "failed"
    }
    $duration = ([DateTime]::UtcNow - $started).TotalSeconds
    Add-Record "graphify" "graphify update . --no-cluster" $exitCode "not parsed" $duration $result
    if ($exitCode -ne 0) {
        $script:qualityFailure = $true
        Add-OperationalBlocker "blk-quality-graphify" "graphify" "quality gate failed with exit code $exitCode" "rerun Graphify after the local defect is repaired" "quality_gate_failed" "do not close the documentation handoff while Graphify fails"
    }
}

try {
    Invoke-Checked "spec-validator" "python C:\\Users\\AKMALSAFARIPELLU\\.agents\\skills\\create-spec\\scripts\\validate_spec.py $SpecPath" {
        & python C:\Users\AKMALSAFARIPELLU\.agents\skills\create-spec\scripts\validate_spec.py $SpecPath
    }
    Invoke-Checked "pyright" "tools/pyright.ps1" {
        & powershell -NoProfile -ExecutionPolicy Bypass -File tools/pyright.ps1
    }
    Invoke-Checked "ruff" "tools/ruff.ps1 check backend/tests/test_reader_profile_contract.py backend/tests/test_reader_latency_attribution.py" {
        & powershell -NoProfile -ExecutionPolicy Bypass -File tools/ruff.ps1 check backend/tests/test_reader_profile_contract.py backend/tests/test_reader_latency_attribution.py
    }
    Invoke-Checked "profile-contract-tests" "tools/pytest.ps1 backend/tests/test_reader_profile_contract.py backend/tests/test_reader_latency_attribution.py backend/tests/test_capacity_harness.py -q" {
        & powershell -NoProfile -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_reader_profile_contract.py backend/tests/test_reader_latency_attribution.py backend/tests/test_capacity_harness.py -q
    }
    Invoke-Checked "recovery-control-tests" "tools/pytest.ps1 backend/tests/test_backup_service.py backend/tests/test_database_backup_crypto.py backend/tests/test_health_service.py backend/tests/test_operator_alert_service.py backend/tests/test_scheduler_service.py -q" {
        & powershell -NoProfile -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_backup_service.py backend/tests/test_database_backup_crypto.py backend/tests/test_health_service.py backend/tests/test_operator_alert_service.py backend/tests/test_scheduler_service.py -q
    }
    Invoke-Checked "restore-focused-tests" "tools/pytest.ps1 backend/tests/test_database_backup_crypto.py backend/tests/test_r2_backup.py backend/tests/test_backup_service.py -q" {
        & powershell -NoProfile -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_database_backup_crypto.py backend/tests/test_r2_backup.py backend/tests/test_backup_service.py -q
    }
    $routerOutput = @(rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py" 2>$null)
    if ($LASTEXITCODE -eq 0 -and $routerOutput.Count -gt 0) { throw "Router import boundary has violations" }
    Add-Record "router-import-guard" "rg router import boundary" 0 "0 matches" 0 "passed"
    Test-WorkflowReferences
    $workflowBlockerCount = @($blockers | Where-Object { $_.blocker_id -like "blk-workflow-path-*" }).Count
    $workflowAuditResult = if ($workflowBlockerCount -eq 0) { "passed" } else { "blocked" }
    Add-Record "workflow-reference-audit" "scan .github/workflows for missing backend test paths" 0 "$workflowBlockerCount blocker(s)" 0 $workflowAuditResult

    Invoke-Checked "markdown-and-path-check" "git diff --check plus required spec/docs/evidence paths" {
        $requiredPaths = @(
            "$SpecPath/requirements.md",
            "$SpecPath/design.md",
            "$SpecPath/tasks.md",
            "$ArtifactPath/baseline.json",
            "$ArtifactPath/route-profile.json",
            "$ArtifactPath/latency-attribution.json",
            "$ArtifactPath/hosted-telemetry.json",
            "$ArtifactPath/b7-mcp-snapshot.json",
            "$ArtifactPath/backup-controls.json",
            "$ArtifactPath/remediation-decision.md",
            "$ArtifactPath/restore-verification.md",
            "$ArtifactPath/recovery-owner-and-rotation.md",
            "$ArtifactPath/handoff.md"
        )
        foreach ($requiredPath in $requiredPaths) {
            if (-not (Test-Path -LiteralPath $requiredPath)) { throw "required documentation or evidence path is missing: $requiredPath" }
        }
        # Git may emit a harmless core.autocrlf conversion notice for files
        # edited on Windows. Preserve the native exit code while keeping that
        # stderr notice from becoming a PowerShell terminating error under
        # ErrorActionPreference=Stop.
        $gitErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $gitDiffOutput = @(& git diff --check 2>&1)
        $gitDiffExitCode = $LASTEXITCODE
        $ErrorActionPreference = $gitErrorAction
        if ($gitDiffExitCode -ne 0) { throw "git diff --check reported whitespace errors" }
    }

    $validator = "tools/capacity/validate_reader_follow_up.ps1"
    Invoke-Checked "evidence-validator-selftest" "powershell -File $validator -SelfTest" {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $validator -SelfTest
    }
    $jsonChecks = @(
        @("baseline", "$ArtifactPath/baseline.json"),
        @("route-profile", "$ArtifactPath/route-profile.json"),
        @("latency-attribution", "$ArtifactPath/latency-attribution.json"),
        @("hosted-telemetry", "$ArtifactPath/hosted-telemetry.json"),
        @("backup-controls", "$ArtifactPath/backup-controls.json")
    )
    $stage = Get-ChildItem (Join-Path $ArtifactPath "reader-stage-1000") -Filter "reader-stage-1000-*.json" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $stage) { throw "No stage-1000 artifact exists" }
    $jsonChecks += ,@("stage-1000", $stage.FullName)
    foreach ($check in $jsonChecks) {
        $label = "artifact-$($check[0])"
        $display = "powershell -File $validator -Kind $($check[0]) -Path $($check[1])"
        $kind = [string]$check[0]
        $path = [string]$check[1]
        Invoke-Checked $label $display {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $validator -Kind $kind -Path $path
        }
    }
    $b7McpSnapshotPath = Join-Path $ArtifactPath "b7-mcp-snapshot.json"
    if (Test-Path -LiteralPath $b7McpSnapshotPath -PathType Leaf) {
        Invoke-Checked "artifact-b7-mcp-snapshot" ".venv\\Scripts\\python.exe tools/capacity/validate_b7_mcp_snapshot.py $b7McpSnapshotPath" {
            & .venv\\Scripts\\python.exe tools/capacity/validate_b7_mcp_snapshot.py $b7McpSnapshotPath
        }
    }
    else {
        Add-OperationalBlocker "blk-b7-mcp-snapshot-missing" "b7-mcp-snapshot.json" "B7 MCP snapshot is missing" "capture the sanitized read-only MCP snapshot before closing the B7 evidence bundle" "runtime_state_unavailable" "do not treat the existing provider posture artifacts as the current B7 MCP snapshot"
        Add-Record "artifact-b7-mcp-snapshot" ".venv\\Scripts\\python.exe tools/capacity/validate_b7_mcp_snapshot.py $b7McpSnapshotPath" 1 "missing artifact" 0 "blocked"
    }
    foreach ($check in @(
        @("remediation-decision", "$ArtifactPath/remediation-decision.md"),
        @("restore-verification", "$ArtifactPath/restore-verification.md"),
        @("recovery-owner", "$ArtifactPath/recovery-owner-and-rotation.md")
    )) {
        $kind = [string]$check[0]
        $path = [string]$check[1]
        Invoke-Checked "artifact-$kind" "powershell -File $validator -Kind $kind -Path $path" {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $validator -Kind $kind -Path $path
        }
    }

    Invoke-GraphifyChecked
}
catch {
    $script:qualityFailure = $true
    $blockers += [ordered]@{
        blocker_id = "blk-quality-gate-failure"
        observed_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        affected_target = "quality_gates"
        measured_value = $null
        budget_ms = $null
        source_or_reason = "quality gate orchestration exception"
        unavailable_reason = "quality_gate_failed"
        owner_role = "project_owner"
        next_action = "repair the failing command and rerun the quality gates"
        retry_or_admission_condition = "do not close the handoff while a quality gate command fails"
        safety_disposition = "keep_capacity_unadmitted"
    }
}
finally {
    $status = if (@($blockers).Count -eq 0) { "passed" } else { "complete_with_blockers" }
    $lines = @(
        "# Validation and Quality Gates Summary",
        "",
        "Spec ID: reader-capacity-and-recovery-follow-up  ",
        "Date: $([DateTime]::UtcNow.ToString('yyyy-MM-dd'))  ",
        "Task: T-011",
        "",
        "## Executed Commands and Outcomes",
        "",
        "| Label | Exit code | Result count | Duration (s) | Result |",
        "|---|---:|---|---:|---|"
    )
    foreach ($record in $records) {
        $lines += "| $($record.label) | $($record.exit_code) | $($record.result_count) | $($record.duration_seconds) | $($record.result) |"
    }
    $lines += @("", "## Operational Blockers", "")
    if (@($blockers).Count -eq 0) {
        $lines += "- None recorded by the quality-gate orchestrator."
    }
    else {
        foreach ($blocker in $blockers) {
            $lines += "- **$($blocker.blocker_id)**: $($blocker.source_or_reason); next action: $($blocker.next_action); safety: $($blocker.safety_disposition)."
        }
    }
    $lines += @("", "## Quality Gates Status", "", "Status: **$status**", "", "A green local check does not erase a reader SLO, telemetry, workflow, or recovery blocker.")
    $lines -join [Environment]::NewLine | Set-Content -LiteralPath $validationPath -Encoding utf8
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

$validatorPath = "tools/capacity/validate_reader_follow_up.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Kind validation -Path $validationPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Kind handoff -Path "$ArtifactPath/handoff.md"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (@($blockers).Count -gt 0) {
    Write-Host "Quality gates completed with $(@($blockers).Count) blocker(s); see $validationPath" -ForegroundColor Yellow
    if ($qualityFailure) { exit 1 }
    exit 0
}
Write-Host "All quality gates passed; see $validationPath" -ForegroundColor Green
exit 0
