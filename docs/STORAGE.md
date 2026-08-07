# Storage

Canonical persistence, artifact, schema, and restore contract.

## Ownership

| Domain | Canonical store | Derived/rebuildable |
|---|---|---|
| Novel metadata, raw chapter bodies, staged raw generations, image assets | Storage backend | PostgreSQL catalog rows |
| Translation overlay (active version + edit history + version blobs) | Storage backend | None |
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

S3/R2 uses `S3_KEY_PREFIX=storage/novel_library` by default. Canonical object
keys therefore begin with `storage/novel_library/novels/`, matching the local
library namespace without writing application objects at bucket root.

## Layout

```text
<library>/
  novels/
    index.json
    <storage_slug>/
      metadata.json                          # raw metadata snapshot
      metadata_backups/<timestamp>.json      # bounded retention
      chapters/<encoded-chapter-stem>.json  # raw chapter bundle (byte-immutable once a generation is active)
      assets/images/<encoded-chapter-stem>/<file>  # raw images, generation-scoped when an active generation exists
      media/<encoded-chapter-stem>.json     # media overlay (media_overlay_v1): mutable OCR/reembed state
      generations/<generation_id>/          # staged raw generation snapshot
        metadata.json
        chapter_index.json
        source_state.json
        chapters/<encoded-chapter-stem>.json
        assets/images/...
        generations/<this-id>.json          # manifest (committed last; contains hashes + chapter_ids)
      translations/                          # mutable translation overlay
        <encoded-chapter-stem>.json         # overlay: translation_versions, active_translation_version_id, edit_history, chapter_id
        active/<encoded-chapter-stem>.json  # active-version pointer mirror
      active_generation.json                # {novel_id, active_generation_id, activated_at}
  runtime/ and cache families owned by their services
```

Public `slug`, storage folder slug, `novel_id`, and `source_novel_id` are separate
concepts. Never build paths from public identifiers outside storage helpers.

## Novel Metadata

`metadata.json` owns `novel_id`, title/translated title, author fields, chapter
list, origin/document/input-adapter context, publication metadata, timestamps,
and schema version. Previous valid metadata is retained under
`metadata_backups/` with bounded retention.

## Immutable Raw Generations + Translation Overlay

Committed raw generation artifacts are **byte-immutable**. Every translation,
retranslation, manual edit, or QA retry writes to the per-chapter translation
overlay — never to the raw chapter bundle. Readers compose the active raw
generation with the active translation overlay on read.

### Raw bundle

`chapters/<encoded-chapter-stem>.json` holds only the raw ingestion output:

- raw id, text, paragraphs, images, source provenance, scrape time;
- media/region reference data;
- schema version.

Mutable OCR/re-embedding state is not part of the raw bundle; it lives in the
novel-root media overlay (see below). Legacy bundles that still carry OCR
fields remain readable; the overlay wins when both exist.

While a generation is active, raw bundle writes are **refused**, not silently
rewritten: `persist_chapter_bundle` raises, document imports are rejected,
checkpoint raw restores skip the raw section, and the rollback bundle-pop
path is gated to the no-generation flow. Translation and media writes never
touch the bundle either.

### Translation overlay

`translations/<encoded-chapter-stem>.json` holds:

- `chapter_id` (stable logical id used everywhere downstream);
- `translation_versions` — append-only ordered list with version id, kind,
  provider/model, created/translated timestamps, text/paragraphs, source/
  glossary/cache/QA metadata, attempt number;
- `active_translation_version_id`;
- `edit_history` — append-only ordered list (`id` uses the `e{N}` convention;
  `action` ∈ `manual_edit` / `rollback`; `version_id` /
  `previous_version_id` / `editor` / `note` / `created_at`);
- `prompt_template_version`, `glossary_hash`.

The active pointer lives at `translations/active/<encoded-chapter-stem>.json`
and mirrors `active_translation_version_id`.

Activating a version changes the pointer and appends to history; it does not
delete old versions. Readers compose raw + overlay at read time so removing
the overlay (rollback) restores the raw feed without losing prior versions.

Legacy bundles that still carry `translation_versions` inside the raw chapter
bundle continue to be readable as a fallback; the overlay wins when both
exist. After the first `save_translated_chapter` against a legacy novel, the
overlay becomes authoritative and the bundle is no longer touched by
translation writes.

### Media overlay

`media/<encoded-chapter-stem>.json` holds the novel-root mutable OCR state
(schema `media_overlay_v1`):

- `ocr_required`, `ocr_text`, `ocr_pages`, `ocr_status`, `reembed_status`.

It is novel-root, not generation-scoped, so OCR/re-embedding progress
survives re-activation. Readers (`load_chapter`, `load_chapter_media_state`,
`load_translated_chapter`) compose raw bundle + media overlay + translation
overlay at read time; the media overlay wins over legacy bundle OCR fields.
Asset resolution under an active generation stays inside the staged
generation — `resolve_asset_path` has no legacy-root fallback there.

### Generation activation contract

Each `generations/<gen-id>/` directory holds a complete raw snapshot staged
before activation:

1. `metadata.json`, `chapter_index.json`, `source_state.json`;
2. `chapters/<encoded-chapter-stem>.json` bundles for every chapter the index
   declares;
3. asset bytes under `assets/images/<encoded-chapter-stem>/<file>`;
4. `generations/<this-id>.json` manifest with serialized hashes
   (`metadata_hash`, `chapter_index_hash`, `source_state_hash`) and final counts
   (`expected_chapters`, `saved_chapters`, `reused_chapters`, `failed_chapters`,
   `carried_unselected_count`, `unavailable_chapter_ids`, `removed_episode_ids`).
   Every current-index chapter ends with exactly one canonical disposition:
   `fetched_new`, `fetched_replaced`, `reused_planner`, `carried_unselected`,
   `unchanged_selected`, `refresh_failed_retained`, or `unavailable`.
   Aggregate counts are derived from the disposition map and must reconcile
   with the physical staged state.

`commit_generation` runs `validate_generation_activation` before swapping
`active_generation.json`. The validator checks:

- manifest status is `staging`;
- metadata identity matches `manifest.source_work_id`;
- every indexed chapter has a bundle, **or** an explicit
  `unavailable_chapter_ids` / `refresh_failed_chapter_ids` entry;
- index entry ids are normalized exactly like `resolve_chapter_selection`
  (integer ids become strings) before reconciliation; a normalized id with
  no physical bundle still fails;
- `source_state.json` exists in the stage;
- every referenced image resolves inside the staged generation (never in
  legacy root, never in another generation);
- manifest hashes are non-empty and match the staged file contents
  byte-for-byte;
- `manifest.chapter_ids` reconcile with the physical bundles the index
  declares (not with index entries alone);
- counts reconcile (`saved_chapters`, `reused_chapters`,
  `unavailable_chapter_ids`, `refresh_failed_chapter_ids`, `failed_chapters`,
  `expected_chapters`, `carried_unselected_count`);
- every current-index chapter has exactly one disposition in `manifest.chapter_dispositions`;
- disposition map agrees with explicit `unavailable_chapter_ids` and
  `refresh_failed_chapter_ids` lists;
- derived counts from dispositions match manifest aggregate counters.

A failed validation rolls the stage back; the previously active pointer (or
legacy root when no generation was active) remains in effect. Operators can
invoke `commit_generation_recovery(reason=..., evidence=...)` only for explicit
recovery paths. After activation, `generations/<gen-id>/` is byte-immutable.

Generation activation uses a cross-process compare-and-swap on `active_generation.json`: the filesystem backend wraps the read-compare-write in an `InterProcessFileLock`; the S3 backend uses a conditional `PUT` with `If-Match`/`If-None-Match` so concurrent activations cannot silently overwrite each other (loser receives `GenerationConflictError`).

## Episode Order & Removal State

`source_state.json` per generation persists an explicit `ordered_episode_ids`
list matching the complete current index. Per-episode entries carry:

- `chapter_id`, `source_episode_id`, `sequence_number`;
- `source_availability` ∈ `active` / `missing_from_current_index`;
- `first_seen_at`, `last_seen_at`, `missing_since`;
- `source_update_date`, `content_hash`, `structure_hash` (when known).

Episodes absent from the current index become
`source_availability == "missing_from_current_index"` rather than being deleted;
raw and translated history is retained. On reappearance, `missing_since` is
cleared and the episode is marked `active`. After a single crawl with stable
order, no further `reordered_episode_ids` / `removed_episode_ids` delta is
produced.

## Image Asset Ownership

When an active generation exists, image bytes live under
`generations/<gen-id>/assets/images/<encoded-chapter-stem>/<file>`. Carrying a
chapter from generation A into a fresh generation B copies those assets
through `seed_generation_from_active` so B's bundle resolves the image without
falling back to legacy root or generation A. Deletion of A (or a legacy root
fallback) must not break B's image resolution; if a referenced image is
missing on disk the manifest's pre-activation validation rejects the stage
rather than falling back.

## Edit History

Append-only ordered list. `id` uses the `e{N}` convention. `action` ∈
`manual_edit` / `rollback`. Each entry carries `version_id`,
`previous_version_id`, `created_at`, and optional `editor` / `note`. Manual
edits and version-rollback activations both append entries; raw rolls,
imports, or schema migrations do not.

## PostgreSQL Projections

SQL `Novel` and `Chapter` rows provide searchable/catalog workflow projections.
Storage owns chapter content and canonical counts. Rebuild stale projections
through catalog refresh, not manual SQL edits.

The `chapters` table carries stable-identity columns (`logical_chapter_id`,
`source_episode_id`, `sequence_number`) per the migration
`c7a8b9d0e1f2_add_stable_chapter_identity`. Lookups prefer
`logical_chapter_id` and fall back to `chapter_number` when the column is
absent (legacy rows).

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
- Cross-actor translations writes land in the per-chapter overlay under the
  novel-level inter-process lock so two writers cannot publish a partial
  version set.

## Backup Contract

- Filesystem backup and R2 snapshots are independently restorable copies.
- R2 snapshot manifest is written last after inventory, ETag checks, byte count,
  and SHA-256 verification.
- Source-read and target-write credentials remain separate.
- Database dumps are encrypted independently from object snapshots.
- Retention never removes newest successful backup or configured minimum.
- Lifecycle rules and bucket locks do not substitute for backups.
- A snapshot of an active generation is a complete raw snapshot plus the
  novel-level active pointer; translation overlays are recoverable from
  activation history, media overlays are separate novel-root state, and
  neither is derivable from raw generation bytes.

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
- Re-activating a generation requires the same staging + validation flow that
  first built it; manual edits to `active_generation.json` will be overwritten
  on the next crawl.
