# Release D Plan: Advanced Media Workflow (OCR + Re-Embedding)

> Historical note: this plan predates the web-only direction. OCR capabilities are now part of the backend service layer; future UX work should surface them in the web admin.

This plan defines Release D as an optional advanced track focused on image-heavy documents.

## Objective

Add a reliable end-to-end media path for:

1. OCR extraction from image-heavy chapters/pages.
2. Human review and correction of OCR text.
3. Translation using reviewed OCR text and glossary context.
4. Optional image text re-embedding.
5. Export preserving translated text and media integrity.

## Scope

In scope:

1. OCR pipeline integration for image-bearing sources.
2. Review-state gating so translation runs only after OCR review when required.
3. Re-embedding workflow as an explicit optional step.
4. Diagnostics visibility for OCR/re-embedding progress and failures.

Out of scope for Release D:

1. New OCR engines beyond the current ingest-and-review workflow.
2. Automatic graphic editing pipelines beyond explicit re-embedding support.

## Architecture Additions

### 1. Chapter-Level OCR State

Introduce chapter flags in chapter bundles:

1. `ocr_required: bool`
2. `ocr_text: str | None`
3. `ocr_status: pending | reviewed | skipped | failed`
4. `reembed_status: pending | completed | failed | skipped`

Primary file targets:

1. `backend/src/novelai/services/storage_service.py`
2. `backend/src/novelai/core/chapter_state.py`

### 2. OCR Service Integration

Add service-level OCR operation that can be called from orchestration:

1. Extract candidate OCR text from image manifests.
2. Persist OCR payload per chapter.
3. Surface retriable failure info.

Primary file targets:

1. `backend/src/novelai/services/novel_orchestration_service.py`
2. `backend/src/novelai/pipeline/stages/fetch.py`
3. `backend/src/novelai/pipeline/stages/parse.py`

### 3. OCR Review Workflow

Add review controls in the web admin and backend API:

1. List OCR-pending chapters.
2. Mark reviewed/approved after correction.
3. Preflight gate translation if OCR is required but not reviewed.

Primary file targets:

1. `backend/src/novelai/interfaces/web/routers/novels.py`
2. `frontend/app/(admin)/admin/editor/page.tsx`
3. `backend/src/novelai/services/novel_orchestration_service.py`

### 4. Re-Embedding Step

Add explicit post-translation optional re-embedding operation:

1. Consume translated OCR text + source image regions.
2. Save generated assets and link them in chapter bundles.
3. Keep fallback behavior if re-embedding fails.

Primary file targets:

1. `backend/src/novelai/services/novel_orchestration_service.py`
2. `backend/src/novelai/services/storage_service.py`
3. `backend/src/novelai/export/epub_exporter.py`
4. `backend/src/novelai/export/html_exporter.py`

## Execution Phases

### Phase D1: Data Model + Storage (1 week)

Deliverables:

1. Chapter bundle schema extension for OCR/re-embedding statuses.
2. Storage read/write helpers and migration-safe defaults.
3. Tests for backward compatibility of old chapter bundles.

Acceptance criteria:

1. Existing chapters without OCR fields still load cleanly.
2. New OCR fields persist and round-trip with no data loss.

### Phase D2: OCR Ingestion + Review Gate (1 week)

Deliverables:

1. OCR ingestion endpoint in orchestration.
2. Preflight check blocks translation if OCR review required and incomplete.
3. Web admin controls to inspect and approve OCR review state.

Acceptance criteria:

1. Translation fails fast with explicit error code when OCR review is missing.
2. Approved OCR chapters proceed through translation.

### Phase D3: Re-Embedding Workflow (1 week)

Deliverables:

1. Optional re-embedding command and orchestration path.
2. Checkpoint entries for re-embedding progress and recovery.
3. Exporters consume re-embedded assets when present.

Acceptance criteria:

1. Re-embedding can be run independently after translation.
2. Export outputs use re-embedded assets when available.

### Phase D4: UX + Diagnostics (3-4 days)

Deliverables:

1. Web admin diagnostics counters for OCR pending/reviewed/failed and re-embedding states.
2. Library/admin inspection panel includes OCR/re-embedding readiness.
3. Updated user docs and runbooks.

Acceptance criteria:

1. Operators can detect blocked chapters and why from web admin diagnostics alone.
2. Guide docs reflect exact commands and state transitions.

## Test Plan

Required test updates:

1. `backend/tests/test_storage_service.py`: schema/default compatibility and OCR field persistence.
2. `backend/tests/test_novel_orchestration_service.py`: OCR preflight enforcement and re-embedding flow.
3. `backend/tests/test_pipeline_stages.py`: OCR-aware parse/translate path behavior.
4. `backend/tests/test_web_api.py`: diagnostics/library API rendering for OCR and re-embedding state.
5. `backend/tests/test_integration.py`: end-to-end OCR reviewed -> translate -> re-embed -> export.

## Risks and Mitigations

1. OCR quality variance across sources.
Mitigation: require review-state gate and expose retries.

2. Increased state complexity in chapter bundles.
Mitigation: typed helpers in storage and explicit defaults.

3. Re-embedding failures on edge cases.
Mitigation: non-blocking optional step; preserve normal export path.

## Operational Rollout

1. Release behind feature flag: `ENABLE_MEDIA_WORKFLOW=true`.
2. Pilot on a small set of novels with image-heavy chapters.
3. Promote to default only after stability thresholds are met.

## Success Metrics

1. Percentage of OCR-required chapters successfully reviewed and translated.
2. Re-embedding success rate.
3. Reduction in manual post-export image text fixes.
4. Zero regression in non-media novel workflows.

