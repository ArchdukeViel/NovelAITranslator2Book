# Archived Architecture Note

This historical document was consolidated into `docs/architecture/architecture.md`. It may contain stale implementation status and should not be used as current architecture guidance.

# Scheduler Readiness

## Verdict

Ready.

Prompt 11 can begin because the hard prerequisites are present: typed chunk identity, provider error classification, exact cache-key foundations, QA before final save, activity/job progress shape, and serializable scheduler state. This is not a claim that scheduler behavior is implemented. The main remaining work is to wire the existing storage hooks into the runtime scheduler path so provider requests, chunk attempts, and chunk outputs are persisted consistently as routing decisions happen.

## Confirmed Prerequisites

- Typed chunk identity exists in `backend/src/novelai/translation/pipeline/context.py` through `TranslationChunk`, with `chunk_id`, `novel_id`, `chapter_ids`, `paragraph_ids`, `source_text`, `char_count`, and `paragraph_refs`.
- Paragraph identity exists in `Paragraph`, and `SmartSegmentStage` assigns deterministic paragraph IDs while preserving chapter boundaries and stable `[CHAPTER ...]` / `[P ...]` markers.
- `PipelineState` remains backward compatible with `chunks: list[str]` while also exposing `translation_chunks`, `paragraphs`, `chunk_states`, `pipeline_events`, and `scheduler_state`.
- `TranslateStage` accepts typed chunks, preserves `chunk_id`, records provider/model identity in in-memory chunk state, and still passes `chunk.source_text` to existing provider implementations.
- Provider failures are normalized through `ProviderError` and `ProviderErrorCode` in `backend/src/novelai/core/errors.py`, with Gemini and OpenAI providers classifying rate limits, quota exhaustion, unavailable models, context limits, safety blocks, timeouts, invalid JSON, empty output, partial output, and unknown failures.
- Translation QA is wired after `TranslateStage` and before `PostProcessStage` in `TranslationService`; failed QA raises before final chapter save in the orchestration path.
- QA supports deterministic plain-text checks and structured paragraph-map validation, including unsafe multi-chapter plain-text rejection.
- Exact translation cache foundations exist in `backend/src/novelai/services/translation_cache.py`; keys can include provider/model and prompt-affecting metadata. The active body translation path uses prompt request content plus provider/model in the cache layer.
- Activity/job API payloads can represent `status`, `current_stage`, `current_label`, `completed`, `total`, `errors`, `warnings`, `paused_reason`, `resume_after`, and `model_states`.
- Scheduler model state contracts exist through `SchedulerModelState` and `SchedulerModelStatus`, and storage can serialize scheduler state under `runtime/traceability/scheduler_states.json`.
- Storage contracts exist for pipeline events, chunk states, translation chunks, temporary bundles, translation outputs, provider request records, scheduler state, fetch cache entries, and exact translation cache behavior.

## Missing Prerequisites

No hard-gate prerequisite from this audit is missing.

Remaining implementation prerequisites for Prompt 11 itself:

- Runtime scheduler selection/routing is not implemented.
- Pause/resume semantics are not implemented.
- Successful chunks are not yet skipped by a scheduler-managed persisted chunk-output/attempt ledger.
- Provider request records exist as storage hooks, but the primary runtime provider-call paths do not consistently write them.
- Chunk output persistence exists as a storage hook, but the primary runtime translation path still mainly stores translated chunk text in memory and final output per chapter.

## Runtime Paths That Still Do Not Record Provider Requests

- `TranslateStage` provider calls in `backend/src/novelai/translation/pipeline/stages/translate.py` record usage, cache entries, and in-memory chunk state, but do not call `save_provider_request_record`.
- Metadata translation calls in `backend/src/novelai/services/orchestration/translation.py` use provider fallback and cache, but do not persist provider request records.
- Glossary provider calls in `backend/src/novelai/services/orchestration/glossary.py` record usage, but do not persist provider request records.
- Provider validation/settings paths are intentionally outside scheduler job execution and should remain separate unless Prompt 11 needs sanitized diagnostics.

## Runtime Paths That Still Do Not Record Chunk Outputs

- `TranslateStage` writes translated chunk text to `context.translations` and updates `context.chunk_states`, but does not persist `runtime/translation/outputs.json`.
- `TranslationQAStage` stores raw provider translations and QA results in pipeline metadata and chunk state, but does not persist per-chunk output records.
- `services/orchestration/translation.py` persists final translated chapters with `save_translated_chapter` and chunk states with `upsert_chunk_state`; it does not currently persist successful per-chunk translation output records.

## Temporary Bundle Lifecycle Gaps

- `SmartSegmentStage` creates temporary chunk/bundle-shaped objects in memory and preserves explicit chapter/paragraph boundaries.
- Storage supports `save_translation_bundle`, `read_translation_bundle`, and `delete_translation_bundle`, but the segmenter/orchestration path does not persist temporary bundles during normal translation.
- There is no scheduler-owned lifecycle yet for bundle creation, retry, successful cleanup, or debug retention.
- Temporary bundle deletion is safe by contract: storage tests prove deleting a bundle does not delete canonical raw or final chapter data.

## API/Frontend Compatibility Notes

- Backend activity models expose optional scheduler-era progress fields without requiring scheduler behavior.
- Frontend API types include `paused_reason`, `resume_after`, and `model_states`; frontend API calls remain centralized through `frontend/lib/api.ts`.
- Compatibility aliases for legacy `provider`/`model` remain in activity/admin contracts while canonical `provider_key` and `provider_model` are exposed for new work.
- Prompt 11 should keep progress additions optional and backward compatible.
- Public contribution credential routing and user/account boundaries are not implemented and must not be assumed by the scheduler.

## Exact Tests To Run Before Prompt 11

Run these immediately before starting Prompt 11:

```bash
pytest backend/tests/test_pipeline_stages.py backend/tests/test_translation_qa.py backend/tests/test_translation_cache.py backend/tests/test_storage_contracts.py backend/tests/test_web_api.py backend/tests/test_frontend_api_contract.py -q
pyright
npm run typecheck
npm run build
```

Recommended broader confidence pass:

```bash
pytest backend/tests/test_gemini_provider.py backend/tests/test_openai_provider.py backend/tests/test_activity_provider_errors.py backend/tests/test_job_queue_service.py backend/tests/test_job_worker_service.py -q
```

## Recommended Scheduler Implementation Scope

- Add scheduler-owned model selection around existing provider/model candidates without moving provider-specific parsing out of `providers/*`.
- Persist provider request records for every scheduler-managed provider call, including success, normalized provider failure, retry-after, cooldown, and quota exhaustion metadata.
- Persist chunk attempts and chunk outputs through storage services before advancing final chapter save.
- Respect existing prompt construction, glossary, exact cache-key, QA, and post-process stages; scheduler routing must not bypass them.
- Use persisted `SchedulerModelState` to represent `available`, `cooling_down`, `daily_exhausted`, `disabled`, and `failed`.
- If one model is cooling down, try the next eligible model; if all are cooling down, pause with `paused_reason` and `resume_after`; if all are daily exhausted, pause until quota reset.
- Never retranslate successful chunks after pause/resume unless explicitly forced.
- Keep final translated output chapter-based and temporary bundles disposable.
