# Storage

Canonical persistence, artifact, schema, and restore contract.

## Ownership

| Domain | Canonical store | Derived/rebuildable |
|---|---|---|
| Novel metadata, raw chapters, translated versions, edit history, assets | Storage backend | PostgreSQL catalog rows |
| Users, sessions, identities | PostgreSQL | None |
| Glossary, reviews, requests, credentials, audit | PostgreSQL | Recovery dumps only |
| Jobs and durable scheduler runtime state | PostgreSQL | In-process/file cache where documented |
| Fetch/translation cache, pipeline events, activity logs | Runtime storage | Disposable/prunable |
| Backups and backup manifests | Independent recovery storage | None |
| Historical generated files | Storage backend | Preservation only; no writer/listing/download API |

Storage backend is filesystem by default or S3-compatible when
`STORAGE_BACKEND=s3`. R2 directories are virtual prefixes. Callers use storage
abstractions and never inspect boto3 clients, buckets, roots, or `Path` state for
object-store data.

## Layout

```text
<library>/
  novels/
    index.json
    <storage_slug>/
      metadata.json
      metadata_backups/<timestamp>.json
      chapters/<chapter_id>.json
      assets/images/<chapter_id>/<index>.<ext>
  runtime/ and cache families owned by their services
```

Public `slug`, storage folder slug, `novel_id`, and `source_novel_id` are separate
concepts. Never build paths from public identifiers outside storage helpers.

## Novel Metadata

`metadata.json` owns `novel_id`, title/translated title, author fields, chapter
list, origin/document/input-adapter context, publication metadata, timestamps,
and schema version. Previous valid metadata is retained under
`metadata_backups/` with bounded retention.

## Chapter Bundle

`chapters/<chapter_id>.json` is unified source/translation artifact:

- raw ID, text, paragraphs, images, source provenance, scrape time;
- `translation_versions` with version ID, kind, provider/model, timestamps,
  text/paragraphs, source/glossary/cache/QA metadata;
- `active_translation_version_id` and active translated projection;
- append-only edit/rollback history.

Activating a version changes pointer and appends history; it does not delete old
versions. Raw scraped chapters remain audit data after translation.

## Assets

Image bytes live under the chapter asset prefix. Chapter image manifests carry
source URL, relative local key, content type, size, checksum, and download error.
APIs never expose raw filesystem paths or unrestricted storage keys.

## PostgreSQL Projections

SQL `Novel` and `Chapter` rows provide searchable/catalog workflow projections.
Storage owns chapter content and canonical counts. Rebuild stale projections
through catalog refresh, not manual SQL edits.

## Forward-Only Schemas

- Versioned artifacts carry exact supported `schema_version`.
- Older, newer, unversioned, or invalid artifacts fail closed and are never
  rewritten implicitly.
- Additive fields may be tolerated only within current schema contract.
- Schema changes update writer, reader, tests, docs, and explicit migration together.
- No dual-read/dual-write compatibility window or legacy directory probing.

## Concurrency and Safety

- Atomic writes use temp file plus replace and canonical inter-process lock where required.
- Path validation rejects traversal, roots, project roots, and symlink escape.
- Object writes use storage-prefix semantics, not directory-marker assumptions.
- Library summary and similar caches are derived, bounded, invalidated after
  mutations, and never become canonical content.

## Backup Contract

- Filesystem backup and R2 snapshots are independently restorable copies.
- R2 snapshot manifest is written last after inventory, ETag checks, byte count,
  and SHA-256 verification.
- Source-read and target-write credentials remain separate.
- Database dumps are encrypted independently from object snapshots.
- Retention never removes newest successful backup or configured minimum.
- Lifecycle rules and bucket locks do not substitute for backups.

## Restore Order

1. Verify committed backup and checksums in isolated target.
2. Restore canonical storage.
3. Restore PostgreSQL-owned data into clean DB.
4. Rebuild SQL catalog projections from storage.
5. Verify backup manifests and representative content.
6. Run health, smoke, reader, auth, and takedown checks.

Operational commands live in [`OPERATIONS.md`](OPERATIONS.md).

## Repair Rules

- Do not hand-edit canonical JSON without verified backup.
- Use service helpers; never construct canonical paths ad hoc.
- Recover metadata from newest valid backup.
- Repair stale SQL through projection refresh.
- Never delete translation versions without repairing active pointers/history.
- Preserve historical generated artifacts; runtime no longer indexes or serves them.
