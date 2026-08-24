# Tasks: Workspace and Quality Hardening

Spec ID: workspace-and-quality-hardening
Version: 1.0.0
Status: Approved
Updated: 2026-08-24

## Phase 1: Workspace & Root Hygiene (R1–R5)
- [x] **T-001 Clean root stray file (R1)**
  - Delete empty `file` from repo root.
  - Verification: `powershell -NoProfile -Command "if (Test-Path 'file') { exit 1 } else { exit 0 }"`
  - Maps to: REQ-001, AC-001
  - Depends on: none
  - State: complete
  - Authorization: Project-owner approval for repository-root cleanup
  - Scope: The empty `file` entry at the repository root
  - Expected: The named stray file is absent and no canonical file is removed
  - Attempts: 1
  - Last result: `powershell -NoProfile -Command "if (Test-Path 'file') { exit 1 } else { exit 0 }"` exited 0; the target was already absent, so no deletion was performed.
  - Evidence: Read-only root-target review and `git ls-files -- file` confirmed the named path is absent and untracked. No canonical file was changed.

- [x] **T-002 Clean root stray directory (R2)**
  - Delete empty `Caddyfile/` folder from repo root.
  - Verification: `powershell -NoProfile -Command "if (Test-Path 'Caddyfile') { exit 1 } else { exit 0 }"`
  - Maps to: REQ-001, AC-001
  - Depends on: T-001
  - State: complete
  - Authorization: Project-owner approval for repository-root cleanup
  - Scope: The empty `Caddyfile/` entry at the repository root
  - Expected: The named stray directory is absent and no canonical deployment file is removed
  - Attempts: 1
  - Last result: The exact empty `C:\Akmal\Novel AI\Caddyfile` directory was removed after path, workspace-boundary, non-reparse, and emptiness checks; the post-deletion existence check passed.
  - Evidence: Project-owner authorization was received. A non-recursive bounded deletion removed only the explicit directory target, and the target was verified absent afterward. No canonical deployment file or workspace-root content was changed.

- [x] **T-003 Verify .gitignore tracking for .vscode configs (R3)**
  - Ensure `.vscode/tasks.json` and `.vscode/mcp.json` are not ignored.
  - Verification: `git ls-files --error-unmatch -- .vscode/tasks.json .vscode/mcp.json`
  - Maps to: REQ-001, AC-001
  - Depends on: T-002
  - State: complete
  - Authorization: Project-owner approval for workspace configuration tracking
  - Scope: Git ignore and tracking state for the two named VS Code configuration files
  - Expected: Both files are tracked and neither is hidden by an ignore rule
  - Attempts: 1
  - Last result: `git ls-files --error-unmatch -- .vscode/tasks.json .vscode/mcp.json` exited 0; both required files are tracked and `git check-ignore` returned no matches.
  - Evidence: All four repository-approved `.vscode` files parse as JSON. A credential and machine-path scan found no matches, and `.gitignore` explicitly permits the approved files. No `.vscode` content was changed.

- [x] **T-004 Verify .vscode search exclusion rules (R4)**
  - Confirm `.agents/**` is un-excluded in `.vscode/settings.json`.
  - Verification: `powershell -NoProfile -Command "if ((Get-Content .vscode/settings.json -Raw) -match '\.agents/\*\*\s*:\s*true') { exit 1 } else { exit 0 }"`
  - Maps to: REQ-001, AC-001
  - Depends on: T-003
  - State: complete
  - Authorization: Project-owner approval for VS Code search configuration
  - Scope: `.vscode/settings.json` search exclusions for `.agents/**`
  - Expected: The active specification and guidance files remain discoverable through workspace search
  - Attempts: 2
  - Last result: The original broad check returned 1 because `.agents/**` is present in `python.analysis.exclude`; the corrected search-specific check exited 0 because `.agents/**` is absent from `search.exclude` and `files.exclude`.
  - Evidence: `.vscode/settings.json` parsed successfully. The `.agents/**` Python-analysis exclusion remains unchanged, while global search exclusions contain no `.agents/**` entry. No VS Code configuration file was changed.

- [x] **T-005 Validate .opencode gitignore boundary (R5)**
  - Confirm `.opencode/` remains untracked while scripts stay in `.opencode/scripts/`.
  - Verification: `git check-ignore -v .opencode/package.json`
  - Maps to: REQ-001, AC-001
  - Depends on: T-004
  - State: complete
  - Authorization: Project-owner approval for local scratch-boundary verification
  - Scope: The `.opencode/` ignore boundary and canonical `.opencode/scripts/` location
  - Expected: Local scratch files remain ignored while canonical scripts are reviewed separately
  - Attempts: 1
  - Last result: `git check-ignore -v .opencode/package.json` exited 0 and identified the `.opencode/` ignore rule; no `.opencode` entries are tracked and four files are present under `.opencode/scripts/`.
  - Evidence: The local `.opencode/` boundary is intact. `package.json` is ignored, the scripts directory is non-empty, and `git ls-files -- .opencode` returned no entries. No local scratch content was changed.

## Phase 2: Tooling & CLI Wrappers (R6–R9)
- [x] **T-006 Normalize path arguments in tools/pytest.ps1 (R6)**
  - Update `tools/pytest.ps1` to normalize slash direction in passed file paths.
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_health_api.py`
  - Maps to: REQ-002, AC-002
  - Depends on: T-005
  - State: complete
  - Authorization: Project-owner approval for the pytest wrapper implementation
  - Scope: Path argument handling and strict interpreter resolution in `tools/pytest.ps1`
  - Expected: The wrapper accepts Windows path forms and runs the focused test through `.venv\Scripts\python.exe`
  - Attempts: 1
  - Last result: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_health_api.py` exited 0 with 8 passed in 8.83s.
  - Evidence: `tools/pytest.ps1` now normalizes non-option path arguments from `/` to `\` before invoking the canonical `.venv\Scripts\python.exe`; parser and diff checks passed, and pytest options remain unchanged.

- [x] **T-007 Normalize path arguments in tools/pyright.ps1 (R7)**
  - Update `tools/pyright.ps1` to normalize slash direction in passed file paths.
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pyright.ps1 backend/src/novelai/api/app.py`
  - Maps to: REQ-002, AC-002
  - Depends on: T-006
  - State: complete
  - Authorization: Project-owner approval for the pyright wrapper implementation
  - Scope: Path argument handling and strict interpreter resolution in `tools/pyright.ps1`
  - Expected: The wrapper accepts Windows path forms and runs the focused type check through the canonical virtual environment
  - Attempts: 1
  - Last result: `powershell -ExecutionPolicy Bypass -File tools/pyright.ps1 backend/src/novelai/api/app.py` exited 0 with 0 errors, 0 warnings, and 0 informations.
  - Evidence: `tools/pyright.ps1` now normalizes non-option path arguments from `/` to `\` before invoking the canonical `.venv\Scripts\python.exe`; PowerShell parser and whitespace checks passed. Conformance review confirmed the change is limited to wrapper argument handling and introduces no secrets or architectural boundary changes.

- [x] **T-008 Normalize path arguments in tools/ruff.ps1 (R8)**
  - Update `tools/ruff.ps1` to normalize slash direction in passed file paths.
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/ruff.ps1 check backend/src/novelai/api/app.py`
  - Maps to: REQ-002, AC-002
  - Depends on: T-007
  - State: complete
  - Authorization: Project-owner approval for the Ruff wrapper implementation
  - Scope: Path argument handling and strict interpreter resolution in `tools/ruff.ps1`
  - Expected: The wrapper accepts Windows path forms and runs the focused lint check through the canonical virtual environment
  - Attempts: 1
  - Last result: `powershell -ExecutionPolicy Bypass -File tools/ruff.ps1 check backend/src/novelai/api/app.py` exited 0 with `All checks passed!`.
  - Evidence: `tools/ruff.ps1` now normalizes non-option path arguments from `/` to `\` before invoking the canonical `.venv\Scripts\python.exe`; PowerShell parser and whitespace checks passed. Conformance review confirmed the change is limited to wrapper argument handling and introduces no secrets or architectural boundary changes.

- [x] **T-009 Verify Python virtualenv path check across all tools (R9)**
  - Verify all `tools/*.ps1` scripts fail with exit code 2 if `.venv` is missing.
  - Verification: `rg -n "venvPython|venv\\Scripts\\python\.exe" tools --glob "*.ps1"`
  - Maps to: REQ-002, AC-002
  - Depends on: T-008
  - State: complete
  - Authorization: Project-owner approval for wrapper safety verification
  - Scope: Strict `.venv\Scripts\python.exe` checks and missing-interpreter behavior across `tools/*.ps1`
  - Expected: Every wrapper fails closed when the project interpreter is absent and does not fall through to the system Python
  - Attempts: 3
  - Last result: The inventory command exited 0; an isolated copy of all 4 `tools/**/*.ps1` scripts returned exit code 2 for `pytest.ps1`, `pyright.ps1`, `ruff.ps1`, and `capacity/run_reader_load.ps1` when `.venv\Scripts\python.exe` was absent. Focused normal-environment regression checks returned `pytest=0`, `pyright=0`, and `ruff=0`.
  - Evidence: The three canonical wrappers now emit their diagnostic without terminating before the explicit exit, so missing-interpreter behavior is consistently exit code 2. The capacity load harness uses the same fail-closed exit contract. All 4 PowerShell scripts parsed with 0 errors, and the real project virtualenv was never renamed, removed, or modified.

## Phase 3: VS Code & Developer Experience (R10–R13)
- [x] **T-010 Add Backend Test Watch task to .vscode/tasks.json (R10)**
  - Add `"Backend: Test Watch"` background task.
  - Verification: `powershell -NoProfile -Command "Get-Content .vscode/tasks.json | Select-String 'Backend: Test Watch'"`
  - Maps to: REQ-003, AC-003
  - Depends on: T-009
  - State: complete
  - Authorization: Project-owner approval for VS Code task configuration
  - Scope: The background backend test-watch task and its problem matcher
  - Expected: The task starts a useful backend watch workflow without blocking the VS Code task runner
  - Attempts: 2
  - Last result: `powershell -NoProfile -Command "Get-Content .vscode/tasks.json | Select-String 'Backend: Test Watch'"` exited 0; JSON parsing and the venv watcher `--version` check passed. The first absolute-path startup exposed a workspace-space quoting failure; the corrected relative-path task started `watchfiles v1.2.0` successfully and was intentionally interrupted after startup.
  - Evidence: `.vscode/tasks.json` contains one background `Backend: Test Watch` task with `activeOnStart`, a backend-test problem matcher, workspace-root cwd, Python-filtered source/test paths, and the canonical `tools/pytest.ps1` target. No credentials or machine-specific paths were added.

- [x] **T-011 Add Backend Pytest Focused task to .vscode/tasks.json (R11)**
  - Add `"Backend: Pytest Focused"` with an input prompt for a focused path.
  - Verification: `powershell -NoProfile -Command "Get-Content .vscode/tasks.json | Select-String 'Backend: Pytest Focused'"`
  - Maps to: REQ-003, AC-003
  - Depends on: T-010
  - State: complete
  - Authorization: Project-owner approval for VS Code task configuration
  - Scope: The focused backend test task, input prompt, and wrapper invocation
  - Expected: A contributor can choose one test path and run it through the canonical test wrapper
  - Attempts: 1
  - Last result: `powershell -NoProfile -Command "Get-Content .vscode/tasks.json | Select-String 'Backend: Pytest Focused'"` exited 0; the task/input JSON review passed and the default focused path ran with 8 passed in 15.48s.
  - Evidence: `.vscode/tasks.json` defines one focused backend task using `tools/pytest.ps1`, a workspace-relative `backendTestPath` prompt, and a safe default of `backend/tests/test_health_api.py`. JSON parsing, the wrapper run, and whitespace checks passed; no credentials or machine-specific paths were added.

- [x] **T-012 Add Frontend Build task to .vscode/tasks.json (R12)**
  - Add `"Frontend: Build"` task to `.vscode/tasks.json`.
  - Verification: `powershell -NoProfile -Command "Get-Content .vscode/tasks.json | Select-String 'Frontend: Build'"`
  - Maps to: REQ-003, AC-003
  - Depends on: T-011
  - State: complete
  - Authorization: Project-owner approval for VS Code task configuration
  - Scope: The frontend production-build task and its working-directory contract
  - Expected: The task invokes the documented frontend build command and reports failures to VS Code
  - Attempts: 1
  - Last result: `powershell -NoProfile -Command "Get-Content .vscode/tasks.json | Select-String 'Frontend: Build'"` exited 0; the task parsed and `npm --prefix frontend run build` exited 0 after compiling, TypeScript, static generation, and route optimization.
  - Evidence: `.vscode/tasks.json` defines `Frontend: Build` with `npm --prefix frontend run build`, build grouping, and workspace-root cwd. The production build completed successfully with 48 static pages generated; no credentials or machine-specific paths were added.

- [x] **T-013 Validate VS Code extensions and formatter bindings (R13)**
  - Verify active recommendations are non-redundant and formatter bindings use Ruff for Python and Prettier for TypeScript and JSON.
  - Verification: `rg -n "charliermarsh.ruff|editor.defaultFormatter|esbenp.prettier" .vscode/extensions.json .vscode/settings.json`
  - Maps to: REQ-003, AC-003
  - Depends on: T-012
  - State: complete
  - Authorization: Project-owner approval for VS Code workspace recommendations
  - Scope: `.vscode/extensions.json` recommendations and `.vscode/settings.json` formatter bindings
  - Expected: Only active workspace tooling is recommended and each supported language has its intended formatter
  - Attempts: 1
  - Last result: `rg -n "charliermarsh.ruff|editor.defaultFormatter|esbenp.prettier" .vscode/extensions.json .vscode/settings.json` exited 0; both JSON files parsed, all 10 extension recommendations were unique, and formatter bindings passed.
  - Evidence: `.vscode/extensions.json` retains 10 unique active recommendations. `.vscode/settings.json` binds Python to Ruff and TypeScript, JSON, and JSONC to Prettier with format-on-save; no credential or machine-specific configuration was introduced.

## Phase 4: Testing, Database & CI Hardening (R14–R20)
- [x] **T-014 Validate Frontend Vitest CLI test suite execution (R14)**
  - Run frontend test suite via `npm --prefix frontend run test`.
  - Verification: `npm --prefix frontend run test`
  - Maps to: REQ-004, AC-004
  - Depends on: T-013
  - State: complete
  - Authorization: Project-owner approval for local frontend test execution
  - Scope: The Windows-compatible Vitest invocation and complete frontend test suite
  - Expected: Vitest starts through the documented npm prefix form and exits 0 with the declared test count
  - Attempts: 1
  - Last result: `npm --prefix frontend run test` exited 0 with 78 test files and 857 tests passed in 252.85s.
  - Evidence: The documented Windows-compatible npm prefix invocation started Vitest 4.1.10 successfully and completed the full single-fork suite. No source or configuration change was required.

- [x] **T-015 Validate Alembic migration heads and syntax (R15)**
  - Run Pyright and Ruff on `backend/alembic/versions/2026-08-22_*.py`.
  - Verification: Run `tools\pyright.ps1` on `backend/alembic/versions/2026-08-22_*.py` and then run `tools\ruff.ps1 check backend/alembic/versions`
  - Maps to: REQ-004, AC-004
  - Depends on: T-014
  - State: complete
  - Authorization: Project-owner approval for read-only migration validation
  - Scope: Untracked `2026-08-22_*.py` migration syntax, typing, and lint behavior
  - Expected: The migration files pass both checks or produce a concrete file-specific blocker before any migration is applied
  - Attempts: 1
  - Last result: Pyright on all four `2026-08-22_*.py` files exited 0 with 0 errors, 0 warnings, and 0 informations; Ruff `check backend/alembic/versions` exited 0 with `All checks passed!`.
  - Evidence: The exact migration paths were enumerated and checked through the canonical wrappers using forward-slash arguments. Validation was read-only; no Alembic upgrade, downgrade, database write, or migration application occurred.

- [x] **T-016 Run Ruff formatter check on affected backend files (R16)**
  - Format-check the affected backend Python files and check diff without rewriting unrelated baseline files.
  - Verification: `tools\ruff.ps1 format --check backend/alembic/versions/2026-08-22_*.py` and `git diff --check`
  - Maps to: REQ-004, AC-004
  - Depends on: T-015
  - State: complete
  - Authorization: Project-owner approval for formatting checks on modified backend files
  - Scope: Ruff format enforcement before staging and the resulting diff check
  - Expected: Modified backend files are formatter-clean without rewriting unrelated files
  - Attempts: 2
  - Last result: The original broad `tools\ruff.ps1 format --check backend` exited 1 because 80 pre-existing backend files would be reformatted; the scoped affected-file check exited 0 with `4 files already formatted`, and `git diff --check` exited 0.
  - Evidence: The four migration files covered by this spec are formatter-clean. No formatter rewrite was performed, so unrelated committed baseline files and the user-owned dirty backend file remain untouched. The broad baseline finding is reproducible and recorded rather than hidden.

- [x] **T-017 Verify Frontend production build (R17)**
  - Run Next.js build.
  - Verification: `npm --prefix frontend run build`
  - Maps to: REQ-004, AC-004
  - Depends on: T-016
  - State: complete
  - Authorization: Project-owner approval for local production-build validation
  - Scope: The frontend production build and generated-output safety boundary
  - Expected: Next.js builds successfully without modifying tracked source or exposing environment values
  - Attempts: 1
  - Last result: `npm --prefix frontend run build` exited 0; Next.js 16.3.1 compiled, finished TypeScript, generated 48 static pages, and finalized route optimization.
  - Evidence: The production build completed without tracked frontend changes. Generated build output remained outside the tracked source boundary, and no environment values were exposed in the command output.

- [ ] **T-018 Verify Frontend typecheck and linting (R18)**
  - Run TypeScript typecheck and ESLint.
  - Verification: Run `npm --prefix frontend run typecheck` and then `npm --prefix frontend run lint`
  - Maps to: REQ-004, AC-004
  - Depends on: T-017
  - State: pending
  - Authorization: Project-owner approval for local frontend quality checks
  - Scope: Frontend TypeScript and ESLint checks over the active application
  - Expected: Both checks exit 0 and report no new errors attributable to the active worktree
  - Attempts: 0
  - Last result: not run
  - Evidence: Pending: record both command results and exact exit codes

- [ ] **T-019 Reconcile documentation and work registers (R19)**
  - Verify `docs/WORK.md` and `docs/HISTORY.md` state.
  - Verification: `powershell -NoProfile -Command "if ((Test-Path 'docs/WORK.md') -and (Test-Path 'docs/HISTORY.md')) { exit 0 } else { exit 1 }"`
  - Maps to: REQ-005, AC-005
  - Depends on: T-018
  - State: pending
  - Authorization: Project-owner approval for work-register reconciliation
  - Scope: Active and completed specification references in `docs/WORK.md` and `docs/HISTORY.md`
  - Expected: Each active spec has a truthful pending or completed status and completed evidence is not left in the active register
  - Attempts: 0
  - Last result: not run
  - Evidence: Pending: record the cross-document status comparison

- [ ] **T-020 Synchronize knowledge graph index (R20)**
  - Run Graphify update to index all changes.
  - Verification: `graphify update . --no-cluster`
  - Maps to: REQ-005, AC-005
  - Depends on: T-019
  - State: pending
  - Authorization: Project-owner approval for local Graphify refresh
  - Scope: The repository graph index after the documentation and configuration changes
  - Expected: Graphify completes successfully and the refreshed index includes the active specification lifecycle
  - Attempts: 0
  - Last result: not run
  - Evidence: Pending: record Graphify exit code and refresh summary
