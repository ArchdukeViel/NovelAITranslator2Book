# Archived Architecture Note

This historical document was consolidated into `docs/architecture/architecture.md`. It may contain stale implementation status and should not be used as current architecture guidance.

# Post-Prompt-10 State

## Verdict

Prompt 11 is ready to start as the next implementation phase, with caveats. The core contracts it needs now exist: smart chunks, typed paragraph/chunk metadata, provider error classification, scheduler state shapes, translation QA, storage traceability, activity/job progress fields, and exact translation cache keys.

The project is not ready for public contribution credentials. It still has no registered public users, no owner/admin role boundary, no encrypted user credential storage, no credential revocation/deletion flow, no credential audit log, and no contribution consent/usage-limit workflow.

The admin frontend refactor is not ready as a complete shared-component pass. Current admin pages work and use `frontend/lib/api.ts`, but many requested admin refactor primitives are missing.

No scheduler routing, public credentials, auth/user system, database support, batch mode, or broad folder migration was implemented during this audit.

## What Is Confirmed Complete

- `SmartSegmentStage` exists in `backend/src/novelai/translation/pipeline/stages/segment.py`.
- `SegmentStage` is a compatibility alias of `SmartSegmentStage`.
- `Paragraph` and `TranslationChunk` are typed in `backend/src/novelai/translation/pipeline/context.py`.
- Paragraph IDs and chunk IDs are deterministic (`p0001`, `c0001`, etc.).
- `TranslationChunk` preserves `chunk_id`, `novel_id`, `chapter_ids`, `paragraph_ids`, `source_text`, `char_count`, and paragraph refs.
- `TranslateStage` accepts typed chunks and bridges to provider calls through `chunk.source_text`.
- `TranslationQAStage` is included before `PostProcessStage` in `backend/src/novelai/translation/service.py`.
- Failed QA raises `TranslationQualityError` and does not proceed to `PostProcessStage` or final save.
- Provider errors are normalized through `ProviderErrorCode` / `ProviderError` in `backend/src/novelai/core/errors.py`.
- Gemini and OpenAI providers normalize common SDK/API failures inside `backend/src/novelai/providers/*`.
- `backend/src/novelai/api/error_handlers.py` maps provider errors to the shared API error envelope.
- Pipeline events and failed stage names are persisted through storage traceability helpers.
- Chunk/provider/model state is represented in pipeline state and chunk state records.
- Scheduler state foundation exists in `backend/src/novelai/shared/pipeline.py` and storage traceability.
- Exact translation cache keys include prompt-affecting and model-affecting metadata.
- Storage runtime contracts exist for translation chunks, chunk outputs, temporary bundles, provider request records, scheduler state, and fetch cache entries.
- Central HTTP fetching exists under `backend/src/novelai/infrastructure/http/`.
- Syosetu/Novel18 uses `FetchService`.
- URL safety validation exists through `validate_safe_url`.
- Per-domain throttle exists in `backend/src/novelai/infrastructure/http/throttle.py`.
- Fetch cache interfaces and in-memory cache exist.
- Source quality gates exist in `backend/src/novelai/sources/quality.py`.
- Offline parser fixtures exist under `backend/tests/fixtures/sources/*`.
- Frontend API calls in the inspected admin/public pages go through `frontend/lib/api.ts`.
- Activity/job payloads can carry `errors`, `warnings`, `current_stage`, `current_label`, `paused_reason`, `resume_after`, and `model_states`.
- `storage/novel_library` is not mounted as a static app directory by the backend API.

## What Is Partially Implemented

- Scheduler readiness is structural only. The state shape can represent cooldown and quota exhaustion, but no full model selection, pause/resume, or all-models-exhausted routing exists.
- Provider/model fallback exists in translation and metadata paths, but it is not the full Prompt 11 scheduler.
- Provider request record helpers exist, but provider calls are not consistently recorded by every runtime path.
- Translation chunk, output, and temporary bundle storage helpers exist, but full lifecycle wiring is incomplete.
- Chunk state can distinguish successful, failed, and QA-failed chunks, but successful chunk reuse after pause/resume is not implemented.
- Source HTTP modernization is partial. Syosetu/Novel18 uses `FetchService`; Kakuyomu and Generic still use older `_fetch_page` logic with `novelai.utils.http_client.create_async_client`.
- API naming is partially canonical. Activity responses expose `activity_id`, `job_id`, `provider_key`, and `provider_model`, but legacy `id`, `provider`, `model`, and `source` fields still exist as compatibility aliases.
- Admin pages are functional but not yet extracted into the requested shared admin primitives.
- `npm run lint` is configured as `next lint`, but there is no committed ESLint config and the command is known to prompt interactively.

## What Is Not Implemented

- Prompt 11 multi-model scheduler routing.
- Prompt 12 public contribution credentials.
- Prompt 13 security hardening.
- Registered public users.
- Owner/admin role separation.
- Encrypted user credential storage.
- Credential revocation/deletion/audit workflow.
- Contribution consent and usage limits.
- Database support.
- Batch mode.
- Distributed workers.
- Full source adapter migration to `FetchService`.
- Full admin frontend refactor component library.

## Debt From Prompts 1-10

1. Full scheduler routing is missing.
2. Provider request records are not universally written for every provider call path.
3. Chunk output and temporary bundle lifecycle storage is not fully wired into translation runtime.
4. Successful chunk reuse and selective retry after pause/resume are not implemented.
5. Kakuyomu still uses legacy direct HTTP client behavior.
6. Generic still uses legacy direct HTTP client behavior.
7. `operations.py` remains thick with preliminary crawl fallback, activity logging, and export assembly.
8. `admin.py` remains thick with provider key validation/application and an embedded HTML admin dashboard.
9. Legacy aliases such as `id`, `source`, `provider`, and `model` remain in storage/API/frontend contracts.
10. Frontend admin shared primitives and hooks are mostly missing.
11. ESLint is not configured for non-interactive lint verification.
12. Source parser fixtures are representative but not exhaustive against live-site drift.
13. Storage backward compatibility is documented and tested in places, but older runtime data still needs careful migration discipline.
14. Public contribution credential prerequisites remain absent.

## Scheduler Readiness

Scheduler foundation fields exist.

Confirmed fields:

- `provider_key`
- `provider_model`
- `rpm_limit`
- `rpd_limit`
- `requests_this_minute`
- `requests_today`
- `cooldown_until`
- `exhausted_until`
- `status`
- `last_error_code`
- `last_error_message`

Confirmed locations:

- `backend/src/novelai/shared/pipeline.py`
- `backend/src/novelai/storage/traceability.py`
- `backend/src/novelai/storage/service.py`
- `backend/tests/test_storage_service.py`

Confirmed statuses:

- `available`
- `cooling_down`
- `daily_exhausted`
- `disabled`
- `failed`

Readiness assessment:

- Historical assessment at the time: ready for Prompt 11 implementation.
- Not currently a scheduler. No routing policy selects the next model, pauses all-cooldown jobs, resumes after cooldown, or avoids retranslating successful chunks after restart.

## Frontend Admin Refactor Readiness

Current admin routes exist under `frontend/app/(admin)/admin/`:

- `activity/page.tsx`
- `activity/[activityId]/page.tsx`
- `crawler/page.tsx`
- `dashboard/page.tsx`
- `editor/page.tsx`
- `library/page.tsx`
- `requests/page.tsx`
- `settings/page.tsx`
- `translation/page.tsx`

Current admin components under `frontend/components/admin/`:

- `activity-table.tsx`
- `admin-shell.tsx`
- `metric.tsx`
- `page-heading.tsx`
- `status-badge.tsx`

Requested refactor pieces missing:

- `frontend/lib/novel-input.ts`
- `frontend/lib/format.ts`
- `frontend/lib/admin-errors.ts`
- `frontend/components/admin/empty-state.tsx`
- `frontend/components/admin/error-banner.tsx`
- `frontend/components/admin/loading-rows.tsx`
- `frontend/components/admin/sortable-header.tsx`
- `frontend/components/admin/table-checkbox.tsx`
- `frontend/components/admin/dialog-shell.tsx`
- `frontend/components/admin/confirm-dialog.tsx`
- `frontend/components/admin/progress-bar.tsx`
- `frontend/hooks/use-sortable-table.ts`
- `frontend/hooks/use-progress-ramp.ts`

Readiness assessment:

- The admin frontend can consume the current API contract.
- A dedicated admin frontend refactor prompt is not ready to be treated as complete. It should be a future focused UI cleanup, not part of Prompt 11 scheduler work.

## API/Frontend Contract Risks

Confirmed strengths:

- API errors use `ApiErrorEnvelope` and central handlers.
- Frontend `ApiError`, `describeApiError`, `apiErrorKey`, and `apiErrorInlineMessage` exist in `frontend/lib/api.ts`.
- Activity/job progress helpers exist in `frontend/lib/api.ts`.
- Admin and public pages inspected use the exported `api` client rather than raw component-level backend fetches.

Observed naming classifications:

- `provider_key`, `provider_model`, `source_key`, `novel_id`, `chapter_id`, `chunk_id`, and `paragraph_id` are canonical and used in new contracts.
- `id` is a compatibility alias in activity records, requests, chapter summaries, route params, UI table rows, and legacy storage records.
- `provider` and `model` are compatibility aliases in activity queue records, translation versions, provider settings payloads, workflow profiles, and frontend provider settings.
- `source` is a compatibility alias for stored novel metadata, imported source strings, glossary source terms, and frontend display labels.
- Some `source`, `provider`, `model`, and `id` hits are unrelated local variables or domain-specific values, especially glossary source terms and UI IDs.

Risks:

- Removing aliases too early would break existing API consumers and stored data.
- Adding new API fields without updating `frontend/lib/api.ts` would recreate drift.
- `backend/src/novelai/api/routers/admin.py` contains embedded frontend-like admin HTML with direct `fetch()`; this is backend-owned HTML, not a React page, but it is still an architectural oddity to retire later.
- `operations.py` and `admin.py` are thicker than ideal and should be thinned through service extraction, not drive-by edits.

## Security/Product Boundary Risks

Confirmed current boundary:

- Authentication is a shared optional bearer token via `WEB_API_KEY`.
- There are no registered public users.
- There is no owner/admin role boundary.
- There are no public contribution credentials.
- Provider API keys are accepted through admin settings and stored only in runtime `SecretStr` settings/environment-backed values.
- Provider key status endpoints return configured status, not raw keys.
- Storage runtime files are not served directly as static files by the backend API.
- Frontend pages do not enforce authorization as a substitute for backend checks; backend routers use `verify_api_key` for protected operations.

Risks:

- Admin settings forms and local UI state can temporarily hold raw provider keys before submission.
- No credential encryption-at-rest system exists because credential storage is not implemented.
- No credential audit log exists.
- No object-level public user authorization exists.
- Public contribution credentials are blocked until auth, roles, encrypted storage, revocation/deletion, audit logging, consent, and usage limits are implemented.

## Historical Recommended Next Prompt (Superseded)

At the time, this note recommended Prompt 11: multi-model scheduler. Use `docs/architecture/architecture.md` for current implementation guidance.

Prompt 11 should:

- Use the existing provider error codes and retry metadata.
- Use existing chunk state and scheduler state foundations.
- Record model cooldown and daily exhaustion without losing chunk progress.
- Pause jobs when all models are cooling down or exhausted.
- Resume from untranslated or retryable chunks.
- Avoid retranslating successful chunks unless explicitly forced.
- Preserve prompt versioning, glossary handling, exact cache keys, provider request recording, QA, and chapter-based final storage.

Do not run Prompt 12 public contribution credentials yet. It is blocked by missing product/security foundations.

Do not combine admin frontend refactor work with Prompt 11 unless the change is only minimal display wiring for scheduler state already returned by the backend.

## Commands Run

- `Get-Content docs\architecture\architecture.md`
  - Result: inspected source-of-truth architecture.
- `Get-Content docs\architecture\IMPLEMENTATION_AUDIT.md`
  - Result: inspected final implementation audit and previous test results.
- `Get-Content docs\architecture\PROMPT_1_TO_10_SUMMARY.md`
  - Result: inspected prompt summary.
- `Get-Content docs\reference\DATA_OUTPUT_STRUCTURE.md`
  - Result: inspected storage/runtime schema documentation.
- `rg` inspections over backend translation, shared, storage, activity, orchestration, providers, sources, API, frontend, and tests.
  - Result: confirmed implementation anchors and debt listed above.
- `rg "provider[^_]|model[^_]|source[^_]|\bid\b" backend/src/novelai frontend/lib frontend/app`
  - Result: naming hits classified as canonical names, compatibility aliases, real debt, or unrelated local/domain variables.
- `rg --files "frontend/app/(admin)/admin"`
  - Result: listed current admin pages.
- `rg --files frontend/components/admin frontend/hooks frontend/lib`
  - Result: listed current admin components and frontend lib files; `frontend/hooks` does not exist.
- `rg --files frontend | rg "(^|/)(eslint\.config\.|\.eslintrc)"`
  - Result: no committed ESLint config found.
- `pytest backend/tests -q`
  - Result: `500 passed, 7 skipped in 21.63s`.
- `pyright`
  - Result: `0 errors, 0 warnings, 0 informations`.
  - Note: pyright reported a newer version is available.
- `npm run typecheck`
  - Working directory: `frontend`
  - Result: passed.
- `npm run build`
  - Working directory: `frontend`
  - Result: passed; Next.js generated 13 pages.
- `npm run lint`
  - Result: not run. The package script is `next lint`, no ESLint config is committed, and prior verification showed it prompts interactively for setup. Per this gate prompt, no unrelated ESLint config was created.
