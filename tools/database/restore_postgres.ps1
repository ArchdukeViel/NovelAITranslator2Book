# restore_postgres.ps1
# Restores a verified pg_dump backup into the dokushodo-db container.

param(
    [string]$BackupFile = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($BackupFile)) {
    $BackupDir = Join-Path $RepoRoot "deploy\postgres\backups"
    $Latest = Get-ChildItem -Path $BackupDir -Filter "dokushodo_backup_*.dump" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $Latest) {
        Write-Error "No backup file specified and no backup files found in $BackupDir"
        exit 1
    }
    $BackupFile = $Latest.FullName
}

if (-not (Test-Path -LiteralPath $BackupFile)) {
    Write-Error "Backup file not found: $BackupFile"
    exit 1
}

$containerRunning = docker ps --filter "name=dokushodo-db" --filter "status=running" -q
if (-not $containerRunning) {
    Write-Error "Container dokushodo-db is not running. Start it with docker compose up -d db first."
    exit 1
}

Write-Host "==> Restoring PostgreSQL 17 from backup: $BackupFile..."
docker cp "$BackupFile" dokushodo-db:/tmp/restore_temp.dump
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to copy backup file into container."
    exit 1
}

# Run pg_restore with clean and if-exists flags
docker exec dokushodo-db pg_restore --clean --if-exists -U dokushodo -d dokushodo -v /tmp/restore_temp.dump 2>$null
docker exec dokushodo-db rm -f /tmp/restore_temp.dump

Write-Host "==> Verifying table row counts in native PostgreSQL 17..."
docker exec dokushodo-db psql -U dokushodo -d dokushodo -c @"
SELECT 'novels' AS table_name, count(*) AS count FROM novels
UNION ALL
SELECT 'chapters', count(*) FROM chapters
UNION ALL
SELECT 'novel_glossary_entries', count(*) FROM novel_glossary_entries
ORDER BY table_name;
"@

Write-Host "`n==> Success! Database restored from: $BackupFile"
