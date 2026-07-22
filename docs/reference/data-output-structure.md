# Data Output Structure

This reference describes the runtime data written under `storage/novel_library/`.

The storage backend is local and JSON-backed today. It is designed to be simple for development and easy to mount as a volume in production-style Docker Compose.

## Quick Overview

```text
storage/
|-- README.md
`-- novel_library/
    |-- preferences.json
    |-- translation_cache.json
    |-- usage.json
    |-- activity_log/
    |   |-- queue.json
    |   `-- source_health.json
    |-- requests/
    |   `-- novel_requests.json
    |-- runtime/
    |   |-- provider_requests.json
    |   |-- fetch_cache/
    |   |   `-- index.json
    |   |-- traceability/
    |   |   |-- pipeline_events.json
    |   |   |-- chunk_states.json
    |   |   `-- scheduler_states.json
    |   `-- translation/
    |       |-- chunks.json
    |       |-- chunk_attempts.json
    |       |-- bundles.json
    |       `-- outputs.json
    `-- novels/
        |-- index.json
        `-- <storage_slug>/
            |-- metadata.json
            |-- metadata_backups/
            |-- glossary.json
            |-- chapters/
            |   `-- <chapter_id>.json
            |-- assets/
            |   `-- images/
            |       `-- <chapter_id>/
            |-- state/
            |   `-- <chapter_id>.json
            |-- checkpoints/
            |   `-- <chapter_id>__translated.json
            |-- full_novel.epub
            |-- full_novel.html
            `-- full_novel.md
```

Title-slug novel content resides under `storage/novel_library/novels/{storage_slug}`.
Single-part legacy folders (e.g. `n2056dn`) live alongside them in the same
`novels/` directory, resolved through the storage index.

`storage/novel_library` is private runtime data. It should not be committed,
served as static frontend files, or pasted into public issue reports. Local
`storage_backups/` folders, when present, are developer backups and should also
remain untracked.

Legacy `raw/` and `translated/` directories may still be read for backward compatibility, but new writes use unified chapter bundles in `chapters/`.

## Global Files

### `preferences.json`

Stores non-secret user preferences.

Example:

```json
{
  "preferred_provider": "gemini",
  "preferred_model": "gemini-3.1-flash-lite",
  "theme": "auto",
  "language": "en",
  "glossary_extraction": {
    "mode": "heuristic",
    "prompt_template": null,
    "max_terms": 50
  }
}
```

Provider API keys should not be stored here. They should come from `.env` or process environment values.

### `translation_cache.json`

Owner module: `backend/src/novelai/services/translation_cache.py`

Stores reusable translation results by exact cache key. New keys must include prompt-affecting and model-affecting metadata: source text hash, source language, target language, `provider_key`, `provider_model`, prompt version, glossary hash, style preset, JSON output mode, and consistency mode. Optional key inputs include chapter/novel memory hashes, selected glossary hash, system prompt hash, temperature, top-p, and structured output schema version.

The current on-disk value is a backward-compatible mapping of cache key to translated text:

Example shape:

```json
{
  "abc123def456": "The translated text."
}
```

Schema version: implicit legacy shape.

Migration/backward compatibility: legacy entries keyed by provider/model/source text may remain readable through the cache service. Exact keys should be used for new prompt-aware cache writes.

Retention policy: cache entries may be cleared by admin/runtime-state operations. Clearing the cache must not delete chapter bundles, translation outputs, provider request records, or traceability records.

### `usage.json`

Tracks translation usage and cost metadata.

Example:

```json
[
  {
    "timestamp": "2026-06-02T10:05:00Z",
    "provider": "gemini",
    "model": "gemini-3.1-flash-lite",
    "tokens": 2847,
    "estimated_cost_usd": 0.0,
    "metadata": {
      "novel_id": "n4423lw",
      "chapter_id": "1"
    }
  }
]
```

### `activity_log/queue.json`

Stores crawl and translation activity. Legacy `jobs/queue.json` data is migrated into `activity_log/queue.json` when the activity queue service starts.

Example:

```json
[
  {
    "id": "translation_abc123",
    "type": "translation",
    "kind": "translate",
    "novel_id": "n4423lw",
    "source_key": "syosetu_ncode",
    "chapters": "1-3",
    "provider": "gemini",
    "model": null,
    "status": "pending",
    "created_at": "2026-06-02T10:00:00Z",
    "started_at": null,
    "finished_at": null,
    "retry_count": 0,
    "error": null,
    "metadata": {}
  }
]
```

Valid job types:

- `crawl`
- `translation`

Common statuses:

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`

### `activity_log/source_health.json`

Tracks source adapter reliability.

Example:

```json
{
  "syosetu_ncode": {
    "source_key": "syosetu_ncode",
    "success_count": 4,
    "failure_count": 1,
    "last_success_at": "2026-06-02T10:20:00Z",
    "last_failure_at": "2026-06-02T09:00:00Z",
    "last_error": null,
    "updated_at": "2026-06-02T10:20:00Z"
  }
}
```

### `requests/novel_requests.json`

Removed legacy file-backed request intake. Novel requests are stored in the
database-backed `novel_requests` table. Legacy admin create/vote/source-candidate
routes remain as compatibility stubs that return `410 Gone`.

## Novel Index

### `novels/index.json`

Maps logical novel IDs/source IDs to actual storage folder names.

The `folder_name` value may be either:

- a legacy source-ID folder such as `n2056dn`
- a title-slug folder such as `the-silent-architect-of-dreams`

Do not manually edit this file unless you are deliberately repairing storage.
If a folder is moved without updating the index, DB rows and public/admin API
lookups may point at missing content.

Example:

```json
{
  "n4423lw": {
    "folder_name": "translated-title",
    "updated_at": "2026-06-02T10:00:00Z"
  }
}
```

## Novel Metadata

### `novels/<storage_slug>/metadata.json`

Legacy path: `novels/<source_id>/metadata.json`

Stores source/import metadata and chapter index.

Important field groups:

- Identity: `novel_id`, `source_novel_id`
- Storage resolver: `folder_name`, `storage_slug`
- Source metadata: `source`, `source_url`, `title`, `author`, `synopsis`,
  `description`, `publication_status`, `source_publication_status`,
  `chapters[].title`, `chapters[].part`
- Translated/public metadata: `translated_title`, `translated_author`,
  `translated_synopsis`, `chapters[].translated_title`,
  `metadata_translation_status`, `metadata_translation_prompt_version`,
  `metadata_translation_provider`, `metadata_translation_model`,
  `metadata_translation_error`
- Timestamps and workflow hints: `scraped_at`, `updated_at`,
  `source_updated_at`, `translation_profiles`

Source fields must be preserved even when translated fields exist. Public
catalog/detail projections prefer translated fields when present, but source
metadata remains needed for audit, re-scrape, and admin inspection.

Example:

```json
{
  "novel_id": "n4423lw",
  "source_novel_id": "n4423lw",
  "schema_version": 2,
  "title": "Original Japanese Title",
  "translated_title": "Translated Title",
  "author": "Author Name",
  "translated_author": "Translated Author Name",
  "synopsis": "Original source synopsis.",
  "translated_synopsis": "Translated synopsis.",
  "source": "syosetu_ncode",
  "source_url": "https://ncode.syosetu.com/n4423lw/",
  "publication_status": "ongoing",
  "source_publication_status": "連載中",
  "metadata_translation_status": "completed",
  "metadata_translation_prompt_version": "metadata-literal-v2",
  "metadata_translation_provider": "gemini",
  "metadata_translation_model": "gemini-3.1-flash-lite",
  "origin_type": "url",
  "origin_uri_or_path": "https://ncode.syosetu.com/n4423lw/",
  "document_type": "web_novel",
  "context_group_id": "n4423lw",
  "chapters": [
    {
      "id": 1,
      "title": "Chapter Title",
      "translated_title": "Translated Chapter Title",
      "part": "Part 1",
      "url": "https://ncode.syosetu.com/n4423lw/1/"
    }
  ],
  "folder_name": "translated-title",
  "storage_slug": "translated-title",
  "scraped_at": "2026-06-02T10:00:00Z",
  "updated_at": "2026-06-02T10:00:00Z"
}
```

## Chapter Bundles

### `novels/<storage_slug>/chapters/<chapter_id>.json`

Legacy path: `novels/<source_id>/chapters/<chapter_id>.json`

The chapter bundle is the main file for source text, translation output, versions, edit history, OCR/media state, and import metadata.

Final readable chapter translation lives in `translated.text` and
`translated.paragraphs`. Historical or alternate translations live in
`translation_versions`. Raw source content remains under `raw.text` and
`raw.paragraphs`.

Do not paste raw or translated chapter bodies into public logs or tickets
casually. Raw source content can be copyrighted, and Novel18/adult content may
exist in raw, translated, runtime, cache, or provider-request records.

Example:

```json
{
  "id": "1",
  "schema_version": 2,
  "title": "Chapter Title",
  "source_key": "syosetu_ncode",
  "source_url": "https://ncode.syosetu.com/n4423lw/1/",
  "origin_type": "web",
  "document_type": "web_novel",
  "unit_type": "chapter",
  "context_group_id": "n4423lw",
  "raw": {
    "id": "1",
    "scraped_at": "2026-06-02T10:10:00Z",
    "text": "[Japanese source text]",
    "paragraphs": [
      "[Japanese source paragraph]"
    ],
    "images": []
  },
  "translated": {
    "version_id": "v1",
    "version_kind": "machine_translation",
    "provider": "gemini",
    "model": "gemini-3.1-flash-lite",
    "translated_at": "2026-06-02T10:20:00Z",
    "created_at": "2026-06-02T10:20:00Z",
    "text": "Translated chapter text.",
    "paragraphs": [
      "Translated chapter text."
    ],
    "confidence_score": 0.91,
    "polish_needed": false
  },
  "translation_versions": [
    {
      "id": "v1",
      "kind": "machine_translation",
      "provider": "gemini",
      "model": "gemini-3.1-flash-lite",
      "created_at": "2026-06-02T10:20:00Z",
      "translated_at": "2026-06-02T10:20:00Z",
      "text": "Translated chapter text.",
      "paragraphs": [
        "Translated chapter text."
      ],
      "confidence_score": 0.91,
      "polish_needed": false
    }
  ],
  "active_translation_version_id": "v1",
  "edit_history": [],
  "ocr_required": false,
  "ocr_text": null,
  "ocr_pages": [],
  "ocr_status": "skipped",
  "reembed_status": "skipped",
  "region_metadata": [],
  "ocr_artifacts": []
}
```

## Translation Versions And Edits

Manual editor saves add a new version and make it active.

Example edit version:

```json
{
  "id": "v2",
  "kind": "manual_edit",
  "provider": "gemini",
  "model": "gemini-3.1-flash-lite",
  "created_at": "2026-06-02T10:30:00Z",
  "translated_at": "2026-06-02T10:30:00Z",
  "text": "Edited translated text.",
  "paragraphs": [
    "Edited translated text."
  ],
  "editor": "admin",
  "note": "Cleaned up honorifics.",
  "base_version_id": "v1"
}
```

Example edit history:

```json
[
  {
    "id": "e1",
    "action": "manual_edit",
    "version_id": "v2",
    "previous_version_id": "v1",
    "created_at": "2026-06-02T10:30:00Z",
    "editor": "admin",
    "note": "Cleaned up honorifics."
  }
]
```

## Glossary

### `novels/<storage_slug>/glossary.json`

Legacy path: `novels/<source_id>/glossary.json`

Stores extracted, translated, reviewed, and approved terms.

Example:

```json
[
  {
    "source": "Akira",
    "target": "Akira",
    "status": "approved",
    "notes": "Character name."
  }
]
```

## Media And OCR

Images are stored under:

```text
novels/<storage_slug>/assets/images/<chapter_id>/
```

Example:

```text
assets/
`-- images/
    `-- 1/
        |-- 0001.jpg
        `-- 0002.png
```

Chapter `raw.images` stores the local asset path and original metadata.

OCR and re-embedding fields live in the chapter bundle:

- `ocr_required`
- `ocr_text`
- `ocr_pages`
- `ocr_status`
- `reembed_status`
- `ocr_artifacts`
- `region_metadata`

Valid OCR statuses:

- `pending`
- `reviewed`
- `skipped`
- `failed`

Valid re-embedding statuses:

- `pending`
- `completed`
- `failed`
- `skipped`

## Chapter State

### `novels/<storage_slug>/state/<chapter_id>.json`

Legacy path: `novels/<source_id>/state/<chapter_id>.json`

Tracks state transitions and retry/error counters.

Example:

```json
{
  "chapter_id": "1",
  "current_state": "translated",
  "transitions": [
    {
      "from_state": null,
      "to_state": "scraped",
      "timestamp": "2026-06-02T10:10:00Z",
      "error": null
    },
    {
      "from_state": "scraped",
      "to_state": "translated",
      "timestamp": "2026-06-02T10:20:00Z",
      "error": null
    }
  ],
  "last_updated": "2026-06-02T10:20:00Z",
  "error_count": 0,
  "retry_count": 0
}
```

## Checkpoints

### `novels/<storage_slug>/checkpoints/<chapter_id>__<name>.json`

Legacy path: `novels/<source_id>/checkpoints/<chapter_id>__<name>.json`

Stores recovery snapshots.

Example:

```json
{
  "chapter_id": "1",
  "timestamp": "2026-06-02T10:20:00Z",
  "checkpoint_name": "translated",
  "raw_chapter": {
    "id": "1",
    "text": "[Japanese source text]"
  },
  "translated_chapter": {
    "id": "1",
    "version_id": "v1",
    "text": "Translated chapter text."
  },
  "chapter_state": {
    "chapter_id": "1",
    "current_state": "translated",
    "transitions": [],
    "last_updated": "2026-06-02T10:20:00Z",
    "error_count": 0,
    "retry_count": 0
  }
}
```

## Runtime Traceability

Runtime files are owned by `backend/src/novelai/storage/*`. Pipeline, service, provider, and API modules should call `StorageService` methods instead of constructing these paths directly.

### `runtime/traceability/pipeline_events.json`

Owner module: `backend/src/novelai/storage/traceability.py`

Append-only list of stage/job events.

Required fields:

- `timestamp`
- `stage_name`
- `message` when useful

Optional fields:

- `job_id` / `activity_id`
- `novel_id`
- `chapter_id`
- `source_key`
- `provider_key`
- `provider_model`
- `chunk_id`
- `status_before`
- `status_after`
- `warning_code`
- `error_code`

Schema version: implicit legacy list.

Migration/backward compatibility: missing optional fields should be treated as unknown.

Retention policy: runtime/debug record; may be pruned by future maintenance without touching canonical chapter bundles.

### `runtime/traceability/chunk_states.json`

Owner module: `backend/src/novelai/storage/traceability.py`

Mapping keyed by `<novel_id>:<chunk_id>` for lightweight chunk state and attempts.

Required fields:

- `chunk_id`
- `novel_id`
- `status`
- `created_at`
- `updated_at`

Optional fields:

- `chapter_ids`
- `paragraph_ids`
- `provider_key`
- `provider_model`
- `attempt_number`
- `error_code`
- `qa_score`

Schema version: implicit legacy mapping.

Migration/backward compatibility: legacy final chapter translations without chunk state remain readable but are not eligible for chunk-level retry unless reprocessed.

Retention policy: may be kept for retry/debug; deleting it must not delete canonical chapter output.

### `runtime/traceability/scheduler_states.json`

Owner module: `backend/src/novelai/storage/traceability.py`

Mapping keyed by `job_id` for scheduler model state used by admin-owned provider/model routing.

Required fields:

- `job_id`
- `updated_at`
- `model_states`

Each `model_states` entry should include:

- `provider_key`
- `provider_model`
- `priority_order`
- `status`

Optional fields:

- `credential_id`
- `credential_owner_user_id`
- `requesting_user_id`
- `rpm_limit`
- `rpd_limit`
- `requests_this_minute`
- `requests_today`
- `window_started_at`
- `cooldown_until`
- `exhausted_until`
- `last_error_code`
- `last_error_message`
- `routing_mode`

Allowed statuses: `available`, `cooling_down`, `daily_exhausted`, `disabled`, `failed`.

Schema version: implicit legacy mapping.

Migration/backward compatibility: per-minute counters should be recovered conservatively after restart.

Retention policy: runtime/job state; deleting it may remove pause/resume hints but must not delete chunks or final chapters.

## Translation Runtime Records

Canonical chapter storage remains `novels/<storage_slug>/chapters/<chapter_id>.json`
for new saves, with legacy reads from
`novels/<source_id>/chapters/<chapter_id>.json`. The following runtime files are
pipeline/cache/retry artifacts and must not be treated as final chapter output.

### `runtime/translation/chunks.json`

Owner module: `backend/src/novelai/storage/runtime_contracts.py`

Mapping keyed by `<novel_id>:<chunk_id>` for traceable translation chunks.

Required fields:

- `schema_version`
- `chunk_id`
- `novel_id`
- `chapter_ids`
- `paragraph_ids`
- `source_text_hash`
- `char_count`
- `status`
- `attempt_count`
- `created_at`
- `updated_at`

Optional fields:

- `source_text`
- `paragraph_refs`
- `provider_key`
- `provider_model`
- `last_error_code`
- `qa_score`
- `qa_warnings`
- `qa_errors`

Schema version: `1`.

Migration/backward compatibility: existing runtime data may lack these records. Existing final chapter output remains readable as legacy chapter-based output.

Retention policy: may be retained for retry/debug. Deleting it must not delete raw chapters, parsed chapters, or final translations.

### `runtime/translation/chunk_attempts.json`

Owner module: `backend/src/novelai/storage/runtime_contracts.py`

Mapping keyed by `<novel_id>:<chunk_id>:<attempt_number>` for scheduler-managed provider attempts and resume skips.

Required fields:

- `schema_version`
- `attempt_id`
- `chunk_id`
- `novel_id`
- `chapter_ids`
- `paragraph_ids`
- `attempt_number`
- `status`
- `created_at`
- `updated_at`

Optional fields:

- `source_text_hash`
- `provider_key`
- `provider_model`
- `scheduler_policy`
- `selection_reason`
- `error_code`
- `qa_score`
- `qa_status`

Allowed statuses: `pending`, `running`, `succeeded`, `failed`, `qa_failed`, `skipped_cache_hit`, `skipped_already_succeeded`.

Schema version: `1`.

Migration/backward compatibility: older runtime data may only have `chunk_states.json`. Missing attempt records do not make final chapter translations unreadable.

Retention policy: retry/debug artifact. Deleting it must not delete canonical chapter output or temporary bundle records.

### `runtime/translation/bundles.json`

Owner module: `backend/src/novelai/storage/runtime_contracts.py`

Mapping keyed by `<novel_id>:<bundle_id>` for temporary translation bundles. Bundles may contain paragraphs from one chapter or nearby short chapters, but must preserve explicit `chapter_ids`, `paragraph_ids`, and chunk membership.

Required fields:

- `schema_version`
- `bundle_id`
- `novel_id`
- `chunk_ids`
- `chapter_ids`
- `paragraph_ids`
- `status`
- `created_at`
- `updated_at`

Optional fields:

- `source_text_hash`
- `target_chars`
- `hard_max_chars`
- `prompt_version`
- `provider_key`
- `provider_model`
- `attempt_count`
- `last_error_code`
- `qa_score`
- `warnings`
- `errors`

Schema version: `1`.

Migration/backward compatibility: bundles are optional. A missing bundle must not make saved chapter output unreadable.

Retention policy: temporary retry/debug artifact. It may be deleted after successful per-chapter save.

### `runtime/translation/outputs.json`

Owner module: `backend/src/novelai/storage/runtime_contracts.py`

Mapping keyed by `<novel_id>:<output_id>` for chunk-level translation output before or alongside canonical chapter saves.

Required fields:

- `schema_version`
- `output_id`
- `chunk_id`
- `novel_id`
- `chapter_ids`
- `paragraph_ids`
- `translated_text`
- `structured_paragraph_map`
- `created_at`

Optional fields:

- `raw_provider_response_path`
- `qa_score`
- `qa_warnings`
- `qa_errors`
- `qa_status`
- `prompt_version`
- `glossary_hash`
- `source_text_hash`
- `output_hash`
- `provider_key`
- `provider_model`
- `scheduler_policy`
- `selection_reason`
- `attempt_number`
- `cache_hit`

Schema version: `1`.

Migration/backward compatibility: final chapter translations still live in chapter bundles. Chunk output records are supplemental and can be absent for legacy translations.

Retention policy: retained for QA/debug/retry when useful. Deleting it must not delete canonical final chapter output.

## Provider Requests

### `runtime/provider_requests.json`

Owner module: `backend/src/novelai/storage/runtime_contracts.py`

Append-only list of successful and failed provider calls.

Required fields:

- `schema_version`
- `request_id`
- `timestamp`
- `provider_key`
- `provider_model`
- `success`

Optional fields:

- `job_id` / `activity_id`
- `novel_id`
- `chapter_id` / `chapter_ids`
- `paragraph_ids`
- `chunk_id`
- `bundle_id`
- `prompt_version`
- `source_text_hash` / `prompt_hash`
- `glossary_hash`
- `style_preset`
- `json_output`
- `consistency_mode`
- `scheduler_policy`
- `selection_reason`
- `attempt_number`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `latency_ms`
- `normalized_provider_error_code`
- `retry_after_seconds`
- `cooldown_until`
- `exhausted_until`
- `requesting_user_id`
- `credential_id`
- `credential_owner_user_id`
- `credential_scope`

Schema version: `1`.

Security: records must not store API keys, raw secrets, authorization headers, cookies, or raw tracebacks. Public APIs should return sanitized summaries.

Migration/backward compatibility: old translations may have usage records but no provider request records.

Retention policy: audit/debug runtime record; may be pruned according to future admin policy.

## Fetch Cache

### `runtime/fetch_cache/index.json`

Owner module: `backend/src/novelai/storage/runtime_contracts.py`

Mapping keyed by `<source_key>:<url>` for source HTTP response cache entries.

Required fields:

- `schema_version`
- `url`
- `canonical_url`
- `source_key`
- `status_code`
- `headers`
- `fetched_at`
- `body_hash`

Optional fields:

- `etag`
- `last_modified`
- `body_text`
- `body_path`
- `parser_version`
- `from_cache`

Schema version: `1`.

Migration/backward compatibility: FetchService can continue using the in-memory cache. File-backed entries are a storage foundation for conditional revalidation with `If-None-Match` and `If-Modified-Since`.

Retention policy: cache/debug artifact. Deleting fetch cache entries must not delete raw chapter snapshots already stored in chapter bundles.

## Runtime File Safety

Runtime JSON is private operational state. Stop the backend, worker, and any
active scrape/translation process before deleting or replacing runtime files.

| Path | Purpose | Producer/consumer | Sensitive/copyright risk | Safe to delete? | Consequence |
|---|---|---|---|---|---|
| `novels/<slug>/` | Title-slug novel metadata and chapter bundles | StorageService, catalog projection, reader/admin APIs | High: raw and translated chapter content | No, unless resetting DB/storage together from backup | Public/admin novel rows may point at missing content |
| `novels/` | Legacy source-ID folders plus `index.json` resolver | StorageService compatibility reads/writes | High: raw and translated chapter content | No, unless resetting DB/storage together from backup | Legacy novels and folder resolution can break |
| `novels/index.json` | Maps logical novel IDs/source IDs to folder names | StorageService | Medium: IDs/source linkage | Only during careful storage repair | Wrong edits can orphan folders or route lookups |
| `metadata_backups/` | Bounded backup copies of old `metadata.json` | StorageService metadata save | Medium: source URLs, synopsis, titles | Usually yes after backup, but keep recent copies during active work | Loses metadata history/diff inspection |
| `runtime/traceability/*.json` | Pipeline events, chunk states, scheduler state | Storage traceability/runtime services | Medium to high: errors, hashes, source snippets may appear | Yes for local dev after stopping services | Loses retry/debug/scheduler history |
| `runtime/translation/*.json` | Chunk, attempt, bundle, and output artifacts | Translation pipeline/runtime services | High: source/translated text may appear | Yes for local dev after stopping services | Loses retry/debug artifacts, but final chapter bundles remain |
| `runtime/provider_requests.json` | Provider call audit summaries | Provider/runtime services | High: prompt hashes, error summaries, token usage; must stay private even when redacted | Only after backup and with services stopped | Loses provider audit/debug records |
| `runtime/fetch_cache/` | Source HTTP cache metadata/body cache | FetchService/runtime services | High: source pages or snippets may appear | Yes after stopping services | Source pages may be fetched again |
| `activity_log/` | Activity queue and source-health records | Activity queue, admin activity UI | Medium: job metadata and errors | Only for local dev reset with services stopped | Loses queued/running/completed activity history |
| `translation_cache.json` | Prompt/model keyed translation cache | Translation cache service | High: translated text | Yes after stopping services | May cost provider calls to regenerate |
| `usage.json` | Local usage/cost accounting | Usage tracking | Low to medium: provider/model/job metadata | Yes for local dev reset | Loses usage history |
| `preferences.json` | Non-secret owner/runtime preferences | Settings/storage service | Low, but should remain private | Yes if defaults are acceptable | Loses local preferences |
| `requests/novel_requests.json` | Removed legacy request store | Legacy compatibility only | Medium if old data exists | Yes only after confirming DB-backed requests are canonical | Old file-backed request history is lost |

Novel18/adult content can appear in raw chapter bundles, translated chapter
bundles, runtime translation files, provider request summaries, fetch cache, and
translation cache. Treat the whole `storage/novel_library` tree as private.

## Backup And Restore

For local backups, copy the entire `storage/novel_library` directory rather than
individual novel folders. Keep backups outside git, for example under a local
`storage_backups/` directory that remains untracked.

Restore storage and the database together when possible. The database contains
catalog projection rows, publish state, users, requests, jobs, and settings;
storage contains chapter bodies and metadata JSON. Resetting only one side can
leave DB rows pointing at missing storage, or storage folders that are invisible
to admin/public listings until reconciliation runs.

Do not manually move `novels/<slug>` or legacy `novels/{source_id}`
folders without also preserving or repairing `novels/index.json`.

## Public URL And Slug Notes

Public reader URLs use plural canonical routes:

```text
/novels/{slug}
/novels/{slug}/chapter/{chapterId}
```

`storage_slug` and public `slug` may align, but they are separate concepts.
`storage_slug` is a filesystem-safe folder slug owned by the storage service.
The public slug is the API/frontend routing identifier. Source IDs can still
exist internally as `novel_id`, `source_novel_id`, source URLs, and index keys.

## Credential Storage

Public user-contributed credential storage is not implemented in the current file-backed storage. Adding it requires an explicit product-boundary change: authenticated public users, admin role separation, encrypted credential storage, revocation/deletion flows, audit logging, contribution consent, and usage limits. Raw provider keys must never be stored in plaintext, returned to the frontend after save, or logged.

## Exports

Default exports are written to the novel directory:

```text
novels/<storage_slug>/full_novel.epub
novels/<storage_slug>/full_novel.html
novels/<storage_slug>/full_novel.md
```

A custom output directory can be used by backend export commands when supplied.
Legacy exports may still exist under `novels/<source_id>/`.

## Workflow Artifacts

Typical web workflow:

1. Crawl metadata.
   - Creates or updates `novels/index.json`.
   - Creates or updates `novels/<storage_slug>/metadata.json`.
   - Existing legacy novels may continue reading from `novels/<source_id>/metadata.json`.
2. Crawl chapters.
   - Creates `chapters/<chapter_id>.json`.
   - Creates image assets when source images exist.
   - Updates source health and chapter state.
3. Translate chapters.
   - Adds `translated`.
   - Adds or appends `translation_versions`.
   - Updates `active_translation_version_id`.
   - Updates `usage.json` and `translation_cache.json`.
   - Creates checkpoints.
4. Edit chapters.
   - Appends manual versions.
   - Updates edit history and active version.
5. Export.
   - Creates `full_novel.epub`, `full_novel.html`, or `full_novel.md`.

## API Integration

The web backend reads and writes this storage through service classes. Current canonical API routes:

```text
GET  /health/live                              — process liveness
GET  /health/ready                             — dependency readiness
GET  /api/public/catalog                        — paginated novel list
GET  /api/public/novels/{slug}                   — novel detail
GET  /api/public/novels/{slug}/chapters          — chapter list
GET  /api/public/novels/{slug}/chapters/{id}     — chapter reader
GET/POST/DELETE /api/user/library/{slug}         — user library
GET/PUT /api/user/progress/{slug}                — reading progress
GET/POST /api/user/history                       — reading history
POST /api/user/reviews/{slug}                    — reviews/ratings
GET/POST /api/user/requests                      — novel/chapter requests
POST /api/auth/login                             — owner bootstrap login
GET  /api/auth/google/start                      — Google OAuth start
GET  /api/auth/google/callback                   — Google OAuth callback
POST /api/auth/logout                            — clear session
GET  /api/auth/me                                — current session
/api/admin/*                                     — admin operations (crawl, translate, settings, activity, editor, requests)
```

The former backend `/novels/*` and `/api/novels/*` compatibility routes are removed. Admin callers use `/api/admin/*`; public reader callers use `/api/public/*` and browser pages use frontend `/novels/*` routes. Use canonical `activity_id` / `job_id` fields.

## Scaling Notes

The JSON-backed store under `storage/novel_library` remains the chapter content store. PostgreSQL 16 (via SQLAlchemy + Alembic) is already the system of record for metadata, user data, jobs, and settings. Redis/RQ is available for background workers.

Recommended future upgrades:

- Explicit `schema_version` fields for every metadata/runtime JSON family.
- DB-backed public slug and storage index resolver so route lookup and storage
  lookup can evolve independently.
- Runtime pruning command with dry-run output before deletion.
- Storage diagnostic command that checks DB rows, index mappings, folder
  existence, metadata validity, translated counts, and public slug resolution.
- Optional legacy migration CLI to move `novels/{source_id}` folders into
  `novels/{storage_slug}` with backups and index repair.
- Object storage (S3/R2/B2) for images, covers, and exports at production scale.
- CDN in front of reader assets.
- Redis-backed rate limiting (current rate limiter is in-memory).
