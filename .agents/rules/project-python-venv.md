---
trigger: always_on
description: Always run backend tooling through the project virtualenv; never invoke bare python/pytest/ruff/pyright outside the tools/ wrappers.
---

# Project Python Virtualenv (`.venv`)

The project virtualenv at `.venv/` is the canonical interpreter (Python ≥ 3.14). PATH-precedence mistakes against the system interpreter silently lose package pinning and produce deceptive test or lint results.

## Mandatory Tooling Wrappers

Always invoke backend quality tools through the repository wrappers:
- `tools/pytest.ps1 [args]` &mdash; focused and suite test runs.
- `tools/pyright.ps1 [args]` &mdash; static type analysis.
- `tools/ruff.ps1 [check|format] [args]` &mdash; linting and formatting.
- `tools/docs-check.ps1` &mdash; documentation contract and path validation.

## One-Off Scripts & CLI Commands

- **Ad-Hoc Scripts**: Run `.venv\Scripts\python.exe <script-path> [args]`. Never use bare `python`.
  ```powershell
  .venv\Scripts\python.exe tools\database\export_seed.py
  ```
- **Alembic Migrations**: Invoke Alembic via the virtualenv:
  ```powershell
  .venv\Scripts\python.exe -m alembic -c backend/alembic.ini <command>
  ```
- **Dependency Management**: `pyproject.toml` is the sole authoritative manifest. Dependencies and lockfiles are synchronized only by running `deploy\update-lockfiles.ps1` after an authorized dependency change.

## Recovery & Verification Protocol

- If `.venv\Scripts\python.exe` is missing, recover it per `docs/OPERATIONS.md` ("Recovering the Project Venv"). Never fallback to a system or global Python interpreter.
- When verifying backend changes, follow the smallest-decisive ladder:
  1. Focused test file: `powershell -File tools\pytest.ps1 backend/tests/test_<name>.py`
  2. Type check: `powershell -File tools\pyright.ps1`
  3. Linter/Formatter: `powershell -File tools\ruff.ps1 check`
