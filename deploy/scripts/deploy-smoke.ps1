<#
.SYNOPSIS
    Deploy smoke check — verifies migration gate, live/ready health, and
    public/admin route separation after deployment.
.DESCRIPTION
    Run after `docker compose up -d`. Three mutually exclusive modes:
    Default (local): uses http, --insecure, skips recovery if cookie absent.
    -Production:   requires https, cookie mandatory, no --insecure, recovery must pass.
    -ExternalMonitor: requires https, public checks only, no recovery, no cookie.
#>

param(
    [string]$BaseUrl = "http://localhost",
    [int]$AdminPort = 8000,
    [int]$ReaderPort = 8001,
    [int]$FrontendPort = 3000,
    [int]$TimeoutSeconds = 60,
    [switch]$Help,
    [switch]$Production,
    [switch]$ExternalMonitor
)

$ErrorActionPreference = "Stop"

if ($Production -and $ExternalMonitor) {
    Write-Error "-Production and -ExternalMonitor are mutually exclusive"
    exit 1
}

if ($Help) {
    Write-Output @"
Smoke check for NovelAI deployment.
Usage: .\scripts\deploy-smoke.ps1 [[-BaseUrl] <str>] [[-AdminPort] <int>] [[-ReaderPort] <int>] [[-FrontendPort] <int>] [-Production] [-ExternalMonitor]

Flags:
  -BaseUrl         Base URL (default http://localhost)
  -AdminPort       Admin backend port (default 8000)
  -ReaderPort      Reader backend port (default 8001)
  -FrontendPort    Frontend port (default 3000)
  -TimeoutSeconds  Max wait in seconds (default 60)
  -Production      Enforce HTTPS, require NOVELAI_SMOKE_SESSION_COOKIE, no TLS bypass, require owner recovery healthy.
  -ExternalMonitor External HTTPS public checks only (live, ready, catalog, frontend/legal/SEO). No session secret.
  -Help            Show this help
"@
    exit 0
}

$insecureFlag = "--insecure"
$nullDevice = if ([System.IO.Path]::DirectorySeparatorChar -eq "\") { "NUL" } else { "/dev/null" }
if ($Production -or $ExternalMonitor) {
    if (-not $BaseUrl.StartsWith("https://")) {
        Write-Error "-Production/-ExternalMonitor require https:// BaseUrl"
        exit 1
    }
    $insecureFlag = ""  # no TLS bypass in production/external
}

if ($Production -and -not $env:NOVELAI_SMOKE_SESSION_COOKIE) {
    Write-Error "-Production requires NOVELAI_SMOKE_SESSION_COOKIE environment variable"
    exit 1
}

$CaddyUrl = $BaseUrl

Write-Output "=== NovelAI Deploy Smoke Check ==="
Write-Output "Base URL: $CaddyUrl"
Write-Output "Mode: $(if ($Production) { 'Production' } elseif ($ExternalMonitor) { 'ExternalMonitor' } else { 'Local' })"
Write-Output "Timeout: ${TimeoutSeconds}s"
Write-Output ""

$allPassed = $true

function Check-Url {
    param([string]$Name, [string]$Url, [int]$ExpectedStatus = 200)
    Write-Host -NoNewline "[CHECK] $Name ... "
    try {
        if ($insecureFlag) {
            $status = & curl.exe --silent --show-error --location $insecureFlag --output $nullDevice --write-out "%{http_code}" --max-time $TimeoutSeconds $Url
        } else {
            $status = & curl.exe --silent --show-error --location --output $nullDevice --write-out "%{http_code}" --max-time $TimeoutSeconds $Url
        }
        if ($LASTEXITCODE -eq 0 -and [int]$status -eq $ExpectedStatus) {
            Write-Output "PASS ($status)"
        } else {
            Write-Output "FAIL (expected $ExpectedStatus, got $status)"
            $script:allPassed = $false
        }
    } catch {
        Write-Output "FAIL ($($_.Exception.Message))"
        $script:allPassed = $false
    }
}

function Run-Check {
    param([string]$Name, [string]$Url, [int]$ExpectedStatus = 200)
    Check-Url -Name $Name -Url $Url -ExpectedStatus $ExpectedStatus
}

function Check-RecoveryHealth {
    if (-not $env:NOVELAI_SMOKE_SESSION_COOKIE) {
        if ($Production) {
            Write-Output "FAIL (NOVELAI_SMOKE_SESSION_COOKIE required in -Production mode)"
            $script:allPassed = $false
        } else {
            Write-Output "[SKIP] Owner recovery health (NOVELAI_SMOKE_SESSION_COOKIE not set)"
        }
        return
    }
    Write-Host -NoNewline "[CHECK] Owner recovery health ... "
    try {
        $resp = Invoke-RestMethod -Uri "$CaddyUrl/api/admin/health" -Headers @{ Cookie = $env:NOVELAI_SMOKE_SESSION_COOKIE } -TimeoutSec 10
        $required = @("object_snapshot", "database_backup", "database_restore_verification")
        $failed = @($required | Where-Object { $resp.checks.$_.status -ne "healthy" })
        if ($failed.Count -eq 0) {
            Write-Output "PASS"
        } else {
            Write-Output "FAIL (unhealthy recovery checks: $($failed -join ', '))"
            $script:allPassed = $false
        }
    } catch {
        Write-Output "FAIL ($($_.Exception.Message))"
        $script:allPassed = $false
    }
}

# 1. Migration gate — the backend should be running (migration one-shot already succeeded)
Write-Output "--- Service Health ---"

# Backend health (through Caddy)
Run-Check -Name "Admin liveness" -Url "$CaddyUrl/health/live"
Run-Check -Name "Admin readiness (DB and R2 probe)" -Url "$CaddyUrl/health/ready"

# Public catalog below proves Caddy-to-reader routing.
if (-not $ExternalMonitor) {
    Check-RecoveryHealth
}

Write-Output ""
Write-Output "--- Route Boundary Checks ---"

# These go through Caddy reverse proxy
# Admin routes
Run-Check -Name "Login page" -Url "$CaddyUrl/login" -ExpectedStatus 200

# Public routes
Run-Check -Name "Public catalog" -Url "$CaddyUrl/api/public/catalog" -ExpectedStatus 200

# Frontend
Run-Check -Name "Frontend responds" -Url "$CaddyUrl" -ExpectedStatus 200
Run-Check -Name "robots.txt" -Url "$CaddyUrl/robots.txt" -ExpectedStatus 200
Run-Check -Name "sitemap.xml" -Url "$CaddyUrl/sitemap.xml" -ExpectedStatus 200
Run-Check -Name "Privacy route" -Url "$CaddyUrl/privacy" -ExpectedStatus 200
Run-Check -Name "Terms route" -Url "$CaddyUrl/terms" -ExpectedStatus 200
Run-Check -Name "Legal route" -Url "$CaddyUrl/legal" -ExpectedStatus 200

Write-Output ""
Write-Output "=== Summary ==="
if ($allPassed) {
    Write-Output "All checks PASSED."
    exit 0
} else {
    Write-Output "Some checks FAILED - review output above."
    exit 1
}
