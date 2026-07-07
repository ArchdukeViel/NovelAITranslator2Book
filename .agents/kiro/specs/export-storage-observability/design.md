# Design: Export Storage Observability

## Overview

This design adds visibility and contract tests for export artifacts. Export creates downstream files from translated chapter storage, active version selection, metadata, and assets. Admins should know what was exported, where it was stored, which input versions were used, whether the export is stale, and why an export failed.

The design is additive and starts with source review. Because the deep research reports did not fully inspect export paths, implementation must first document the current export service before locking tests.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| Existing `ExportService` module | Emit export manifest and failure metadata |
| Storage/export helper module, if present | Add/list/read export manifests |
| Activity worker/queue export path | Persist progress/result/failure metadata |
| Admin export/novel API routes | Expose export artifacts and status |
| Admin frontend export UI | Show latest exports, stale state, failures, re-export action |
| `backend/tests/test_export_storage_observability.py` | New focused tests |
| Docs/storage contract | Add export artifact contract section |

### Files Not Touched

- Translation renderer internals, unless needed to emit manifest data.
- Public reader availability policy.
- Translation version storage schema, except read-only use for freshness.
- Crawler/source adapters.

## Export Manifest Contract

Create a manifest per export:

```json
{
  "export_id": "exp_20260708_001",
  "novel_id": "novel-id",
  "format": "epub",
  "status": "succeeded",
  "filename": "Novel Title.epub",
  "storage_key": "exports/epub/exp_20260708_001/Novel Title.epub",
  "file_size_bytes": 123456,
  "sha256": "abc123",
  "created_at": "2026-07-08T00:00:00Z",
  "source_chapter_count": 42,
  "exported_chapter_count": 42,
  "translation_versions": [
    {
      "chapter_id": "1",
      "version_id": "v3"
    }
  ],
  "metadata_revision": "2026-07-08T00:00:00Z",
  "glossary_revision": 12,
  "options": {
    "include_images": true,
    "chapter_range": null,
    "template": "default"
  },
  "stale": false,
  "stale_reasons": []
}
```

If storing every chapter/version pair would make the manifest too large, store a bounded sample plus a hash:

```json
{
  "translation_version_count": 42,
  "translation_versions_hash": "sha256:def456",
  "translation_versions_sample": []
}
```

## Export Statuses

| Status | Meaning |
|---|---|
| `pending` | Export was requested but not started |
| `running` | Export is currently generating |
| `succeeded` | Artifact was written and verified |
| `failed` | Export failed and no valid artifact was produced |
| `deleted` | Artifact was removed by cleanup/delete operation |

## Failure Categories

| Category | Meaning |
|---|---|
| `missing_translation` | A required chapter has no translated content |
| `missing_asset` | Required image or asset is unavailable |
| `render_error` | Renderer failed to generate output |
| `write_error` | Artifact or manifest write failed |
| `invalid_options` | Export request options are invalid |
| `unknown` | Unexpected failure |

Failure metadata:

```json
{
  "status": "failed",
  "failure_category": "missing_translation",
  "failure_message": "Chapter 12 has no active translated version.",
  "failed_at": "2026-07-08T00:00:00Z"
}
```

Do not store full chapter text or stack traces in manifest/activity metadata.

## Storage Strategy

Implementation must inspect current export paths first.

Preferred manifest placement:

```text
<novel-dir>/exports/<format>/<export-id>/manifest.json
<novel-dir>/exports/<format>/<export-id>/<artifact-file>
```

If existing export service uses a different path, keep existing artifact path and place manifest next to the artifact or in an export metadata directory.

Rules:

- Do not break existing download routes.
- Use existing storage helper APIs when available.
- Write manifest atomically if atomic storage helper exists.
- Temporary render files should stay out of listed exports.

## Freshness Detection

An export is stale when any of these are true and data is available:

- current active translation version for an exported chapter differs from manifest version,
- novel metadata updated after export's recorded metadata revision,
- glossary revision is newer than manifest glossary revision,
- export options/template version changed.

Helper:

```python
def compute_export_freshness(
    manifest: dict[str, Any],
    current_state: ExportInputState,
) -> tuple[bool, list[str]]:
    ...
```

Stale reasons:

- `translation_version_changed`
- `metadata_changed`
- `glossary_revision_changed`
- `export_options_changed`
- `unknown_legacy_manifest`

Staleness does not delete or invalidate download access automatically.

## Activity Metadata Integration

During export activity:

```json
{
  "export": {
    "export_id": "exp_20260708_001",
    "format": "epub",
    "status": "running",
    "progress": {
      "completed": 10,
      "total": 42,
      "current_label": "Chapter 10"
    }
  }
}
```

On success:

```json
{
  "export": {
    "status": "succeeded",
    "manifest_path": ".../manifest.json",
    "artifact_path": ".../Novel Title.epub",
    "file_size_bytes": 123456
  }
}
```

On failure:

```json
{
  "export": {
    "status": "failed",
    "failure_category": "render_error",
    "failure_message": "EPUB renderer failed."
  }
}
```

## Admin API Design

Add or extend admin export endpoints.

Examples:

```http
GET /admin/novels/{novel_id}/exports
GET /admin/novels/{novel_id}/exports/latest
```

Response:

```json
{
  "novel_id": "novel-id",
  "exports": [
    {
      "export_id": "exp_20260708_001",
      "format": "epub",
      "status": "succeeded",
      "created_at": "2026-07-08T00:00:00Z",
      "file_size_bytes": 123456,
      "stale": true,
      "stale_reasons": ["translation_version_changed"]
    }
  ],
  "latest_by_format": {
    "epub": "exp_20260708_001"
  }
}
```

If an export endpoint already exists, extend it rather than adding duplicates.

## Admin UI Design

Export panel on novel/admin page:

- list latest export per format,
- show status badge,
- show created time and file size,
- show stale badge and reason,
- show failure category/message,
- show re-export action using existing export flow,
- show download/open action if current UI already supports it.

## Legacy Export Handling

Existing exports without manifests:

- remain downloadable if current routes support them,
- appear as `legacy` or `unknown` in admin list if discoverable,
- can be marked stale with reason `unknown_legacy_manifest`,
- should not be rewritten automatically.

## Test Design

Create `backend/tests/test_export_storage_observability.py`.

Backend tests:

- export writes artifact and manifest,
- manifest includes format, file size, chapter count, and version summary,
- latest export per format is discoverable,
- stale detection after active translation version changes,
- stale detection after metadata/glossary revision changes where available,
- missing translation failure is classified,
- write/render failure is classified using mocks,
- legacy export artifact remains accessible,
- admin API exposes export metadata,
- public API does not expose unpublished export artifact.

Frontend tests if UI changes:

- latest export status renders,
- stale reason renders,
- failed export message renders,
- re-export action triggers existing export flow.

## Migration and Backward Compatibility

- Existing export files remain valid.
- Existing download routes remain valid.
- Manifests are additive.
- Legacy exports without manifests remain accessible if currently accessible.
- No public reader behavior changes.
- No export format redesign.

## Acceptance Criteria

1. Export service writes a manifest for completed exports.
2. Manifest records output artifact, format, file size, chapter count, and input version state where available.
3. Export activity metadata exposes progress, success artifact, or safe failure category/message.
4. Admin APIs list exports and latest export per format.
5. Admin UI shows status, stale state, failures, and re-export action.
6. Existing export/download behavior remains compatible.
7. Public APIs do not expose unpublished export artifacts.
8. Focused backend and frontend tests pass.

