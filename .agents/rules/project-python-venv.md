---
trigger: always_on
description: Always run backend tooling through the project virtualenv; never invoke bare python/pytest/ruff/pyright outside the tools/ wrappers.
---

## project-python-venv

The project virtualenv at `.venv/` is the canonical interpreter
(Python ≥ 3.13). PATH-precedence mistakes against the system interpreter
silently lose the venv pinning and poison results.

Rules:

- Always invoke backend tooling through `tools/`:
  - `tools/pytest.ps1` for the test suite
  - `tools/pyright.ps1` for type checking
  - `tools/ruff.ps1` for lint and format
- Never run bare `python`, `pytest`, `ruff`, or `pyright` for backend
  work; those fall through to the system interpreter.
- If `.venv\Scripts\python.exe` is missing, rebuild per
  `docs/OPERATIONS.md` "Recovering the Project Venv" (or
  `readme.md`). Do not continue with a different interpreter.
- The CI workflow installs
  `.[documents,gemini,dev,db,worker,s3,auth]` into the venv before
  invoking tooling.
- When verifying a change, use the smallest decisive check first:
  focused test file through `tools/pytest.ps1`, then type checking
  through `tools/pyright.ps1`.
