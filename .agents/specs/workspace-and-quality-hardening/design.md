# Design: Workspace and Quality Hardening

Spec ID: workspace-and-quality-hardening
Version: 1.0.0
Status: Approved
Updated: 2026-08-24

## Architecture & System Invariants

### 1. Root & Workspace Hygiene (R1–R5)
- Repository root must only contain canonical files. Stray items (`file`, `Caddyfile/`) are removed.
- `.gitignore` allows `.vscode/settings.json`, `.vscode/extensions.json`, `.vscode/tasks.json`, `.vscode/mcp.json`.
- `.vscode/settings.json` excludes noisy build artifacts while keeping `.agents/` searchable.
- `.opencode/` remains untracked in git, providing local sandbox isolation for scratch scripts in `.opencode/scripts/`.

### 2. Tooling Wrappers & Windows Path Resilience (R6–R9)
- All PowerShell scripts in `tools/*.ps1` enforce:
  - Strict virtualenv resolution (`.venv\Scripts\python.exe`).
  - Path normalization: convert `/` to `\` in path arguments before forwarding to Python modules.

### 3. VS Code Developer Task Ergonomics (R10–R13)
- `.vscode/tasks.json` defines complete task registry:
  - `Backend: Pyright Typecheck` (default build)
  - `Backend: Run Tests` (default test)
  - `Backend: Test Watch` (background watcher with `$tsc` / test matcher)
  - `Backend: Ruff Lint & Format`
  - `Frontend: Typecheck`
  - `Frontend: Run Tests`
  - `Frontend: Build`
  - `Graphify: Update Index`
- `.vscode/extensions.json` pins exact necessary toolchain.

### 4. Verification & CI Baseline Alignment (R14–R20)
- Frontend: `frontend/vitest.config.ts` runs single-fork jsdom test suite cleanly via `npm --prefix frontend run test`.
- Backend: Alembic migrations under `backend/alembic/versions/` conform to SQLAlchemy ORM models and pass Pyright/Ruff.
- Formatter: `tools/ruff.ps1 format` runs cleanly on modified files prior to commit staging.
- Documentation & Work Tracking: `docs/WORK.md` and `docs/HISTORY.md` maintain single-source-of-truth status.
- Graphify: AST graph index updated with 0 missing required symbols.

## Traceability

| Requirement | Acceptance criterion | Planned task IDs |
| --- | --- | --- |
| REQ-001 | AC-001 | T-001, T-002, T-003, T-004, T-005 |
| REQ-002 | AC-002 | T-006, T-007, T-008, T-009 |
| REQ-003 | AC-003 | T-010, T-011, T-012, T-013 |
| REQ-004 | AC-004 | T-014, T-015, T-016, T-017, T-018 |
| REQ-005 | AC-005 | T-019, T-020 |
