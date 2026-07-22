# Install recommended VS Code extensions for this project
# Run from repository root: .\deploy\install-extensions.ps1

$extensions = @(
    "charliermarsh.ruff"
    "esbenp.prettier-vscode"
    "bradlc.vscode-tailwindcss"
    "ms-python.python"
    "ms-python.vscode-pylance"
    "usernamehw.errorlens"
    "eamodio.gitlens"
    "Gruntfuggly.todo-tree"
)

Write-Host "Installing recommended VS Code extensions..." -ForegroundColor Cyan

$installed = 0
$failed = 0

foreach ($ext in $extensions) {
    try {
        $result = & code --install-extension $ext --force 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] $ext" -ForegroundColor Green
            $installed++
        } else {
            Write-Host "  [FAIL] $ext — $result" -ForegroundColor Red
            $failed++
        }
    } catch {
        Write-Host "  [SKIP] $ext — $($_.Exception.Message)" -ForegroundColor Yellow
        $failed++
    }
}

Write-Host ""
Write-Host "Done. $installed installed, $failed failed." -ForegroundColor Cyan
Write-Host "If 'code' is not on PATH, open VS Code and search for extensions manually." -ForegroundColor Yellow
