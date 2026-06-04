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
