# Runtime storage

Disposable local runtime space lives at `data/runtime/`. It is not the novel
library and it is not a production content store. Git ignores the complete
directory. Compose mounts that host path to `/app/data/runtime` inside the
containers through `RUNTIME_HOST_DIR`. The container path and host path are
different on purpose.

Canonical novel artifacts are stored in Cloudflare R2 bucket `dokushodo`.
Incremental recovery material is stored in `dokushodo-backup`. PostgreSQL owns
novel identity, catalog state, and exact object references; Redis/Valkey owns
short-lived coordination. See [`../docs/STORAGE.md`](../docs/STORAGE.md).

The runtime root may contain temporary fetch/translation caches, checkpoints,
logs, worker scratch files, and other prunable state. These files must never be
treated as canonical chapter, translation, generation, media, or asset data and
must not be served directly by the frontend. The current checkpoint service
deliberately writes temporary recovery copies of the raw chapter,
translated-chapter payload, and chapter state into each checkpoint JSON file.
Those copies are private, disposable recovery material; PostgreSQL references
and R2 objects remain authoritative.

The implementation-managed layout is approximately:

```text
data/runtime/
  chapter-state/<novel-id>/<encoded-chapter-id>.json
  checkpoints/<novel-id>/<encoded-chapter-id>__<checkpoint-name>.json
  translation_cache/<shard>/<entry>.json
  traceability/       # pipeline evidence
  translation/        # temporary pipeline state
```

Chapter-state files are one small JSON record per stable chapter identity. The
record contains `chapter_id`, `current_state`, `transitions`, `last_updated`,
`error_count`, and `retry_count`; filesystem names encode unsafe logical ids
without changing the logical id used by the application. Checkpoint files are
larger because they bundle recovery payloads and state. This per-chapter layout
is clear and appropriate for local recovery, but a large catalog will eventually
need stronger checkpoint retention/compaction and preferably reference-based or
R2-backed checkpoint payloads to reduce duplicate content, inode count, and
directory scans. That is a scale follow-up, not a reason to treat local runtime
files as canonical storage.

Do not commit or manually delete runtime files as part of a cutover. Use the
R2 inventory, migration, backup, verification, and garbage-collection
procedures in [`../docs/OPERATIONS.md`](../docs/OPERATIONS.md).
