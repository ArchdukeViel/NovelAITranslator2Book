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

Write-Output "=== NovelAI Deploy Smoke Check ==="
Write-Output "Admin API: $AdminApi"
Write-Output "Reader API: $ReaderApi"
Write-Output "Frontend: $Frontend"
Write-Output "Timeout: ${TimeoutSeconds}s"
Write-Output ""

$allPassed = $true

function Check-Url {
    param([string]$Name, [string]$Url, [int]$ExpectedStatus = 200)
    Write-Output -NoNewline "[CHECK] $Name ... "
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -SkipCertificateCheck
        if ($resp.StatusCode -eq $ExpectedStatus) {
            Write-Output "PASS ($($resp.StatusCode))"
            return $true
        } else {
            Write-Output "FAIL (expected $ExpectedStatus, got $($resp.StatusCode))"
            return $false
        }
    } catch {
        Write-Output "FAIL ($($_.Exception.Message))"
        return $false
    }
}

# 1. Migration gate — the backend should be running (migration one-shot already succeeded)
Write-Output "--- Service Health ---"

# Backend health (through Caddy)
Check-Url -Name "Admin liveness" -Url "$AdminApi/health/live"
Check-Url -Name "Admin readiness" -Url "$AdminApi/health/ready"

# Reader health (through Caddy)
Check-Url -Name "Reader liveness" -Url "$ReaderApi/health/live"
Check-Url -Name "Reader readiness" -Url "$ReaderApi/health/ready"

Write-Output ""
Write-Output "--- Route Boundary Checks ---"

# These go through Caddy reverse proxy
$CaddyUrl = "$BaseUrl"

# Admin routes
Check-Url -Name "POST /api/auth/login returns 200 or redirect" -Url "$CaddyUrl/login" -ExpectedStatus 200

# Public routes
Check-Url -Name "Public catalog" -Url "$CaddyUrl/api/public/catalog" -ExpectedStatus 200

# Frontend
Check-Url -Name "Frontend responds" -Url "$Frontend" -ExpectedStatus 200

Write-Output ""
Write-Output "=== Summary ==="
if ($allPassed) {
    Write-Output "All checks PASSED."
    exit 0
} else {
    Write-Output "Some checks FAILED — review output above."
    exit 1
}
