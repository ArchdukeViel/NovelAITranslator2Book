# Storage

Canonical persistence, artifact, schema, and restore contract for the Cloudflare R2-only
content cutover.

## Ownership

| Domain | Canonical store | Derived or disposable |
|---|---|---|
| Novel identity, source/public URLs, publication state, chapter identity/order, active generation | PostgreSQL | None |
| Raw chapters, translations, media, generation manifests, deduplicated assets | R2 bucket `dokushodo` | PostgreSQL exact references and hashes |
| Users, sessions, glossary, reviews, requests, credentials, audit, jobs, usage | PostgreSQL | Encrypted database recovery dumps |
| Queues, leases, locks, rate limits, quota reservations | Redis/Valkey | None |
| Fetch/translation caches, logs, checkpoints, worker scratch | `RUNTIME_DIR` | Disposable and prunable |
| Object backups and snapshot manifests | R2 bucket `dokushodo-backup` | None |

The application has no filesystem content backend, configurable storage
selector, or legacy content namespace. R2 is accessed through storage
services; normal API and reader requests never list an R2 prefix. Tests use an
in-memory R2-compatible double, while local disk is reserved for disposable
runtime state and never acts as canonical content storage.

## Application bucket layout

Application keys begin directly with `novels/`:

```text
dokushodo/
  novels/<novel_id>/
    generations/<generation_id>.json.gz
    chapters/<chapter_id>/<source_hash>.json.gz
    translations/<chapter_id>/<translation_hash>.json.gz
    media/<chapter_id>/<media_hash>.json.gz
    assets/<sha256>.<ext>
```

There is no `novels/index.json`, active-generation pointer, translation-active
pointer, metadata backup, runtime state, cache, log, activity, checkpoint,
lock, or temporary provider object in this bucket. The generation manifest is
small and references shared chapter, translation, media, and asset keys; it
does not duplicate a complete directory tree.

## Content addressing and writes

Logical JSON is normalized with stable key ordering, NFC Unicode, LF line
endings, compact UTF-8 encoding, and volatile timestamps excluded. SHA-256 is
computed over the uncompressed logical bytes. JSON artifacts use deterministic
gzip (`mtime=0`), `Content-Type: application/json`, and
`Content-Encoding: gzip`. Assets use their byte SHA-256 in the key and are
stored without content encoding.

Immutable writes are idempotent: an existing key is accepted only when its
logical checksum and bytes agree; a same-key conflict fails. Small immutable
artifacts use `R2Storage.put_immutable()`. Streamed assets use
`R2Storage.save_stream()`, which delegates to a bounded boto3 transfer
configuration (8 MiB multipart threshold/chunks and four workers), requests a
provider SHA-256 checksum, and HEAD-verifies the committed length. A declared
length mismatch removes the just-written object before failing. All R2 writes
use bounded timeouts/retries and explicit missing/permission/conflict
classification. The service records operation count, bytes, latency,
checksum, reuse, and error metrics without recording credentials or content.

## PostgreSQL activation

`Novel.active_generation_id` and `Novel.active_generation_storage_key` are the
only active-generation truth. `Chapter` stores exact raw, translated, media
keys and logical hashes. Publication proceeds in this order:

1. Upload or reuse immutable chapter/media/asset artifacts.
2. HEAD-verify every manifest reference by exact key.
3. Upload the small generation manifest.
4. Lock the PostgreSQL novel row and check the expected active generation.
5. Update the active generation and chapter references in one transaction.
6. Invalidate derived catalog/reader caches after commit.

A failed verification or optimistic-concurrency check leaves the prior
PostgreSQL activation unchanged. An uploaded but unactivated manifest is an
orphan eligible for grace-period GC. Readers load the exact keys persisted in
PostgreSQL and return unavailable/404 rather than reconstructing or listing
storage paths.

## Translation, media, and assets

Every raw or translated revision is immutable and content-addressed. Editing a
translation creates a new hash object and changes only the PostgreSQL active
reference. Selective invalidation is based on source hash, glossary hash,
prompt version, and translation identity. Media state is an immutable
content-addressed artifact with a PostgreSQL reference; normalized asset bytes
are reused by SHA-256 across chapters and generations.

## Backup bucket layout

```text
dokushodo-backup/
  objects/novels/<novel_id>/{chapters,translations,media,generations,assets}/...
  snapshots/<snapshot_id>/manifest.json
  database/<timestamp>/{database.dump.zst.enc,manifest.json}
  migrations/<migration_id>/{source-state.json,application-manifest.json,
                             backup-manifest.json,verification.json}
```

Object backups are incremental: immutable objects are copied once under
`objects/novels/...`, and later snapshot manifests reference the existing
backup object. Database dumps are encrypted independently. Application
source-read and backup-write credentials are separate from each other and
from application credentials. Retention is bounded by configured manifest
count/age and uses `BACKUP_SAFETY_GRACE_DAYS` before collecting an unreferenced
shared object.

## Garbage collection and deletion

GC is mark-and-sweep over the fully paginated `novels/` namespace. The mark
set includes PostgreSQL references, the active generation, protected rollback
generations, committed backup manifests, and in-progress work. Unmarked
objects must remain past the configured grace period (7 days initially) before
deletion. Dry-run is the default. Novel deletion is a PostgreSQL state
transition followed by backup confirmation and a separate object sweep; it is
never an implicit prefix delete from a request path.

## Clean cutover

The hard cutover preserves the three existing novel IDs, slugs, public URLs,
source URLs, and publication states. Before any destructive action, operators
must freeze writers, inventory both buckets, preserve and verify the identity
manifest, and create an independent backup. The reset tool is dry-run by
default and refuses execution without the exact bucket names, writer-freeze
evidence, identity verification, and the explicit reset confirmation token.
The backup bucket is emptied before the application bucket; both buckets are
kept, verified empty, repopulated, and checked through the old public URLs.

## Runtime boundary and restore

Local disk contains only `RUNTIME_DIR` caches, logs, checkpoints, locks, and
temporary staging. It is disposable and is never served as content. Redis is
transient coordination; PostgreSQL remains the mutable application truth.

Restore order is: verify a committed backup manifest and checksums; restore
the application objects; restore the encrypted PostgreSQL dump into a clean
database; verify exact key references and active generation; rebuild derived
projections if required; then run health, public reader, authentication,
takedown, and representative URL checks. R2 lifecycle rules and bucket locks
are not backups.
