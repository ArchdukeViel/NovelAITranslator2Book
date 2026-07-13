# Implementation Prompt — Milestone M1 (Glossary and Router Repair)

Copy-paste the fenced block below into a new session. It is pre-filled from
`docs/operations/implementation-prompt-template.md`, the M1 entry in
`docs/roadmap.md`, and the archived `glossary-management-consolidation` and
`jp-en-prompt-quality-policy` specs.

---

```
You are working in the NovelAITranslator2Book repository on branch main.
Latest commit: 16f41ffe.

## 1. Read These Files First (in this order)

1. `AGENTS.md` — operating rules, layer boundaries, canonical names, verification commands.
2. `docs/architecture/architecture.md` — canonical architecture, layer rules, ownership.
3. `docs/roadmap.md` — milestone plan M0-M7, acceptance gates.
4. `docs/DEBT.md` — active technical debt register, completion criteria.
5. `docs/SPECS_COMPLETION.md` — active/archived specs inventory.
6. `docs/storage-contract.md` — canonical ownership matrix and restore rules.
7. `docs/operations/deployment.md` — container topology, reverse proxy routing.
8. `docs/operations/runbook.md` — health, worker, cache invalidation procedures.
9. `docs/operations/data-recovery.md` — backup and restore procedures.
10. `.agents/kiro/archive/glossary-management-consolidation/design.md` — glossary resolution contract, data model, API shape, non-goals.
11. `.agents/kiro/archive/glossary-management-consolidation/requirements.md` — numbered requirements (REQ-N).
12. `.agents/kiro/archive/glossary-management-consolidation/tasks.md` — implementation checklist with REQ-N tags.
13. `.agents/kiro/archive/jp-en-prompt-quality-policy/design.md` — JP-EN prompt quality policy contract, activation rules, test design.
14. `.agents/kiro/archive/jp-en-prompt-quality-policy/requirements.md` — numbered requirements (REQ-N).
15. `.agents/kiro/archive/jp-en-prompt-quality-policy/tasks.md` — implementation checklist with REQ-N tags.
16. `docs/glossary/glossary-system.md` — glossary system overview, known issues, implementation status.

## 2. Your Task

Implement **Milestone M1 — Glossary and Router Repair** from `docs/roadmap.md`.

### Scope (from roadmap.md)

- Refactor circular glossary module imports.
- Fix prompt quality policy test drift (expected prompt assertion mismatch).
- Enforce the router layer guard (prevent direct storage/DB imports in API endpoints).

### Acceptance Gates (from roadmap.md)

- `test_admin_glossary_api.py` passes.
- Router layer validation script returns green.

### Blockers (from roadmap.md)

- DEBT-006: admin_glossary routers cyclic imports block test runner collection.
- DEBT-073: test_glossary_prompt_injection test expects stale prompt text.

### Current State (verified by running tests on 2026-07-13)

**DEBT-006 — Circular import in admin_glossary routers:**
- The circular import is currently *partially mitigated* by a lazy `_ensure_sub_routers_merged()` function in `admin_glossary.py` (line 1302) that defers importing the sub-routers until first access. The test file calls `_ensure_sub_routers_merged()` at module load (line 38).
- However, the architecture is still fragile: all four sub-routers (`admin_glossary_apply.py`, `admin_glossary_candidates.py`, `admin_glossary_provider.py`, `admin_glossary_suggestions.py`) import Pydantic schemas and helper functions from `admin_glossary.py` at **module level**, while `admin_glossary.py` imports them back lazily. This creates a latent cycle that breaks under certain import orders.
- `test_admin_glossary_api.py` currently collects (53 tests) and runs, but 1 test fails: `test_not_found_behavior_for_missing_novel_entry_alias_and_qa` (asserts 404 but gets 400 — a novel lookup validation issue, not the circular import itself).
- DEBT-006 completion criteria: "Extracted helper functions and model schema definitions to a clean non-circular shared file."

**DEBT-073 — Glossary prompt injection test drift:**
- `test_glossary_prompt_injection.py::test_canonical_term_and_translation_render_deterministically` fails.
- The test expects:
  ```
  "Use these approved translations consistently:\n"
  "- maso => magicules\n"
  "- seireikai => Spirit Realm"
  ```
- The actual prompt now produces:
  ```
  "The glossary is authoritative. If a source term appears below you MUST use its approved translation.\n"
  "\n"
  "LOCKED (override any other translation):\n"
  "- maso => magicules\n"
  "- seireikai => Spirit Realm"
  ```
  (The `maso` entry has `owner_locked=True`, which triggers the "LOCKED" section header.)
- DEBT-073 completion criteria: "Test assertions updated to match current prompt policy."
- The prompt policy is defined in `backend/src/novelai/services/glossary_prompt_injection.py` (line 278+). The test must be updated to match the current rendered output, not the other way around — the prompt builder is the source of truth.

**Router layer guard:**
- The router boundary guard already returns **no matches** (verified via `rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"`).
- The CI workflow (`.github/workflows/ci.yml`) already enforces this via a `grep` step in the `backend-lint` job.
- The `docs/glossary/glossary-system.md` known-issues table (line 115) still lists "5 glossary routers import `db.models.glossary`, `StorageService` directly" as a deferred issue (DEBT-014, DEBT-054), but the guard itself is green. This milestone's acceptance gate is that the *validation script* returns green, which it already does.

### Spec Contract — glossary-management-consolidation (from design.md)

Affected areas:

| Area | Expected change |
|---|---|
| `backend/src/novelai/glossary/` | Resolution rules and hash generation |
| `backend/src/novelai/services/orchestration/` | Use resolved glossary for translation |
| `backend/src/novelai/api/` | Admin glossary routes stay thin |
| `frontend/` | Display backend conflict/status fields only |
| `backend/tests/` | Resolution, prompt, auth tests |

Glossary entry canonical fields: `term_id`, `source_text`, `target_text`, `scope`, `novel_id`, `status`, `notes`, `created_at`, `updated_at`, `created_by_user_id`.

Resolution rules (order):
1. Load approved global entries.
2. Load approved novel entries for `novel_id`.
3. Replace global entries when novel entry has same normalized source term.
4. Sort deterministically by source term, then target term.
5. Hash resolved entries to produce `glossary_hash`.

Acceptance criteria:
1. Translation prompt receives one resolved glossary view.
2. Novel-approved terms override global-approved terms.
3. Candidate/rejected terms never enter prompts.
4. Admin glossary mutations require owner session.

Non-goals: No public-user glossary contribution, no LLM auto-approval, no frontend-only conflict resolution.

### Spec Contract — jp-en-prompt-quality-policy (from design.md)

Scope: JP-EN prompt review rules, snapshot tests, regression fixtures, prompt quality checklist, prompt policy/template versioning, cache identity checks.

Activation rules: JP-EN policy applies when `source_language in {"ja", "japanese"}` and `target_language in {"en", "english"}`.

Prompt versioning: `JP_EN_PROMPT_POLICY_VERSION = "jp_en_quality_v1"`. Prompt metadata should include `{"prompt_policy": "jp_en_quality", "prompt_policy_version": "jp_en_quality_v1"}`.

Cache identity must include: source language, target language, model/provider, style preset, consistency mode, glossary revision/hash, prompt template version, JP-EN prompt policy version (when applied).

Non-goals: No new translation pipeline, no scheduler changes, no provider routing changes, no glossary workflow changes, no public reader changes, no live LLM tests, no duplicating completed prompt correctness hardening.

### Implementation Checklist

**DEBT-006 — Break the circular import (completion criteria: extract shared schemas/helpers to a non-circular file):**

- [ ] 1. Create a new shared module for glossary router schemas and helpers
  - [ ] 1.1 Create `backend/src/novelai/api/routers/admin_glossary_shared.py` (or similar) containing:
    - All Pydantic request/response models currently defined in `admin_glossary.py` (e.g. `GlossaryEntryCreateRequest`, `GlossaryEntryResponse`, `GlossaryAliasResponse`, `GlossaryProviderSuggestionRequest`, `GlossaryApplyPreviewResponse`, etc. — ~30+ models).
    - Shared helper functions: `_body_fields`, `_require_novel`, `_repo`, `_owner_user_id`, `_raise_repo_error`, `_entry_response`, `_alias_response`, `_provenance_response`, `_event_response`, `_qa_response`, `_provider_error_status`, `_safe_provider_error_detail`.
    - Type aliases: `NonEmptyStr`, `EntryStatus`, `TermType`, `AliasType`, `AliasAppliesTo`, `QASeverity`, `QAFindingStatus`, `CandidateImportMode`, `CandidateImportAction`.
  - [ ] 1.2 The shared module must have **no imports** from any `admin_glossary*.py` router file — only from `novelai.api.auth`, `novelai.core.errors`, `novelai.db.models`, `novelai.services`, `sqlalchemy`, `pydantic`, `fastapi`.
  - [ ] 1.3 Update `admin_glossary.py` to import schemas/helpers from the shared module instead of defining them inline.
  - [ ] 1.4 Update all four sub-routers (`admin_glossary_apply.py`, `admin_glossary_candidates.py`, `admin_glossary_provider.py`, `admin_glossary_suggestions.py`) to import from the shared module instead of from `admin_glossary.py`.
  - [ ] 1.5 Remove the `_ensure_sub_routers_merged()` lazy-merge pattern from `admin_glossary.py` — with the shared module breaking the cycle, the sub-routers can be imported normally at module level, or the merge can happen eagerly.
  - [ ] 1.6 Update `test_admin_glossary_api.py` to remove the `_ensure_sub_routers_merged()` call (line 38) if it's no longer needed.
  - [ ] 1.7 Verify no router file imports `db.models.*` or `storage.service.*` directly (the shared module uses `db.models` but it is not a router — it's a shared schema module). The router boundary guard must still return no matches for files in `api/routers/` excluding `dependencies.py`. **Note:** if the shared module lives inside `api/routers/`, it must be added to the guard's exclusion list, OR it must be placed outside `api/routers/` (e.g. `api/schemas/admin_glossary.py`). Prefer placing it outside `api/routers/` to avoid weakening the guard.

- [ ] 2. Fix the `test_not_found_behavior_for_missing_novel_entry_alias_and_qa` failure
  - [ ] 2.1 Investigate why the test expects 404 but gets 400 for a missing novel (novel_id 999999). This is likely a validation-ordering issue in `_require_novel` or the service layer.
  - [ ] 2.2 Fix the novel lookup so missing novels return 404 before other validation errors, OR update the test if the 400 behavior is intentional and correct per the current API contract.
  - [ ] 2.3 Confirm all 53 tests in `test_admin_glossary_api.py` pass.

**DEBT-073 — Fix prompt injection test drift (completion criteria: test assertions match current prompt policy):**

- [ ] 3. Update `test_canonical_term_and_translation_render_deterministically` in `backend/tests/test_glossary_prompt_injection.py`
  - [ ] 3.1 Read `backend/src/novelai/services/glossary_prompt_injection.py` to understand the current rendered output format, especially the "LOCKED" section for `owner_locked=True` entries.
  - [ ] 3.2 Update the expected string in the test assertion (line 146-153) to match the actual current output:
    ```
    "GLOSSARY FOR THIS NOVEL\n"
    "These are approved owner glossary rules. Use them consistently when the source term appears.\n"
    "\n"
    "The glossary is authoritative. If a source term appears below you MUST use its approved translation.\n"
    "\n"
    "LOCKED (override any other translation):\n"
    "- maso => magicules\n"
    "- seireikai => Spirit Realm"
    ```
    (Verify the exact text by running the test with `-vv` and copying the actual output.)
  - [ ] 3.3 Do NOT change the prompt builder to match the old test — the prompt builder is the source of truth and the test was stale.
  - [ ] 3.4 Run the full `test_glossary_prompt_injection.py` suite and confirm all 15 tests pass.

**Router layer guard enforcement:**

- [ ] 4. Verify the router boundary guard is green
  - [ ] 4.1 Run: `rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"` — must return no matches.
  - [ ] 4.2 If the shared module from step 1 is placed inside `api/routers/`, add it to the guard's exclusion list in both the CI workflow (`.github/workflows/ci.yml` `backend-lint` job) and the AGENTS.md documented command. Prefer placing it outside `api/routers/` to avoid this.
  - [ ] 4.3 Confirm the CI `backend-lint` grep step still passes.

- [ ] 5. Update `docs/DEBT.md`
  - [ ] 5.1 DEBT-006: mark `Status: Resolved` once `test_admin_glossary_api.py` passes all 53 tests and the circular import is eliminated (no lazy-merge workaround). Add evidence: file created, test results.
  - [ ] 5.2 DEBT-073: mark `Status: Resolved` once `test_glossary_prompt_injection.py` passes all 15 tests. Add evidence: test assertion updated, test results.

- [ ] 6. Update `docs/roadmap.md`
  - [ ] 6.1 Flip M1 `Status` from `Blocked` to `Done` once both acceptance gates pass.

- [ ] 7. Update `docs/glossary/glossary-system.md`
  - [ ] 7.1 Update the "Known Issues" table (line 114) to mark the circular import as resolved.
  - [ ] 7.2 Update the "Router layer violations" row if the shared module changes the violation count.

## 3. Constraints

- Do not modify completed Phase 0 or Phase 1 work unless a regression is proven.
- Do not reintroduce direct storage/DB/source imports in routers. Routers stay thin.
- Use canonical identifiers: `novel_id`, `chapter_id`, `request_id`, `audit_id`, `requesting_user_id`, `credential_owner_user_id`, `provider_key`, `provider_model`, `activity_id`, `job_id`, `request_id`, `credential_id`, `glossary_hash`, `prompt_version`.
- Use owner-only authorization via `require_role("owner")`. Do not invent multi-admin roles.
- Use `ENV`, not `APP_ENV`. Use canonical setting names: `PUBLIC_FRONTEND_URL`, `SESSION_SECRET_KEY`, `WEB_CORS_ORIGINS`, `S3_BUCKET`.
- Follow the existing service extraction pattern: create service in `services/`, add factory to `api/routers/dependencies.py`, thin router to pure HTTP adapter.
- For takedown: use HTTP 451 for legally blocked content. Do not make it configurable.
- For audit: use `audit_id` (not `event_id` or `id`). Use `novel_id`/`chapter_id` in target maps. Use display name + email hash, not raw email.
- Add or update tests for every behavior change. One runnable check is enough for a one-liner.
- Run `python -m ruff check .`, `python -m pyright`, and targeted tests before declaring done.
- Run the router boundary guard: `rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"` must return no matches.
- Update `docs/DEBT.md` when debt items are resolved (mark Status: Resolved, add evidence).
- Do not commit unless explicitly authorized. Do not push. Do not amend. Do not force checkout.

## 4. Preflight (do this before coding)

1. Inspect the five glossary router files in `backend/src/novelai/api/routers/`:
   - `admin_glossary.py` (1320 lines — defines all schemas, helpers, CRUD endpoints, and the lazy merge function).
   - `admin_glossary_apply.py` (imports 10 symbols from `admin_glossary.py` at module level).
   - `admin_glossary_candidates.py` (imports 6 symbols from `admin_glossary.py` at module level).
   - `admin_glossary_provider.py` (imports 1 symbol at module level, 6 more lazily inside functions).
   - `admin_glossary_suggestions.py` (imports 3 symbols from `admin_glossary.py` at module level).
2. Confirm the current state: `test_admin_glossary_api.py` has 1 failure (`test_not_found_behavior_for_missing_novel_entry_alias_and_qa`), `test_glossary_prompt_injection.py` has 1 failure (`test_canonical_term_and_translation_render_deterministically`).
3. Identify the smallest diff that satisfies the acceptance gates:
   - Create one shared schemas/helpers module.
   - Update 5 router files to import from it.
   - Update 2 test files (remove `_ensure_sub_routers_merged()` call, fix prompt assertion).
   - Fix the 404-vs-400 novel lookup bug.
4. List the files you expect to change:
   - **New:** `backend/src/novelai/api/schemas/admin_glossary.py` (shared schemas + helpers, outside `routers/` to avoid weakening the guard).
   - **Modified:** `backend/src/novelai/api/routers/admin_glossary.py`, `admin_glossary_apply.py`, `admin_glossary_candidates.py`, `admin_glossary_provider.py`, `admin_glossary_suggestions.py`.
   - **Modified:** `backend/tests/test_admin_glossary_api.py`, `backend/tests/test_glossary_prompt_injection.py`.
   - **Modified:** `docs/DEBT.md`, `docs/roadmap.md`, `docs/glossary/glossary-system.md`.
5. State any assumptions:
   - The 404-vs-400 bug is a validation-ordering issue, not an intentional API contract change.
   - The prompt builder output is correct and the test is stale (DEBT-073 says "test expects stale prompt text").
   - Placing the shared module in `api/schemas/` (not `api/routers/`) avoids needing to update the router boundary guard exclusion list.

## 5. Implementation Order

1. Add or update settings in `backend/src/novelai/config/settings.py` if the spec requires new config. (M1 does not — skip.)
2. Add or update SQLAlchemy models and Alembic migrations if the spec requires new tables. (M1 does not — skip.)
3. Add or update the service layer in `backend/src/novelai/services/` or `backend/src/novelai/services/orchestration/`. (M1 does not — skip.)
4. Add the factory to `backend/src/novelai/api/routers/dependencies.py`. (M1 does not — skip.)
5. Add or update the router in `backend/src/novelai/api/routers/`. (M1 does — refactor existing routers.)
   - Create `backend/src/novelai/api/schemas/admin_glossary.py` with all shared schemas, type aliases, and helpers.
   - Update `admin_glossary.py` to import from the shared module and remove the lazy `_ensure_sub_routers_merged()`.
   - Update the four sub-routers to import from the shared module.
6. Add or update frontend API client in `frontend/lib/api.ts` or `frontend/lib/public-api.ts`. (M1 does not — skip.)
7. Add or update frontend route in `frontend/app/(admin)/` or `frontend/app/(public)/`. (M1 does not — skip.)
8. Add or update tests in `backend/tests/` and `frontend/`. (M1 does — fix 2 test files.)
   - Remove `_ensure_sub_routers_merged()` call from `test_admin_glossary_api.py`.
   - Fix the 404-vs-400 novel lookup test.
   - Update the prompt assertion in `test_glossary_prompt_injection.py`.
9. Update `docs/DEBT.md` to mark DEBT-006 and DEBT-073 as resolved.
10. Update `docs/glossary/glossary-system.md` known-issues table.

## 6. Verification (run before declaring done)

| Command | Purpose |
|---|---|
| `python -m ruff check .` | Lint |
| `python -m pyright` | Typecheck |
| `python -m pytest backend/tests/test_admin_glossary_api.py --tb=short -q` | All 53 admin glossary API tests must pass |
| `python -m pytest backend/tests/test_glossary_prompt_injection.py --tb=short -q` | All 15 prompt injection tests must pass |
| `rg -n "^from novelai\.(db\.models\|storage\.service\|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"` | Router boundary guard — must return no matches |
| `git diff --check` | Diff integrity |

If frontend files changed (not expected for M1):

| Command | Purpose |
|---|---|
| `cd frontend && npm run typecheck` | Frontend typecheck |
| `cd frontend && npm run lint` | Frontend lint |
| `cd frontend && npm run build` | Frontend build |

## 7. Final Report

Report:
1. What you implemented (files changed, shared module created, circular import eliminated, test fixes).
2. What you verified (commands run, test counts, router guard result).
3. What remains (follow-up debt, unrun checks, known limitations).
4. Any deviations from the spec and why.
5. Any new debt items discovered during implementation.

Do not mark a debt item complete until implementation and validation justify it.
```

---

## Notes Specific to M1

- **Two specs are involved:** `glossary-management-consolidation` (for the router architecture) and `jp-en-prompt-quality-policy` (for the prompt test drift). Both are archived but their design contracts are the canonical reference.
- **The circular import is partially mitigated** by the lazy `_ensure_sub_routers_merged()` pattern, but DEBT-006's completion criteria explicitly call for extracting shared schemas/helpers to a non-circular file — the lazy pattern is a workaround, not a fix.
- **The prompt test failure (DEBT-073) is a stale test, not a prompt bug.** The prompt builder was updated to produce "LOCKED (override any other translation):" for `owner_locked=True` entries, but the test still expects the old "Use these approved translations consistently:" header. Update the test, not the prompt.
- **The router layer guard is already green.** The acceptance gate "router layer validation script returns green" is already satisfied. The work is to keep it green after the refactor — place the shared schemas module outside `api/routers/` to avoid weakening the guard.
- **The 404-vs-400 test failure** in `test_admin_glossary_api.py` is a separate issue from the circular import. It needs investigation — likely a validation-ordering bug in `_require_novel` or the service layer where a missing novel returns 400 (validation error) instead of 404 (not found).
