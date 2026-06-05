# Archived Architecture Note

This historical document was consolidated into `docs/architecture/architecture.md`. It may contain stale implementation status and should not be used as current architecture guidance.

# Prompt 1-10 Implementation Summary

## Executive Summary

Prompts 1-10 completed the core reliability pass described by `docs/architecture/architecture.md`: smart translation segmentation, normalized provider errors, traceable pipeline/job state, deterministic translation QA, central fetch infrastructure, source quality gates, offline parser fixtures, storage/cache contracts, API/frontend error contract cleanup, and a final integration audit.

The implementation remains intentionally pre-scheduler and pre-public-contribution. No Prompt 11 multi-model scheduler routing, Prompt 12 public contribution credentials, Prompt 13 security hardening, public auth/user system, database support, or batch mode was implemented during Prompts 1-10.

Current storage remains file-backed and chapter-based. Translation preparation can use chunks and temporary bundles, but canonical translated output remains per chapter. Runtime data under `storage/` is untracked and must not be committed.

## Prompt-by-Prompt Summary

### Prompt 1 SmartSegmentStage

Implemented typed paragraph and chunk contracts in `backend/src/novelai/translation/pipeline/context.py` and budget-aware segmentation in `backend/src/novelai/translation/pipeline/stages/segment.py`.

Key outcomes:

- Added `Paragraph` with deterministic `paragraph_id` values such as `p0001`.
- Added `TranslationChunk` with deterministic `chunk_id` values such as `c0001`.
- Preserved `novel_id`, `chapter_ids`, `paragraph_ids`, `chunk_id`, `source_text`, and character counts.
- Replaced paragraph-only splitting with `SmartSegmentStage`.
- Kept `SegmentStage` as a compatibility alias.
- Preserved backward compatibility for existing `chunks: list[str]` consumers while exposing typed chunk metadata.
- Added stable source markers such as `[CHAPTER chapter_001]` and `[P p0001]`.
- Added tests for deterministic IDs, chunk packing, short chapters, multi-chapter bundles, long chapters, oversized paragraphs, image placeholders, scene breaks, chapter markers, and paragraph order.

Remaining debt:

- Temporary bundle persistence and retry lifecycle are storage foundations only; full scheduler-driven retry belongs later.

### Prompt 2 Provider Error Classification

Implemented normalized provider error classification using `ProviderErrorCode` and `ProviderError` in `backend/src/novelai/core/errors.py`, with provider-specific parsing in `backend/src/novelai/providers/*` and API mapping in `backend/src/novelai/api/error_handlers.py`.

Key outcomes:

- Normalized rate limit, quota exhaustion, model unavailable/deprecated, context too large, safety block, timeout, invalid JSON, empty output, partial output, and unknown provider failures.
- Preserved `provider_key`, `provider_model`, `provider_error_code`, `retry_after_seconds`, `cooldown_until`, `exhausted_until`, and safe public details.
- Updated Gemini and OpenAI providers to raise normalized `ProviderError` values.
- Mapped known provider failures into the shared API error envelope instead of anonymous generic 500s.
- Added provider and API tests for known failure cases and success paths.

Remaining debt:

- Full provider/model routing behavior is not implemented. The scheduler will use these normalized errors later.
- Provider request records exist in storage contracts, but not every provider call path records a request yet.

### Prompt 3 Pipeline and Job Traceability

Introduced traceability contracts in `backend/src/novelai/shared/pipeline.py` and extended the translation pipeline state in `backend/src/novelai/translation/pipeline/context.py` without abruptly breaking `PipelineState` compatibility.

Key outcomes:

- Added or preserved `PipelineContext` / `PipelineStep` contracts.
- Added stage events with stage name, status before/after, warnings, errors, provider metadata, timestamps, and job/activity identity.
- Made `translated_partial` representable.
- Added chunk state and chunk attempt traceability fields.
- Added scheduler state foundations for provider/model status values: `available`, `cooling_down`, `daily_exhausted`, `disabled`, and `failed`.
- Ensured failed stage names are persisted accurately after the follow-up fix in `services/orchestration/translation.py`.
- Added tests for stage transitions, failed stage recording, partial status, chunk status, provider/model traceability, and job/activity compatibility.

Remaining debt:

- Scheduler state is representational only. Prompt 11 must implement routing, pause/resume policy, and successful-chunk reuse rules.

### Prompt 4 Translation QA

Added deterministic translation QA under `backend/src/novelai/translation/*`, primarily `backend/src/novelai/translation/qa.py` and `backend/src/novelai/translation/pipeline/stages/translation_qa.py`.

Key outcomes:

- Added `TranslationQAResult`.
- Checked empty output, identical source/target, suspicious length ratios, placeholders, image placeholders, scene breaks, provider error/refusal text, probable summaries, probable truncation, and paragraph/chapter mapping when available.
- Inserted QA after translation and before post-processing/final save.
- Prevented failed QA output from being saved as final translated text.
- Supported plain-text compatibility for safe single-chapter output while treating unsafe multi-chapter output without mapping as `qa_failed` or `needs_review`.
- Added tests for valid output, empty output, identical output, missing placeholders, missing/duplicate/unexpected paragraph IDs, order mismatch, multi-chapter mapping, unsafe multi-chapter plain text, refusal text, and QA state/event behavior.

Remaining debt:

- No model-based polishing was added.
- Selective retry is not implemented beyond the existing status foundations.

### Prompt 5 Central FetchService

Added shared source HTTP infrastructure under `backend/src/novelai/infrastructure/http/`.

Key outcomes:

- Added shared async HTTP client factory in `client.py`.
- Added `FetchResult` and `FetchService` in `fetch_service.py`.
- Added per-domain throttling in `throttle.py`.
- Added fetch cache support in `cache.py`.
- Preserved URL safety validation.
- Integrated the highest-risk Syosetu/Novel18 path with `FetchService`.
- Added tests for successful fetches, URL rejection, throttle calls, cache behavior, and adapter integration.

Remaining debt:

- Kakuyomu and Generic still need a gradual move away from legacy direct/inherited HTTP behavior.

### Prompt 6 Source Quality Gates

Added source quality validation in `backend/src/novelai/sources/quality.py` and integrated quality warnings/errors into ingestion paths.

Key outcomes:

- Added `QualityGateResult`.
- Added metadata checks for title, source URL, source key, novel/source IDs, chapter count, duplicate chapter URLs, and sane order.
- Added chapter checks for empty text, short text, navigation/menu boilerplate, block/error pages, age gates, image placeholder consistency, and Japanese-ratio sanity.
- Added Novel18/Syosetu age-gate/block-page classification.
- Added Generic confidence scoring with positive and negative link signals.
- Added tests for empty chapters, nav-heavy text, age gates, generic low-confidence pages, duplicate chapter URLs, and valid dedicated-source imports.

Remaining debt:

- Source-specific quality rules can be expanded as fixture coverage and real-world parser drift reveal gaps.

### Prompt 7 Parser Fixture Tests

Added offline parser fixtures and source parser tests under `backend/tests/fixtures/sources/*` and `backend/tests/test_source_parser_fixtures.py`.

Key outcomes:

- Added Syosetu fixtures for ongoing/completed metadata, preface/body/afterword, ruby, images, and paginated TOC pages.
- Added Kakuyomu fixtures for work and episode pages, separators, and images.
- Added Generic fixtures for valid TOC, navigation-heavy pages, and low-confidence pages.
- Covered URL matching, ID normalization/extraction, metadata parsing, chapter ordering, body extraction, placeholder preservation, confidence scoring, duplicate normalization, and no-network behavior.

Remaining debt:

- Fixtures are representative, not exhaustive. More real-world fixture snapshots should be added when source parsers drift.

### Prompt 8 Storage and Cache Contracts

Documented and implemented storage/runtime foundations in `backend/src/novelai/storage/*`, `backend/src/novelai/services/translation_cache.py`, and `docs/reference/DATA_OUTPUT_STRUCTURE.md`.

Key outcomes:

- Documented runtime shapes for novels, chapters, raw/parsed/final chapter data, chunks, temporary bundles, outputs, provider requests, jobs, job events, scheduler state, fetch cache, and translation cache.
- Added runtime contract helpers in `backend/src/novelai/storage/runtime_contracts.py`.
- Added traceability storage helpers in `backend/src/novelai/storage/traceability.py`.
- Added storage service APIs for translation chunks, bundle records, output records, provider request records, scheduler state, and fetch cache entries.
- Added exact translation cache keys that include prompt-affecting and model-affecting metadata such as `provider_key`, `provider_model`, `prompt_version`, glossary hash, style preset, JSON output mode, and consistency mode.
- Added tests for storage shapes, chunk status persistence, provider/model recording, provider error persistence, provider request persistence, fetch cache read/write, scheduler state serialization, bundle deletion safety, and cache-key drift.

Remaining debt:

- Storage foundations are present, but not every runtime path records provider requests, chunk outputs, or bundle lifecycle details yet.
- No credential storage was implemented. Public contribution credentials remain deferred.

### Prompt 9 API/Frontend Contract

Aligned backend API error handling and frontend API consumption through `backend/src/novelai/api/*` and `frontend/lib/api.ts`.

Key outcomes:

- Added or tightened API response models in `backend/src/novelai/api/models.py`.
- Updated `backend/src/novelai/api/error_handlers.py` so known errors return the shared envelope with `code`, `message`, `explanation`, `details`, optional `trace_id`, and legacy compatibility fields where needed.
- Normalized activity/job responses in `backend/src/novelai/api/routers/activity.py`.
- Added frontend error parsing, activity/job progress helpers, and typed API shapes in `frontend/lib/api.ts`.
- Ensured frontend activity pages consume structured progress and error fields without implementing backend scheduling or QA logic.
- Added tests for API error envelopes, no raw tracebacks, frontend API path centralization, frontend error parsing, and job progress payload shape.

Deferred by scope:

- Public-user and admin credential management routes/pages were not implemented because public contribution credentials remain Prompt 12 work and require real auth, roles, encrypted credential storage, revocation, audit logging, consent, and limits.

Remaining debt:

- Some API/storage contracts still expose compatibility aliases such as `id`, `source`, `provider`, and `model`.
- `operations.py` and `admin.py` remain thicker than ideal and should be split only during focused service-boundary work.

### Prompt 10 Final Integration Audit

Ran the final integration audit and performed only small safe cleanup.

Key outcomes:

- Updated the historical implementation audit now archived at `docs/archive/architecture/IMPLEMENTATION_AUDIT.md` with the `## Final Implementation Pass` section.
- Moved metadata prompt construction into `backend/src/novelai/prompts/metadata.py`.
- Updated orchestration to import `build_metadata_translation_prompt` from `novelai.prompts`.
- Restored CLI worker compatibility for older `job_runner` naming while preserving the newer activity runner.
- Verified backend, frontend build/typecheck, provider, translation, storage, source, and API tests.

Remaining debt:

- `npm run lint` cannot complete non-interactively because `next lint` prompts for ESLint configuration.
- The full scheduler, public credentials, and security hardening phases remain explicitly unimplemented.

## Test Results

Recorded final verification from Prompt 10:

- `pytest backend/tests/test_pipeline_stages.py backend/tests/test_integration.py backend/tests/test_translation_qa.py backend/tests/test_gemini_provider.py backend/tests/test_openai_provider.py backend/tests/test_storage_contracts.py backend/tests/test_translation_cache.py backend/tests/test_source_quality.py backend/tests/test_fetch_service.py backend/tests/test_source_parser_fixtures.py backend/tests/test_web_api.py backend/tests/test_frontend_api_contract.py -q`
  - Result: `194 passed`.
- `pytest backend/tests -q`
  - Initial result: `1 failed, 499 passed, 7 skipped`.
  - The failure was a CLI `job_runner` compatibility regression.
  - After cleanup: `500 passed, 7 skipped`.
- `pyright`
  - Initial result: failed on the moved metadata prompt constant reference.
  - After cleanup: `0 errors, 0 warnings, 0 informations`.
- `npm run typecheck`
  - Result: passed.
- `npm run build`
  - Result: passed.
- `npm run lint`
  - Result: could not complete as a non-interactive verification. `next lint` started deprecated interactive ESLint configuration setup because the frontend has no committed ESLint config.

These results are documented in the historical audit now archived at `docs/archive/architecture/IMPLEMENTATION_AUDIT.md`.

## Historical Architecture State

Inspected state at the time:

- Recent commits show one implementation commit per major prompt from Prompt 1 through Prompt 10.
- `backend/src/novelai/translation/` contains SmartSegmentStage, typed pipeline context, TranslateStage compatibility, TranslationQAStage, and deterministic QA helpers.
- `backend/src/novelai/providers/` contains provider-specific Gemini and OpenAI normalization logic. The canonical provider error model currently lives in `backend/src/novelai/core/errors.py`.
- `backend/src/novelai/storage/` owns runtime persistence contracts, traceability storage, chapter storage, translations, jobs, fetch cache records, provider request records, and scheduler state foundations.
- `backend/src/novelai/infrastructure/http/` contains the shared fetch client, fetch service, throttle, and cache foundation.
- `backend/src/novelai/sources/` contains source-specific selectors and parsers plus quality gates.
- `backend/src/novelai/api/` maps structured errors and exposes typed activity/job responses.
- `frontend/lib/api.ts` remains the frontend API boundary and contains centralized error parsing and activity/job progress helpers.
- `docs/reference/DATA_OUTPUT_STRUCTURE.md` documents current runtime shapes and explicitly states that public user-contributed credential storage is not implemented.

Current worktree safety note:

- `git status --short` shows untracked runtime `storage/` data. This data must remain untracked and must not be committed.
- The current inspection also shows prompt metadata files in the working tree. Do not use this summary as a commit manifest; review `git status` before committing.

## Remaining Debt

### High Priority

- Implement Prompt 11 multi-model scheduler routing using the existing provider error, chunk state, scheduler state, cache key, QA, and activity/job contracts.
- Ensure model cooldown and daily quota exhaustion pause/resume jobs without losing chunk progress or retranslating successful chunks.
- Record provider request records consistently for all successful and failed provider calls, including metadata translation paths.
- Complete safe multi-chapter structured-output handling so temporary bundles never require fragile text-boundary guessing.
- Keep public contribution credentials deferred until real authenticated users, owner/admin authorization, encrypted credential storage, revocation/deletion flows, audit logging, contribution consent, and usage limits exist.

### Medium Priority

- Continue moving source adapters from legacy direct/inherited HTTP behavior to `FetchService`, especially Kakuyomu and Generic.
- Thin `operations.py` and `admin.py` by moving remaining orchestration into services.
- Reduce persisted/API naming debt around compatibility fields such as `id`, `source`, `provider`, and `model` without breaking existing callers.
- Expand parser fixture coverage as source HTML changes.
- Add non-interactive frontend lint configuration or replace deprecated `next lint` usage with a stable lint command.
- Strengthen storage backward-compatibility tests for older runtime chapter bundles and activity/job records.

### Low Priority

- Add more source-specific quality reason codes as real parse failures are observed.
- Add more documentation examples for chunk output and provider request records.
- Consider generated TypeScript types from FastAPI OpenAPI once API shapes stabilize.
- Remove legacy compatibility aliases only after a planned migration and test coverage.

## Historical Recommended Next Phase (Superseded)

At the time, the recommended next phase was Prompt 11: implement the multi-model scheduler. Use `docs/architecture/architecture.md` for current guidance.

Prompt 11 should build on the contracts already in place:

- `ProviderErrorCode` / `ProviderError`
- chunk state and chunk attempts
- scheduler model state
- provider/model identity per chunk where available
- exact translation cache keys
- deterministic QA before final save
- activity/job progress fields
- storage-backed traceability

Prompt 11 should not bypass glossary handling, prompt versioning, QA, cache-key rules, provider request recording, chunk status tracking, or chapter-based final storage.

Prompt 12 public contribution credentials should remain deferred until the product boundary includes authenticated users, owner/admin role separation, encrypted credential storage, revocation/deletion flows, audit logging, contribution consent, object-level authorization, and usage limits.

## Safety Notes

- No Prompt 11 scheduler routing was implemented during Prompts 1-10.
- No Prompt 12 public contribution credential flow was implemented during Prompts 1-10.
- No Prompt 13 security hardening phase was implemented during Prompts 1-10.
- No public auth/user system was added.
- No database support was added.
- No batch mode was added.
- Public contribution credentials remain deferred.
- Storage/runtime data remains untracked and must not be committed.
- Raw API keys, provider secrets, request headers, cookies, and raw tracebacks must not be added to docs, tests, runtime records, API responses, or logs.
- Final translated output remains chapter-based; temporary chunks and bundles are runtime/cache/retry artifacts, not canonical chapter storage.
