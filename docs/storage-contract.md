# Storage Contract

This document is the canonical reference for the file/JSON storage contract. It
describes *where* artifacts live and *what* they contain. It does **not** change
any layout or schema; it documents the current behavior so migrations, backups,
repair tools, and refactors have an explicit contract to test against.

## Backend-specific behavior

R2/S3 is the canonical persisted storage backend when `STORAGE_BACKEND=s3` is
configured. Object-store directories are **virtual prefixes** — there is no
directory-marker object.

Storage-aware code must use the storage abstraction (`StorageService._is_dir_present`,
`_path_exists` for exact files) rather than direct `Path.exists()` or `Path.is_dir()`
calls. SQL `chapter_count` and `translated_count` are cached catalog projections, not
authoritative. Authoritative counts come from `StorageService.count_stored_chapters()`
and `StorageService.count_translated_chapters()` against R2/S3.

Canonical high-volume artifacts live on the filesystem under `storage/novel_library`
(the configured `DATA_DIR`, resolved by `StorageService`). PostgreSQL stores
relational state and projections derived from these files.

## Canonical vs Derived State

### Ownership Matrix

| Domain | Canonical store | Derived/rebuildable | Notes |
|---|---|---|---|
| Novel metadata, raw chapters, translated versions, edit history, image assets | File storage (canonical) | PostgreSQL `Novel`/`Chapter` rows | Source of truth for content. SQL rows are projections used for catalog indices. |
| Users, sessions, auth identities | PostgreSQL | None | Primary authentication tables. |
| Glossary, reviews, novel requests, provider credentials, audit logs | PostgreSQL | None | Related storage exports may copy data, but Postgres is authoritative. |
| Runtime cache, pipeline events, activity logs, scheduler state | Storage runtime files | None | Transient logs. Prunable and disposable. |
| Exports, export manifests, full backups | Storage backend | None | Historical output artifacts. |

### Restore Rules
When performing a database or system restore, the following sequence must be respected:
1. **Restore Storage Backend First:** Deploy canonical filesystem or S3 artifacts back to the target directory.
2. **Restore PostgreSQL Tables Second:** Deploy dump files for database-owned domains (users, credentials, glossary, audits).
3. **Rebuild Catalog Projections Third:** Trigger `catalog_service.refresh_catalog_projection` to reconstruct relational `Novel` and `Chapter` tables entirely from the restored storage files.
4. **Verify Manifests Fourth:** Enumerate and load the restored export and backup manifest JSON records to align runtime indexes.

## Artifact Index

| Artifact | Canonical? | Storage owner | Writer | Reader | Notes |
|---|---:|---|---|---|---|
| Novel metadata | Yes | File storage | `save_metadata` | `load_metadata` | Includes chapter list and translated metadata fields |
| Metadata backup | Backup | File storage | backup helper (`save_metadata`) | `list_metadata_history`, `load_metadata_snapshot` | Timestamped snapshots under `metadata_backups/` |
| Raw chapter bundle | Yes | File storage | `save_chapter` | `load_chapter` | Raw text, paragraphs, images, source provenance |
| Chapter image asset | Yes | File storage | `save_chapter_image_asset` | chapter/image loaders | Binary asset plus manifest fields |
| Translated version bundle | Yes | File storage | `save_translated_chapter`, `save_edited_translation` | `load_translated_chapter`, `list_translated_chapter_versions` | Active and historical versions |
| Edit history | Yes | File storage | `save_edited_translation`, `activate_translated_chapter_version` | `load_translation_edit_history` | Human edits and rollbacks |
| SQL novel/chapter rows | Projection | PostgreSQL | catalog refresh / DB services | query APIs | Searchable status and workflow state |

## Novel Metadata

Path: `<novel_dir>/metadata.json`. Written by `save_metadata`, read by
`load_metadata`. Required/key fields:

- `novel_id` (str)
- `title` (str), optional `translated_title`
- `chapters` (list of `{id, num, title, url}`)
- `origin_type`, `origin_uri_or_path`, `document_type`
- `input_adapter_key`, `context_group_id`
- `schema_version` (set by writer), `scraped_at`, `updated_at`

Optional: `source_language`, `author`/`translated_author`, `publication_status`,
`translation_profiles`, `translation_defaults`, `titles`, `authors`.

## Metadata Backups

Path: `<novel_dir>/metadata_backups/<timestamp>.json`. On every `save_metadata`,
the previous `metadata.json` is copied into this dir. Backups are named from
`updated_at` and pruned to `METADATA_BACKUP_RETENTION` (5). Sorted newest-first
by filename. Read via `list_metadata_history` / `load_metadata_snapshot`.

## Raw Chapter Bundles

Path: `<novel_dir>/chapters/<chapter_id>.json`. Written by `save_chapter`, read
by `load_chapter`. The chapter bundle is a unified file containing `raw` (and,
optionally, `translated`) content. Legacy `raw/<id>.json` / `translated/<id>.json`
are still loaded as a fallback.

Required `raw` fields:

- `id` (str)
- `scraped_at` (ISO timestamp)
- `text` (str)
- `paragraphs` (list[str])
- `images` (list)

Optional `raw` fields: `source_blocks`. Provenance fields on the bundle:
`source_key`, `source_url`, `origin_type`, `document_type`, `input_adapter_key`,
`context_group_id`, `unit_type`, `import_order`, plus OCR/media fields
(`ocr_required`, `ocr_status`, `reembed_status`, `region_metadata`, `ocr_artifacts`).

Callers must not construct the chapter path manually; use `save_chapter` /
`load_chapter` (paths are helper-owned).

## Chapter Image Assets

Binary assets live under `<novel_dir>/assets/images/<chapter_id>/<index>.<ext>`.
Written by `save_chapter_image_asset`, cleared by `clear_chapter_image_assets`.
The manifest entry (stored in the chapter bundle's `raw.images`) carries:

- `source_url` (original image URL)
- `local_path` (relative asset path)
- `content_type`, `size_bytes`, `sha256`
- `download_error` (present when image download failed)

Image bytes themselves have no JSON schema; only the manifest entry is
contractual.

## Translated Chapter Versions

Translated versions live inside the same unified chapter bundle
(`<novel_dir>/chapters/<chapter_id>.json`) under `translation_versions`, with the
active version referenced by `active_translation_version_id` (and mirrored into
`translated`). Written by `save_translated_chapter` / `save_edited_translation`,
activated by `activate_translated_chapter_version`.

Version fields:

- `id` (str)
- `kind` (`mt` / `manual_edit` / etc.)
- `provider`, `model`
- `created_at` / `translated_at` (ISO timestamps)
- `text`, `paragraphs`
- `active` (boolean, exposed by `list_translated_chapter_versions`)
- optional: `editor`, `note`, `base_version_id`, `source_hash`,
  `confidence_score`, `glossary_revision`, `glossary_hash`, `batch_id`, QA fields

Activating a version changes the active pointer and appends an edit-history entry;
older versions are **never deleted** by activation.

## Translation Edit History

Path: `edit_history` list inside the chapter bundle. Written by
`save_edited_translation` and `activate_translated_chapter_version`, read by
`load_translation_edit_history`. Each entry:

- `id` (str)
- `action` (`manual_edit` / `rollback`)
- `version_id`, optional `previous_version_id`
- `created_at`
- optional `editor`, `note`, `batch_id`

## PostgreSQL Projection Relationship

- The SQL `Novel` row owns relational/searchable metadata; the file `metadata.json`
  owns the canonical chapter list and translated metadata fields.
- The SQL `Chapter` row owns status / storage-key projection; the file
  `chapters/<id>.json` owns the raw and translated content bundles.
- Glossary lives entirely in SQL, separate from file translation artifacts.
- For stale SQL projection rows, prefer `catalog_service.refresh_catalog_projection`
  (best-effort rebuild from canonical files) over manual DB edits.

## Compatibility Rules

- Loaders tolerate additive fields.
- Missing optional fields receive existing default behavior.
- Required fields must be present in newly written artifacts.
- Legacy artifacts load if they match supported historical shapes
  (`raw/` / `translated/` fallback, legacy metadata fields).
- SQL projection state can be rebuilt from canonical file storage where existing
  code supports it.

## Storage Backends

Canonical high-volume artifacts can be stored on:

| Backend | Setting | Notes |
|---|---|---|
| Local filesystem | `STORAGE_BACKEND=filesystem` (default) | `NOVEL_LIBRARY_DIR` is the base path. Backups via `BackupManager` (tar.gz). |
| Cloudflare R2 | `STORAGE_BACKEND=s3` with `S3_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com` | S3-compatible via boto3. Requires `S3_ACCESS_KEY_ID` + `S3_SECRET_ACCESS_KEY`. R2 lifecycle rules replace local backups. |
| AWS S3 | `STORAGE_BACKEND=s3` without `S3_ENDPOINT` | Uses IAM role credentials. Standard S3 API. |

All storage backends implement the same `StorageBackend` interface. R2 and S3 differences are handled by the `S3Backend` class — callers never touch boto3 directly.

## Migration and Repair Notes

- Do not edit canonical JSON by hand unless backups are available.
- Use storage service helpers for migrations instead of constructing paths ad hoc.
- For corrupted metadata, prefer the latest valid metadata backup.
- For stale SQL projection rows, prefer catalog projection refresh.
- Translation versions should not be deleted manually unless active-version
  pointers are also repaired.
