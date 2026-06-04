# Implementation Audit

## Summary

The repository broadly follows the revised top-level architecture: API routers, services/orchestration, sources, providers, prompts, storage, activity, and frontend API client boundaries all exist. The current implementation is still transitional in the areas the architecture names as immediate debt.

The highest-risk gaps are:

- `SegmentStage` is paragraph-only and stores chunks as plain strings.
- Provider failures are mostly generic exceptions, not normalized provider error codes.
- Pipeline state is not chunk-traceable and does not persist partial translated chunks.
- Source adapters still combine fetching, parsing, retry, throttling, validation, and source selectors.
- Prompt construction mostly lives in `prompts/*`, but metadata prompts are built in orchestration.
- API/frontend payloads still expose legacy names such as `source`, `provider`, `model`, and generic `id`.
- Credentials are single-owner/admin runtime settings, not public-user credentials.

The project does not currently have authenticated public users, admin role separation, encrypted credential storage, credential revocation/audit flows, or object-level authorization. Public contribution credentials therefore require an explicit product-boundary/security change and should not be bolted onto the current admin settings flow.

## Current Pipeline Map

Current translation pipeline files:

- `backend/src/novelai/translation/service.py`
- `backend/src/novelai/translation/pipeline/context.py`
- `backend/src/novelai/translation/pipeline/pipeline.py`
- `backend/src/novelai/translation/pipeline/stages/fetch.py`
- `backend/src/novelai/translation/pipeline/stages/parse.py`
- `backend/src/novelai/translation/pipeline/stages/segment.py`
- `backend/src/novelai/translation/pipeline/stages/translate.py`
- `backend/src/novelai/translation/pipeline/stages/post_process.py`

`TranslationService` wires the runtime stage order as:

```text
FetchStage -> ParseStage -> SegmentStage -> TranslateStage -> PostProcessStage
```

`SegmentStage` currently chunks with:

```python
context.chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
```

That means segmentation is paragraph-split only. It does not create `paragraph_id`, `chunk_id`, chapter lineage, chunk budget targets around 4,500 Japanese characters, temporary bundle records, chunk metadata, placeholder/image preservation state, or retryable chunk records.

Provider calls happen in:

- `backend/src/novelai/translation/pipeline/stages/translate.py`, through `provider.translate(...)` for body chunks.
- `backend/src/novelai/services/orchestration/translation.py`, through `_translate_text(...)` for metadata/glossary-adjacent translation.
- `backend/src/novelai/api/routers/admin.py`, through provider validation in the admin API key routes.

Prompt construction mostly lives under `backend/src/novelai/prompts/*`:

- `prompts/builders.py`
- `prompts/models.py`
- `prompts/responses_api.py`
- `prompts/templates.py`

Known prompt leaks:

- `backend/src/novelai/services/orchestration/translation.py` builds metadata translation prompt strings in `_metadata_translation_prompt`.
- `TranslateStage._build_prompt_request` prepares prompt inputs in the stage but delegates actual body prompt construction to `build_translation_request`.
- `OpenAIProvider._build_payload` adds a fallback system prompt for raw prompt calls. This is provider payload construction, but should be watched so prompt wording does not drift into providers.

Provider errors are partially structured at the API boundary but not normalized at the provider boundary:

- `backend/src/novelai/core/errors.py` has generic `ProviderError`, `ProviderConfigError`, and `ProviderAPIError`.
- `backend/src/novelai/providers/errors.py` does not exist.
- `GeminiProvider` and `OpenAIProvider` raise generic `ProviderError` only for missing config/package cases; SDK/API failures usually bubble as raw exceptions.
- `TranslateStage` catches broad exceptions for model fallback and re-raises the last raw exception.
- `api/error_handlers.py` maps broad provider/core errors to envelopes, but it cannot distinguish rate limit, quota exhaustion, invalid model, safety block, invalid JSON, timeout, empty output, context too large, or retry-after.

Source ingestion map:

- Source registry: `backend/src/novelai/sources/registry.py`
- Source base contract/retry/throttle/url validation: `backend/src/novelai/sources/base.py`
- Source adapters: `syosetu_ncode.py`, `novel18_syosetu.py`, `kakuyomu.py`, `generic.py`
- Shared HTML helpers: `html_parsers.py`, `_helpers.py`
- HTTP client helper: `backend/src/novelai/utils/http_client.py`
- Crawler orchestration: `backend/src/novelai/services/orchestration/crawler.py`

Adapters create per-request `httpx.AsyncClient` instances through `novelai.utils.http_client.create_async_client`. Retry and throttle live on `SourceAdapter` in `sources/base.py`; URL validation also lives there. There is no `backend/src/novelai/infrastructure/http/*` FetchService, fetch cache, source fetch error model, conditional response cache, or central per-domain fetch coordinator.

Storage/activity map:

- Final translated output: chapter bundle JSON via `backend/src/novelai/storage/translations.py`
- Chapter state/checkpoints: `backend/src/novelai/storage/jobs.py`
- Activity/job queue: `backend/src/novelai/activity/queue.py`
- Activity worker/runner: `backend/src/novelai/activity/worker.py`, `runner.py`
- Translation cache: `backend/src/novelai/services/translation_cache.py`
- Usage log: `backend/src/novelai/services/usage_service.py`
- Request queue: `backend/src/novelai/services/novel_request_service.py`

Partial progress is chapter-level only. The workflow creates `before_translate`, `translated`, and `failed` checkpoints and marks chapter state as `segmented` or `translated`, but successful chunks are not persisted independently. Failed chunks cannot be retried without retranslating the chapter.

Credential/auth readiness map:

- Auth is a single optional bearer token in `api/routers/dependencies.py` via `WEB_API_KEY`.
- Provider keys come from environment-backed settings or in-memory runtime `SecretStr` values in `PreferencesService`.
- Admin settings routes accept raw provider API keys and store them in process memory via `PreferencesService.set_api_key`.
- Preferences explicitly avoid persisting API keys to disk.
- There is no credential storage module, encryption-at-rest layer, user ownership model, admin role model, or credential audit log.
- Raw provider secrets are not returned by status endpoints, but raw keys are accepted from frontend settings forms and live in browser-local UI state while being submitted.

## Highest-Risk Architecture Violations

1. Smart segmentation is missing.
   `backend/src/novelai/translation/pipeline/stages/segment.py` produces `list[str]` chunks by double-newline split only. This violates the architecture's immediate Priority 1 requirements.

2. Provider errors are not normalized.
   There is no `backend/src/novelai/providers/errors.py`, no canonical provider error code model, no retry-after handling, and no chunk/job-level provider error code persistence.

3. Pipeline state is not traceable enough.
   `PipelineState` has `chapter_url`, `provider_key`, `provider_model`, raw/normalized text, chunks, translations, final text, and metadata. It does not model `novel_id`, `chapter_id`, `source_key`, `activity_id` / `job_id`, `paragraph_id`, `chunk_id`, stage transitions, warnings, structured errors, credential/request trace fields, or per-chunk provider/model records.

4. Partial progress is not persistable or retryable.
   Storage saves final active translation versions after success. Chapter checkpoints help resume around whole-chapter work, but not around individual successful/failed chunks.

5. Source adapters mix fetching and parsing.
   `syosetu_ncode.py`, `novel18_syosetu.py`, `kakuyomu.py`, and `generic.py` each contain HTTP fetch methods, source selectors, parsing methods, source-specific validation, and asset download logic.

6. HTTP fetching is not in `infrastructure/http`.
   Retry/throttle/url validation are in `sources/base.py`, client creation is in `utils/http_client.py`, and source adapters call the client directly. This is close to useful shared code, but still not the target FetchService boundary.

7. Routers are not consistently thin.
   `operations.py` contains preliminary crawl source fallback, activity success/failure recording, export assembly, timeout handling, and source-health mutation. `admin.py` contains provider default/model validation and API key application logic.

8. Prompt construction leaks outside `prompts/*`.
   Metadata prompt construction is currently in `services/orchestration/translation.py`.

9. Naming is inconsistent with the canonical contract.
   Examples:
   - `ActivityQueueService.create_translation_activity` stores `provider` and `model`, not `provider_key` and `provider_model`.
   - `frontend/lib/api.ts` uses `provider`, `model`, `source`, and generic `id` in several stable types.
   - `library.py` exposes `NovelSummary.source` and `ChapterSummary.id`.
   - Request records use generic `id` for `request_id`.
   - Activity records use generic `id` for `activity_id` / `job_id`.
   - Translated chapter storage uses `provider` and `model` in translation versions.

10. Public contribution mode is not architecturally ready.
    The current app has an admin token, not authenticated registered users; no owner_admin role boundary; no encrypted credential persistence; no credential owner IDs; no revocation/deletion workflow; no audit log for credential lifecycle; and no usage limits for contributed credentials.

## Files Likely To Change In Phase 1

Phase 1 should focus on the architecture's Priority 1-5 core pipeline reliability work.

- `backend/src/novelai/translation/pipeline/stages/segment.py`
- `backend/src/novelai/translation/pipeline/context.py`
- `backend/src/novelai/translation/pipeline/stages/translate.py`
- `backend/src/novelai/translation/pipeline/stages/post_process.py`
- `backend/src/novelai/translation/qa.py` (new)
- `backend/src/novelai/translation/pipeline/stages/translation_qa.py` (new)
- `backend/src/novelai/providers/errors.py` (new)
- `backend/src/novelai/providers/base.py`
- `backend/src/novelai/providers/gemini_provider.py`
- `backend/src/novelai/providers/openai_provider.py`
- `backend/src/novelai/providers/model_fallbacks.py`
- `backend/src/novelai/api/error_handlers.py`
- `backend/src/novelai/activity/queue.py`
- `backend/src/novelai/activity/worker.py`
- `backend/src/novelai/core/chapter_state.py`
- `backend/src/novelai/storage/jobs.py`
- `backend/src/novelai/storage/translations.py`
- `backend/src/novelai/storage/service.py`
- `backend/src/novelai/services/orchestration/translation.py`
- `backend/src/novelai/prompts/builders.py`
- `backend/src/novelai/prompts/models.py`
- `backend/src/novelai/prompts/templates.py`
- `backend/tests/test_pipeline_stages.py`
- `backend/tests/test_gemini_provider.py`
- `backend/tests/test_openai_provider.py`
- `backend/tests/test_job_worker_service.py`
- `backend/tests/test_job_queue_service.py`
- `backend/tests/test_web_api.py`
- `backend/tests/test_translation_cache.py`
- `docs/reference/DATA_OUTPUT_STRUCTURE.md`

## Files Likely To Change In Phase 2

Phase 2 should focus on source ingestion boundaries, FetchService, source quality gates, parser fixtures, and API/frontend schema cleanup.

- `backend/src/novelai/infrastructure/http/client.py` (new)
- `backend/src/novelai/infrastructure/http/fetch_service.py` (new)
- `backend/src/novelai/infrastructure/http/throttle.py` (new)
- `backend/src/novelai/infrastructure/http/cache.py` (new)
- `backend/src/novelai/infrastructure/http/errors.py` (new)
- `backend/src/novelai/sources/base.py`
- `backend/src/novelai/sources/syosetu_ncode.py`
- `backend/src/novelai/sources/novel18_syosetu.py`
- `backend/src/novelai/sources/kakuyomu.py`
- `backend/src/novelai/sources/generic.py`
- `backend/src/novelai/sources/quality.py` (new)
- `backend/src/novelai/services/orchestration/crawler.py`
- `backend/src/novelai/services/novel_orchestration_service.py`
- `backend/src/novelai/api/routers/operations.py`
- `backend/src/novelai/api/routers/activity.py`
- `backend/src/novelai/api/routers/library.py`
- `backend/src/novelai/api/routers/admin.py`
- `frontend/lib/api.ts`
- `backend/tests/test_syosetu_source.py`
- `backend/tests/test_novel18_source.py`
- `backend/tests/test_kakuyomu_source.py`
- `backend/tests/test_generic_source.py`
- `backend/tests/test_source_registry.py`
- `backend/tests/test_source_helpers.py`
- `backend/tests/test_web_api.py`

## Do Not Touch Yet

- Do not add database support.
- Do not add billing, organizations, multi-admin teams, or distributed workers.
- Do not add new source sites before FetchService, quality gates, and parser fixture tests are stable.
- Do not add batch translation before smart segmentation, provider errors, chunk persistence, and QA are reliable.
- Do not implement a multi-model scheduler until provider errors and pipeline traceability are stable.
- Do not broadly rewrite frontend UI before backend/API naming and error contracts settle.
- Do not migrate runtime storage formats broadly without compatibility readers and tests.
- Do not expose runtime storage directly through frontend/static hosting.
- Do not accept raw filesystem paths from the frontend.
- Do not move source selectors outside `sources/*`.
- Do not move prompt wording into providers, routers, or frontend code.

Public user contributed credentials are not ready.

Do not implement public user contributed credentials unless the project already has or explicitly introduces:

- authenticated public users
- admin role separation
- encrypted credential storage
- revocation/deletion flows
- audit logging
- contribution consent and usage limits

Current state:

- No public account/authentication system exists.
- No `registered_user` or `owner_admin` role model exists.
- Admin protection is a shared optional bearer token only.
- Provider credentials are global/admin runtime keys, not user-owned credentials.
- Provider keys are held in environment-backed settings or in-memory `SecretStr` values, not encrypted storage.
- No raw provider key is returned by the current status endpoints.
- The frontend settings page can hold raw API tokens in browser state/local store and submit them to admin endpoints.
- No credential owner, contribution scope, consent, usage limit, revocation, deletion, or security audit schema exists.
- Public contribution mode would be a product-boundary change, not a settings-page enhancement.

## Recommended Implementation Order

1. Add a normalized provider error model in `providers/errors.py` and map it through API errors and activity/job metadata.
2. Replace `SegmentStage` with smart paragraph/chunk contracts including `paragraph_id`, `chunk_id`, chapter lineage, budgets, and placeholder/image preservation.
3. Extend pipeline state with `novel_id`, `chapter_id`, `source_key`, `activity_id` / `job_id`, stage names, warnings, structured errors, and per-chunk provider/model traces.
4. Persist chunk-level state and outputs behind `storage/*`, including failed chunk retry metadata.
5. Add deterministic translation QA before final save.
6. Move metadata prompt construction into `prompts/*`.
7. Normalize activity/storage/API naming toward `provider_key`, `provider_model`, `activity_id` / `job_id`, `chapter_id`, and `source_key`, keeping short compatibility aliases only during migration.
8. Move source HTTP fetching into `infrastructure/http/FetchService`.
9. Split source fetching from parsing and add source quality gates.
10. Add offline parser fixture tests and API/schema contract tests.
11. Run a final core integration audit before scheduler work.
12. Only after auth/role/security foundations exist, design public request approval and contributed credential workflows.

## Final Implementation Pass

This section records the post-implementation integration audit. Earlier sections preserve the original Prompt 0 audit context and may describe pre-implementation gaps that have since been partially or fully addressed.

### Completed

- Translation segmentation now has typed `Paragraph` and `TranslationChunk` contracts, deterministic paragraph/chunk IDs, budget-aware chunk packing, explicit `[CHAPTER ...]` and `[P ...]` markers, and backward-compatible `SegmentStage` aliasing.
- Translation traceability now carries `novel_id`, `chapter_id`, `source_key`, `provider_key`, `provider_model`, `activity_id` / `job_id`, `chunk_id`, paragraph IDs, stage events, chunk states, and scheduler-state foundation fields.
- Provider errors are normalized through `ProviderErrorCode` / `ProviderError` and mapped by `api/error_handlers.py` into the shared frontend-readable envelope.
- Gemini and OpenAI provider tests cover rate limits, quota exhaustion, invalid/unavailable models, context limits, safety/refusal, timeout, empty output, partial output, invalid JSON, unknown provider errors, and success paths.
- Deterministic `TranslationQAStage` exists in `translation/*`; QA prevents failed outputs from being saved as clean final text and checks placeholders, obvious refusal/error text, suspicious truncation/summary output, and paragraph/chapter mapping where structured data exists.
- Metadata prompt construction has been moved from orchestration into `backend/src/novelai/prompts/metadata.py`; orchestration now imports `build_metadata_translation_prompt`.
- Central HTTP fetching exists under `backend/src/novelai/infrastructure/http/*`; Syosetu/Novel18 uses `FetchService`, shared throttling, URL validation, and conditional-cache interfaces.
- Source quality gates exist, including metadata/chapter checks, adult-source age-gate classification, generic confidence scoring, and offline parser fixture tests.
- Storage contracts now document and support runtime traceability, chunk records, temporary bundles, chunk outputs, provider request record shapes, scheduler state, fetch cache entries, and exact translation cache keys.
- `docs/reference/DATA_OUTPUT_STRUCTURE.md` documents implemented runtime shapes, owner modules, schema versions, retention behavior, and backward-compatibility notes.
- API error responses preserve the shared envelope fields: `code`, `message`, `explanation`, `details`, optional `trace_id`, plus legacy `detail` / `error` compatibility fields.
- Activity/job API responses expose canonical compatibility fields such as `activity_id`, `job_id`, `provider_key`, `provider_model`, `current_stage`, `current_label`, `completed`, `total`, `errors`, `warnings`, `paused_reason`, `resume_after`, and `model_states`.
- Frontend API calls remain centralized in `frontend/lib/api.ts`; frontend activity pages display structured job progress and warning/error counts without implementing backend scheduling or QA logic.
- CLI worker compatibility was restored so older `job_runner` aliases and user-facing “job” wording still work while the runtime uses `activity_runner`.

### Remaining Debt

- The full multi-model scheduler is not implemented. Model fallback exists, but scheduler policy for selecting the next model, pausing all-cooldown jobs, daily quota reset handling, and resumable routing belongs to Prompt 11.
- Public contribution credentials are not implemented. The project still lacks authenticated public users, admin role separation, encrypted credential storage, credential owner IDs, revocation/deletion flows, contribution consent, usage limits, and credential audit logging.
- Provider request record persistence is available in storage, but provider calls are not yet consistently recorded for every successful/failed request across all translation and metadata paths.
- Temporary bundle persistence exists as a storage foundation, but bundle lifecycle integration is still limited; temporary bundles should remain retry/debug artifacts and must not become canonical chapter output.
- Some source adapters still own direct HTTP client calls or inherited source-base fetch behavior. Syosetu/Novel18 is integrated with `FetchService`; Kakuyomu and Generic should move gradually in a later source-boundary pass.
- `operations.py` and `admin.py` remain thicker than ideal. They contain preliminary-crawl fallback orchestration, export assembly, provider key validation/application, and runtime-state handling. These should be split only during focused service-boundary work.
- Activity/job storage still stores legacy `id`, `provider`, and `model` fields for backward compatibility. API responses expose canonical aliases, but persisted schema migration should wait for a compatibility plan.
- Chapter and translation version payloads still expose legacy `source`, `provider`, `model`, and generic `id` fields in some places. These are stable UI/storage contracts and should not be renamed destructively.
- `backend/src/novelai/utils/http_client.py` remains for legacy/shared callers while the new `infrastructure/http` layer is adopted incrementally.
- Existing full frontend lint script uses deprecated `next lint` and prompts interactively because no ESLint config is committed.

### Risky Areas

- Provider quota handling: normalized errors and model-state shapes exist, but without Prompt 11 routing a long job can still stop instead of waiting/resuming intelligently.
- Multi-model fallback: fallback must continue to preserve glossary selection, prompt versioning, exact cache keys, QA, chunk state, and provider/model trace metadata.
- Cache correctness: exact cache-key helpers exist and tests cover key drift, but every translation path must continue passing prompt-affecting metadata into cache keys.
- Temporary bundle splitting: multi-chapter bundles require structured output or safe paragraph maps; unsafe plain-text multi-chapter output must remain `qa_failed` or `needs_review`.
- Source parser drift: fixture tests protect current selectors, but live source HTML can still change; quality gates should record structured warnings/errors rather than silently forwarding bad text.
- Storage backward compatibility: runtime records are additive, but persisted legacy chapter bundles and activity records need compatibility readers until a migration plan exists.
- API naming migration: frontend and storage still carry compatibility aliases. Removing `id`, `provider`, `model`, or `source` too early would break existing callers.

### Test Results

- `pytest backend/tests/test_pipeline_stages.py backend/tests/test_integration.py backend/tests/test_translation_qa.py backend/tests/test_gemini_provider.py backend/tests/test_openai_provider.py backend/tests/test_storage_contracts.py backend/tests/test_translation_cache.py backend/tests/test_source_quality.py backend/tests/test_fetch_service.py backend/tests/test_source_parser_fixtures.py backend/tests/test_web_api.py backend/tests/test_frontend_api_contract.py -q`
  - Result: `194 passed`.
- `pytest backend/tests -q`
  - Initial result: `1 failed, 499 passed, 7 skipped`; failure was a CLI `job_runner` compatibility regression.
  - After cleanup: `500 passed, 7 skipped`.
- `pyright`
  - Initial result: failed on the moved metadata prompt constant reference.
  - After cleanup: `0 errors, 0 warnings, 0 informations`.
- `npm run typecheck`
  - Result: passed.
- `npm run build`
  - Result: passed.
- `npm run lint`
  - Result: could not complete as a non-interactive verification. After an unsandboxed retry, `next lint` started deprecated interactive ESLint configuration setup because the frontend has no committed ESLint config.

### Recommended Next Phase

The next implementation phase should be Prompt 11: implement the multi-model scheduler using the existing `ProviderError`, chunk state, scheduler state, cache-key, QA, and activity/job progress contracts. Do not implement public contribution credentials until the project first adds authenticated users, admin role separation, encrypted credential storage, revocation/deletion flows, audit logging, contribution consent, and usage limits.
