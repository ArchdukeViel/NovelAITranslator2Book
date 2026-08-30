# Tasks: Workspace and Quality Hardening

Status: Complete
Evidence: `docs/EVIDENCE.md#2026-08-24-workspace-and-quality-hardening-completion`

## Phase 1: Workspace & Root Hygiene (R1–R5)
- [ ] **1. Clean root stray file**
  - Delete empty `file` from repo root.
  - *Verification*: `powershell -NoProfile -Command "if (Test-Path 'file') { exit 1 } else { exit 0 }"`

- [ ] **2. Clean root stray directory**
  - Delete empty `Caddyfile/` folder from repo root.
  - *Verification*: `powershell -NoProfile -Command "if (Test-Path 'Caddyfile') { exit 1 } else { exit 0 }"`

- [ ] **3. Verify .gitignore tracking for .vscode configs**
  - Ensure `.vscode/tasks.json` and `.vscode/mcp.json` are not ignored.
  - *Verification*: `git check-ignore -v .vscode/tasks.json .vscode/mcp.json`

- [ ] **4. Verify .vscode search exclusion rules**
  - Confirm `.agents/**` is un-excluded in `.vscode/settings.json`.
  - *Verification*: `powershell -NoProfile -Command "if ((Get-Content .vscode/settings.json -Raw) -match '\"\.agents/\*\*\"') { exit 1 } else { exit 0 }"`

- [ ] **5. Validate .opencode gitignore boundary**
  - Confirm `.opencode/` remains untracked while scripts stay in `.opencode/scripts/`.
  - *Verification*: `git check-ignore -v .opencode/package.json`

## Phase 2: Tooling & CLI Wrappers (R6–R9)
- [ ] **6. Normalize path arguments in tools/pytest.ps1**
  - Update `tools/pytest.ps1` to normalize slash direction in passed file paths.
  - *Verification*: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_health_api.py`

- [ ] **7. Normalize path arguments in tools/pyright.ps1**
  - Update `tools/pyright.ps1` to normalize slash direction in passed file paths.
  - *Verification*: `powershell -ExecutionPolicy Bypass -File tools/pyright.ps1 backend/src/novelai/api/app.py`

- [ ] **8. Normalize path arguments in tools/ruff.ps1**
  - Update `tools/ruff.ps1` to normalize slash direction in passed file paths.
  - *Verification*: `powershell -ExecutionPolicy Bypass -File tools/ruff.ps1 check backend/src/novelai/api/app.py`

- [ ] **9. Verify Python virtualenv path check across all tools**
  - Verify all `tools/*.ps1` scripts fail with exit code 2 if `.venv` is missing.
  - *Verification*: `powershell -NoProfile -Command "Get-ChildItem tools/*.ps1 | ForEach-Object { if (-not ((Get-Content $_.FullName -Raw) -match 'venvPython')) { exit 1 } }; exit 0"`

## Phase 3: VS Code & Developer Experience (R10–R13)
- [ ] **10. Add Backend Test Watch task to .vscode/tasks.json**
  - Add `"Backend: Test Watch"` background task.
  - *Verification*: `powershell -NoProfile -Command "Get-Content .vscode/tasks.json | Select-String 'Backend: Test Watch'"`

- [ ] **11. Add Frontend Build task to .vscode/tasks.json**
  - Add `"Frontend: Build"` task to `.vscode/tasks.json`.
  - *Verification*: `powershell -NoProfile -Command "Get-Content .vscode/tasks.json | Select-String 'Frontend: Build'"`

- [ ] **12. Validate .vscode/extensions.json recommendations**
  - Verify all recommendations match current active stack without redundant entries.
  - *Verification*: `powershell -NoProfile -Command "Get-Content .vscode/extensions.json | Select-String 'charliermarsh.ruff'"`

- [ ] **13. Validate .vscode/settings.json formatter bindings**
  - Confirm Ruff is default Python formatter and Prettier is default TS/JSON formatter.
  - *Verification*: `powershell -NoProfile -Command "Get-Content .vscode/settings.json | Select-String 'charliermarsh.ruff'"`

## Phase 4: Testing, Database & CI Hardening (R14–R20)
- [ ] **14. Validate Frontend Vitest CLI test suite execution**
  - Run frontend test suite via `npm --prefix frontend run test`.
  - *Verification*: `npm --prefix frontend run test`

- [ ] **15. Validate Alembic migration heads and syntax**
  - Run Pyright and Ruff on `backend/alembic/versions/2026-08-22_*.py`.
  - *Verification*: `tools/pyright.ps1; tools/ruff.ps1 check backend/alembic/versions/`

- [ ] **16. Run Ruff formatter check on working tree**
  - Format backend Python files and check diff.
  - *Verification*: `tools/ruff.ps1 check .`

- [ ] **17. Verify Frontend production build**
  - Run Next.js build.
  - *Verification*: `npm --prefix frontend run build`

- [ ] **18. Verify Frontend typecheck and linting**
  - Run TypeScript typecheck and ESLint.
  - *Verification*: `npm --prefix frontend run typecheck; npm --prefix frontend run lint`

- [ ] **19. Reconcile documentation and work registers**
  - Verify `docs/STATUS.md` and `docs/EVIDENCE.md` state.
  - *Verification*: `powershell -NoProfile -Command "if (Test-Path 'docs/STATUS.md') { exit 0 } else { exit 1 }"`

- [ ] **20. Synchronize knowledge graph index**
  - Run Graphify update to index all changes.
  - *Verification*: `graphify update . --no-cluster`
