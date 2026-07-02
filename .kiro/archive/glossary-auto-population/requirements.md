# Requirements: Glossary Auto-Population

## Introduction

Glossary management is currently a manual process. The owner must identify terms that need consistent translation, research appropriate translations, and add them to the glossary one by one. This is time-consuming and error-prone, especially for novels with large character casts, specialized terminology, or unusual settings.

This spec adds a semi-automatic glossary suggestion system that analyzes translated output to identify candidate terms for glossary entries. The owner can review, accept, reject, or modify suggestions. This reduces manual effort while keeping the owner in control of the final glossary.

## Requirements

### REQ-1: Term Extraction from Translated Output

After a chapter is translated, the system must analyze the output to identify potential glossary terms.

- REQ-1.1: After pipeline Stage 6 (Post-Process) completes for a chapter, trigger term extraction on the translated text.
- REQ-1.2: Term extraction must use two strategies:
  - **Frequency-based:** Identify repeated phrases (2-5 word n-grams) in the translated text that appear more than a configurable threshold (default: 3 times in a single chapter).
  - **LLM-based:** Use a lightweight LLM call to extract proper nouns (character names, place names, organization names) from the source text that may be candidates for glossary entries.
- REQ-1.3: The extraction must be best-effort: if extraction fails (e.g. LLM call timeout), log at `WARNING` and proceed without suggestions.
- REQ-1.4: Terms already present in the novel's glossary must be excluded from suggestions.
- REQ-1.5: Terms previously suggested and rejected must be excluded from future suggestions.

### REQ-2: Suggestion Storage

Suggestions must be stored durably for owner review.

- REQ-2.1: Suggestions must be stored in a JSON file `glossary_suggestions.json` under the novel's directory (`storage/novel_library/novel/{slug}/glossary/`).
- REQ-2.2: Each suggestion entry must contain: `term` (source language), `suggested_translation` (target language), `frequency` (int), `source` (`"frequency"` or `"llm"`), `chapter_ids` (list of chapters where found), `confidence` (float 0-1), `status` (`"pending"`, `"accepted"`, `"rejected"`), `created_at` (ISO timestamp).
- REQ-2.3: A rejected suggestion must store the rejection reason (optional, free text).

### REQ-3: Owner Review API

The owner must be able to review, accept, reject, and modify suggestions.

- REQ-3.1: `GET /api/admin/novels/{novel_id}/glossary/suggestions` — list all suggestions for a novel, filterable by `status` (pending/accepted/rejected) and `source` (frequency/llm).
- REQ-3.2: `POST /api/admin/novels/{novel_id}/glossary/suggestions/{suggestion_id}/accept` — accept a suggestion. Optionally accepts a `modified_translation` field to edit the suggested translation before adding to glossary.
- REQ-3.3: `POST /api/admin/novels/{novel_id}/glossary/suggestions/{suggestion_id}/reject` — reject a suggestion. Accepts an optional `reason` field.
- REQ-3.4: `POST /api/admin/novels/{novel_id}/glossary/suggestions/accept-all` — accept all pending suggestions at once.
- REQ-3.5: `POST /api/admin/novels/{novel_id}/glossary/suggestions/reject-all` — reject all pending suggestions at once.

### REQ-4: Acceptance Integration

When a suggestion is accepted, it must be added to the active glossary.

- REQ-4.1: Accepting a suggestion must call `GlossaryService.add_term(novel_id, source_term, translated_term)` to add the term to the novel's active glossary file.
- REQ-4.2: After accepting, the suggestion's `status` must change to `"accepted"` and the translation cache must be invalidated (via `TranslationCacheService.invalidate(novel_id)`, if the caching spec is implemented).
- REQ-4.3: The accepted term must trigger glossary re-application for future translations. Re-translation of existing chapters is not required unless the owner explicitly requests it.

### REQ-5: Deduplication and Merging

- REQ-5.1: If a suggestion exists with the same `term` and `status=pending`, a new extracted suggestion must be merged (increment frequency, append chapter_id) instead of creating a duplicate.
- REQ-5.2: If the exact `term` already exists in the active glossary, skip creating a suggestion.
- REQ-5.3: If a suggestion was previously rejected, it must not be re-created unless the `rejected` flag is manually cleared by the owner.

## Non-Goals

- This spec does not automatically accept suggestions. Owner review is required.
- This spec does not add glossary suggestion UI to the frontend — API-only for now.
- This spec does not change the existing glossary file format or storage.
- This spec does not add multi-language extraction (source language only).
- This spec does not re-translate chapters after glossary acceptance.
