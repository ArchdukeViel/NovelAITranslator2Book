[CmdletBinding(SupportsShouldProcess)]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$repoPrefix = $repoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
$excludedRoots = @(".git", ".venv", ".tmp", "frontend\node_modules", "graphify-out", ".tmp.driveupload") |
    ForEach-Object { [System.IO.Path]::GetFullPath((Join-Path $repoRoot $_)) }

function Assert-SafeProjectPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside the repository."
    }
    if ($excludedRoots | Where-Object {
        $resolved -eq $_ -or $resolved.StartsWith(
            $_.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    }) {
        throw "Refusing to clean an excluded repository path."
    }
    return $resolved
}

function Remove-ProjectItem {
    param([Parameter(Mandatory = $true)][string]$Path)

    $safePath = Assert-SafeProjectPath -Path $Path
    if ((Test-Path -LiteralPath $safePath) -and $PSCmdlet.ShouldProcess($safePath, "Remove runtime artifact")) {
        Remove-Item -LiteralPath $safePath -Recurse -Force
        return $true
    }
    return $false
}

Write-Host "=== Novel AI Cleanup ===" -ForegroundColor Cyan

$fixedTargets = @(
    "backend/tests/.tmp",
    ".pytest_cache",
    ".hypothesis"
)
foreach ($relativeTarget in $fixedTargets) {
    $target = Join-Path $repoRoot $relativeTarget
    if (Remove-ProjectItem -Path $target) {
        Write-Host "[OK] Removed $relativeTarget" -ForegroundColor Green
    } else {
        Write-Host "[SKIP] $relativeTarget not found or not approved" -ForegroundColor Yellow
    }
}

$cacheDirs = Get-ChildItem -LiteralPath $repoRoot -Directory -Recurse -Filter "__pycache__" -Force -ErrorAction SilentlyContinue |
    Where-Object {
        $candidate = $_.FullName
        -not ($excludedRoots | Where-Object {
            $candidate -eq $_ -or $candidate.StartsWith(
                $_.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        })
    }

$count = 0
foreach ($dir in $cacheDirs) {
    if (Remove-ProjectItem -Path $dir.FullName) {
        $count++
    }
}
Write-Host "[OK] Removed $count __pycache__ directories" -ForegroundColor Green
Write-Host "=== Done ===" -ForegroundColor Cyan
