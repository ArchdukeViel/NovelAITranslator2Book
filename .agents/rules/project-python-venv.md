---
trigger: always_on
description: Always run backend tooling through the project virtualenv; never invoke bare python/pytest/ruff/pyright outside the tools/ wrappers.
---

# Project Python Virtualenv (`.venv`)

The project virtualenv at `.venv/` is the canonical interpreter (Python ≥ 3.14). PATH-precedence mistakes against the system interpreter silently lose package pinning and produce deceptive test or lint results.

## Mandatory Tooling Wrappers

Always invoke backend quality tools through the repository wrappers with `-ExecutionPolicy Bypass`:
- `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 [args]` &mdash; focused and suite test runs.
- `powershell -ExecutionPolicy Bypass -File tools/pyright.ps1 [args]` &mdash; static type analysis.
- `powershell -ExecutionPolicy Bypass -File tools/ruff.ps1 [check|format] [args]` &mdash; linting and formatting.
- `powershell -ExecutionPolicy Bypass -File tools/docs-check.ps1` &mdash; documentation contract and path validation.

## One-Off Scripts & CLI Commands

- **Ad-Hoc Scripts & Module Execution**: Run `.venv\Scripts\python.exe <script-path> [args]`. Never use bare `python`. Note that `backend/src` must be in `PYTHONPATH` or `novelai` installed in editable mode (`pip install -e backend`) for package imports to resolve. Prefer module execution:
  ```powershell
  .venv\Scripts\python.exe -m novelai --interface cli
  .venv\Scripts\python.exe tools\database\export_seed.py
  ```
- **Alembic Migrations**: Invoke Alembic via the virtualenv:
  ```powershell
  .venv\Scripts\python.exe -m alembic -c backend/alembic.ini <command>
  ```
- **Dependency Management**: `pyproject.toml` is the sole authoritative manifest. Dependencies and lockfiles are synchronized only by running `deploy\update-lockfiles.ps1` after an authorized dependency change.

## CI Test Sharding Contract

CI divides backend tests into two tiers:
- `backend-tests` (Core): Unit tests running in parallel with `-n 2`, excluding 18 integration/extended test files.
- `backend-extended`: Sharded matrix (`orchestration-and-pipeline`, `web-api-and-auth`, `components-and-lifecycle`) running the heavy suites.
When authoring or reorganizing test files in `backend/tests/`, verify where the test runs in `.github/workflows/ci.yml` to prevent runner timeouts or missing test coverage.

## Recovery & Verification Protocol

- If `.venv\Scripts\python.exe` is missing, recover it per `docs/OPERATIONS.md` ("Recovering the Project Venv"). Never fallback to a system or global Python interpreter.
- When verifying backend changes, follow the smallest-decisive ladder:
  1. Focused test file: `powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_<name>.py`
  2. Type check: `powershell -ExecutionPolicy Bypass -File tools\pyright.ps1`
  3. Linter/Formatter: `powershell -ExecutionPolicy Bypass -File tools\ruff.ps1 check`
