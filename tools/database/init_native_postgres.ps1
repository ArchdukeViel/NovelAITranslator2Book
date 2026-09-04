# init_native_postgres.ps1
# Automates starting dokushodo-db, running Alembic migrations, and seeding live data into native PostgreSQL 17.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

Write-Host "==> Checking Docker engine availability..."
try {
    $null = docker info --format '{{.ServerVersion}}' 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker engine is not reachable."
    }
}
catch {
    Write-Error "Docker engine is not running. Please open Docker Desktop on Windows, then rerun this script."
    exit 1
}

Write-Host "==> Starting dokushodo-db container (postgres:17.4-alpine)..."
docker compose -f deploy/compose.yml up -d db
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start dokushodo-db container."
    exit 1
}

Write-Host "==> Waiting for dokushodo-db to become healthy..."
$retries = 30
$healthy = $false
while ($retries -gt 0) {
    $status = docker inspect --format '{{.State.Health.Status}}' dokushodo-db 2>$null
    if ($status -eq "healthy") {
        $healthy = $true
        break
    }
    Start-Sleep -Seconds 2
    $retries--
}

if (-not $healthy) {
    Write-Error "dokushodo-db did not reach healthy state in time."
    docker logs --tail 20 dokushodo-db
    exit 1
}

Write-Host "==> dokushodo-db is healthy!"

Write-Host "==> Running Alembic migrations to head (a1b2c3d4e5f6)..."
if (-not $env:DATABASE_URL) {
    if (Test-Path "$RepoRoot\.env") {
        $envMatch = Get-Content "$RepoRoot\.env" | Where-Object { $_ -match "^DATABASE_URL=" } | Select-Object -First 1
        if ($envMatch) {
            $env:DATABASE_URL = $envMatch.Split("=", 2)[1].Trim()
        }
    }
}
if (-not $env:DATABASE_URL) {
    Write-Error "DATABASE_URL is not configured. Please define DATABASE_URL in .env before running this script."
    exit 1
}
$env:MIGRATION_DATABASE_URL = $env:DATABASE_URL

Push-Location "$RepoRoot\backend"
try {
    & "$RepoRoot\.venv\Scripts\python.exe" -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Alembic migration failed."
    }
}
finally {
    Pop-Location
}

Write-Host "==> Copying and ingesting seed data into dokushodo-db..."
docker cp "$RepoRoot\deploy\postgres\seeds\02-data-seed.sql" dokushodo-db:/tmp/02-data-seed.sql
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to copy seed file into dokushodo-db."
    exit 1
}

docker exec dokushodo-db psql -U dokushodo -d dokushodo -v ON_ERROR_STOP=1 -f /tmp/02-data-seed.sql
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to execute seed data in dokushodo-db."
    exit 1
}

Write-Host "==> Verifying table row counts in native PostgreSQL 17..."
docker exec dokushodo-db psql -U dokushodo -d dokushodo -c @"
SELECT 'novels' AS table_name, count(*) AS count FROM novels
UNION ALL
SELECT 'chapters', count(*) FROM chapters
UNION ALL
SELECT 'novel_glossary_entries', count(*) FROM novel_glossary_entries
ORDER BY table_name;
"@

Write-Host "`n==> Success! Native PostgreSQL 17 is initialized and fully populated."
Write-Host "    Web Browser GUI (CloudBeaver):"
Write-Host "    URL: http://127.0.0.1:8978"
Write-Host "    Host: db | Port: 5432 | User: dokushodo | Database: dokushodo (password set in .env)"
Write-Host "`n    Desktop GUI (TablePlus/DBeaver) connection:"
Write-Host "    Host: 127.0.0.1 | Port: 5432 | User: dokushodo | Database: dokushodo (password set in .env)"
