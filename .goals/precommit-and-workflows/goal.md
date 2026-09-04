# Goal: Pre-commit Hardening and Workflows Audit & Optimization

## Goal Description
Audit and improve `.pre-commit-config.yaml` with essential safety hooks (merge conflicts, YAML syntax, large files, case collisions). Review and audit all 13 GitHub Action workflows in `.github/workflows/`. Fix existing regression in `backend/tests/test_ci_workflows.py` (`test_production_compose_contract` expecting 4 pinned images instead of 3), synchronize lockfiles (`uv.lock`), and optimize workflow execution times and security posture. Conduct 5 iterations of review, audit, findings, and improvements with independent verification.

## Acceptance Criteria
1. `.pre-commit-config.yaml` contains hardened local safety checks (`trailing-whitespace`, `end-of-file-fixer`, `check-merge-conflict`, `check-yaml`, `check-added-large-files`, `check-case-conflict`, `ruff`, `ruff-format`) and passes `uv run --locked pre-commit run --all-files`.
2. `test_ci_workflows.py` passes all 31 tests via `powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_ci_workflows.py`.
3. `uv.lock` and lockfiles synchronized via `deploy\update-lockfiles.ps1` and match `pyproject.toml`.
4. Documentation contract check passes with 0 violations (`powershell -ExecutionPolicy Bypass -File tools\docs-check.ps1`).
5. All 13 workflows in `.github/workflows/` audited for orphaned triggers, timeouts, caching, action pins, and security risks (validated offline by Zizmor).
6. 5 iterative review and audit improvement cycles executed with Inspector verification.

## Out of Scope
- No production database or storage mutation.
- No removal of active reusable workflows (`reusable-test-database-migration.yml`, `reusable-test-recovery.yml`).
- No secret or credential exposure.
- No unpinned third-party actions in `.github/workflows/`.

## Quality Gates
- Pre-commit: `uv run --locked pre-commit run --all-files`
- Workflow tests: `powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_ci_workflows.py`
- Backend Lint: `powershell -ExecutionPolicy Bypass -File tools\ruff.ps1 check .`
- Backend Types: `powershell -ExecutionPolicy Bypass -File tools\pyright.ps1`
- Docs Check: `powershell -ExecutionPolicy Bypass -File tools\docs-check.ps1`
- Security Audit: `uvx --from zizmor==1.29.0 zizmor --offline --format=json .github/workflows`

## Commit Convention
- Builder: `type(scope): [B] description` (trailer `Assisted-by: OpenAI:GPT-5.6 Luna`)
- Inspector: `chore(scope): [I] description` (trailer `Assisted-by: OpenAI:GPT-5.6 Sol`)
- Max 72 chars, imperative mood.
