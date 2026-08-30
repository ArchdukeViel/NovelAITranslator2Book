# Requirements: Workspace and Quality Hardening

## Goal
Comprehensive workspace, developer environment, VS Code integration, testing harness, and quality hardening covering all 20 audit recommendations across backend, frontend, tools, deployment, and repository governance.

## Scope (All 20 Recommendations)

### Area 1: Workspace & Root Hygiene
1. **R1**: Purge stray root file `file`.
2. **R2**: Purge empty root directory `Caddyfile/`.
3. **R3**: Track `.vscode/tasks.json` and `.vscode/mcp.json` in git (update `.gitignore`).
4. **R4**: Un-exclude `.agents/**` in `.vscode/settings.json` so global search finds specs/rules.
5. **R5**: Keep `.opencode/` local/scratch gitignored while maintaining canonical scripts in `.opencode/scripts/`.

### Area 2: Tooling & CLI Wrappers
6. **R6**: Normalize path arguments in `tools/pytest.ps1` (`/` to `\`) for seamless Windows PowerShell runs.
7. **R7**: Normalize path arguments in `tools/pyright.ps1`.
8. **R8**: Normalize path arguments in `tools/ruff.ps1`.
9. **R9**: Verify Python venv launcher strict check (`.venv\Scripts\python.exe`) across all wrapper scripts.

### Area 3: VS Code & Developer Experience
10. **R10**: Add `"Backend: Test Watch"` background task in `.vscode/tasks.json`.
11. **R11**: Add `"Backend: Pytest Focused"` task with input prompt in `.vscode/tasks.json`.
12. **R12**: Add `"Frontend: Build"` production check task in `.vscode/tasks.json`.
13. **R13**: Maintain clean `.vscode/extensions.json` containing only active workspace extensions.

### Area 4: Testing, Database & CI Hardening
14. **R14**: Fix Vitest CLI command invocation (`npm --prefix frontend run test`) for Windows path compatibility.
15. **R15**: Validate syntax and type correctness of untracked Alembic migrations (`2026-08-22_*.py`).
16. **R16**: Enforce `tools/ruff.ps1 format` pre-commit check routine on modified files.
17. **R17**: Verify Frontend Next.js production build (`npm --prefix frontend run build`).
18. **R18**: Verify Frontend TypeScript typecheck (`npm --prefix frontend run typecheck`) and ESLint (`npm --prefix frontend run lint`).
19. **R19**: Reconcile active spec lifecycle with `docs/WORK.md` and `docs/HISTORY.md`.
20. **R20**: Sync and verify knowledge graph index (`graphify update . --no-cluster`).

## Acceptance Criteria
- All 20 items have explicit, runnable verification commands in `tasks.md`.
- Zero stray files/folders in repo root.
- All wrapper scripts accept forward and backward slash paths on Windows.
- All backend and frontend type checks, linters, and tests pass with exit code 0.
- Graphify index fully synchronized.
