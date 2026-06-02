# Data Output Structure

This reference describes the runtime data written under `storage/novel_library/`.

The storage backend is local and JSON-backed today. It is designed to be simple for development and easy to mount as a volume in production-style Docker Compose.

## Quick Overview

```text
storage/novel_library/
|-- preferences.json
|-- translation_cache.json
|-- usage.json
|-- jobs/
|   |-- queue.json
|   `-- source_health.json
|-- requests/
|   `-- novel_requests.json
`-- novels/
    |-- index.json
    `-- <novel_id>/
        |-- metadata.json
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

Legacy `raw/` and `translated/` directories may still be read for backward compatibility, but new writes use unified chapter bundles in `chapters/`.

## Global Files

### `preferences.json`

Stores non-secret user preferences.

Example:

```json
{
  "preferred_provider": "gemini",
  "preferred_model": "gemini-2.5-flash",
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

Stores reusable translation results by provider, model, and source text hash.

Example shape:

```json
{
  "abc123def456": {
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "text": "The translated text.",
    "created_at": "2026-06-02T10:00:00Z"
  }
}
```

### `usage.json`

Tracks translation usage and cost metadata.

Example:

```json
[
  {
    "timestamp": "2026-06-02T10:05:00Z",
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "tokens": 2847,
    "estimated_cost_usd": 0.0,
    "metadata": {
      "novel_id": "n4423lw",
      "chapter_id": "1"
    }
  }
]
```

### `jobs/queue.json`

Stores crawl and translation jobs.

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

### `jobs/source_health.json`

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

Stores reader/admin novel request intake.

Example:

```json
[
  {
    "id": "request_abc123",
    "title": "Requested Novel",
    "source_url": "https://example.com/novel",
    "status": "open",
    "vote_count": 3,
    "created_at": "2026-06-02T10:00:00Z",
    "updated_at": "2026-06-02T10:00:00Z"
  }
]
```

## Novel Index

### `novels/index.json`

Maps novel IDs to stable folder names.

Example:

```json
{
  "n4423lw": {
    "folder_name": "n4423lw",
    "updated_at": "2026-06-02T10:00:00Z"
  }
}
```

## Novel Metadata

### `novels/<novel_id>/metadata.json`

Stores source/import metadata and chapter index.

Example:

```json
{
  "novel_id": "n4423lw",
  "schema_version": 2,
  "title": "Original Japanese Title",
  "translated_title": "Translated Title",
  "author": "Author Name",
  "translated_author": "Translated Author Name",
  "source": "syosetu_ncode",
  "source_url": "https://ncode.syosetu.com/n4423lw/",
  "origin_type": "url",
  "origin_uri_or_path": "https://ncode.syosetu.com/n4423lw/",
  "document_type": "web_novel",
  "context_group_id": "n4423lw",
  "chapters": [
    {
      "id": 1,
      "title": "Chapter Title",
      "url": "https://ncode.syosetu.com/n4423lw/1/"
    }
  ],
  "folder_name": "n4423lw",
  "scraped_at": "2026-06-02T10:00:00Z",
  "updated_at": "2026-06-02T10:00:00Z"
}
```

## Chapter Bundles

### `novels/<novel_id>/chapters/<chapter_id>.json`

The chapter bundle is the main file for source text, translation output, versions, edit history, OCR/media state, and import metadata.

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
    "model": "gemini-2.5-flash",
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
      "model": "gemini-2.5-flash",
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
  "model": "gemini-2.5-flash",
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

### `novels/<novel_id>/glossary.json`

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
novels/<novel_id>/assets/images/<chapter_id>/
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

### `novels/<novel_id>/state/<chapter_id>.json`

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

### `novels/<novel_id>/checkpoints/<chapter_id>__<name>.json`

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

## Exports

Default exports are written to the novel directory:

```text
novels/<novel_id>/full_novel.epub
novels/<novel_id>/full_novel.html
novels/<novel_id>/full_novel.md
```

A custom output directory can be used by backend export commands when supplied.

## Workflow Artifacts

Typical web workflow:

1. Crawl metadata.
   - Creates or updates `novels/index.json`.
   - Creates or updates `novels/<novel_id>/metadata.json`.
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

The web backend reads and writes this storage through service classes. Common API shapes include:

```text
GET  /api/health
GET  /api/novels
GET  /api/novels/{novel_id}/metadata
GET  /api/novels/{novel_id}/chapters/{chapter_id}
GET  /api/jobs
GET  /api/jobs/{job_id}
POST /api/jobs/crawl
POST /api/jobs/translation
```

## Scaling Notes

The JSON-backed store is good for local-first development, small deployments, and early production testing.

Recommended future upgrades:

- PostgreSQL for novel metadata, chapter versions, jobs, requests, and usage.
- Object storage for images and exports.
- Redis/RQ, Celery, Dramatiq, or another queue backend for jobs.
- CDN in front of reader assets.
