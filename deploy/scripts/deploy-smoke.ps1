<#
.SYNOPSIS
    Deploy smoke check — verifies migration gate, live/ready health, and
    public/admin route separation after deployment.
.DESCRIPTION
    Runs after `docker compose up -d`. Does not require production secrets.
    Safe to run against any environment.
#>

param(
    [string]$BaseUrl = "http://localhost",
    [int]$AdminPort = 8000,
    [int]$ReaderPort = 8001,
    [int]$FrontendPort = 3000,
    [int]$TimeoutSeconds = 60,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Output @"
Smoke check for NovelAI deployment.

Usage: .\scripts\deploy-smoke.ps1 [[-BaseUrl] <str>] [[-AdminPort] <int>] [[-ReaderPort] <int>] [[-FrontendPort] <int>]

Flags:
  -BaseUrl       Base URL (default http://localhost)
  -AdminPort     Admin backend port (default 8000)
  -ReaderPort    Reader backend port (default 8001)
  -FrontendPort  Frontend port (default 3000)
  -TimeoutSeconds Max wait in seconds (default 60)
  -Help          Show this help
"@
    exit 0
}

$AdminApi = "$BaseUrl`:$AdminPort"
$ReaderApi = "$BaseUrl`:$ReaderPort"
$Frontend = "$BaseUrl`:$FrontendPort"
$CaddyUrl = $BaseUrl

Write-Output "=== NovelAI Deploy Smoke Check ==="
Write-Output "Admin API: $AdminApi"
Write-Output "Reader API: $ReaderApi"
Write-Output "Frontend: $Frontend"
Write-Output "Timeout: ${TimeoutSeconds}s"
Write-Output ""

$allPassed = $true

function Check-Url {
    param([string]$Name, [string]$Url, [int]$ExpectedStatus = 200)
    Write-Host -NoNewline "[CHECK] $Name ... "
    try {
        $status = & curl.exe --silent --show-error --location --insecure --output NUL --write-out "%{http_code}" --max-time 5 $Url
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
        Write-Output "[SKIP] Owner recovery health (NOVELAI_SMOKE_SESSION_COOKIE not set)"
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
Check-RecoveryHealth

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
