# Runtime storage

This directory is disposable local runtime space. It is not the novel library
and it is not a production content store.

Canonical novel artifacts are stored in Cloudflare R2 bucket `dokushodo`.
Incremental recovery material is stored in `dokushodo-backup`. PostgreSQL owns
novel identity, catalog state, and exact object references; Redis/Valkey owns
short-lived coordination. See [`../docs/STORAGE.md`](../docs/STORAGE.md).

The runtime root may contain temporary fetch/translation caches, checkpoints,
logs, worker scratch files, and other prunable state. It must never contain
canonical chapter, translation, generation, media, or asset data and must not
be served directly by the frontend.

Do not commit or manually delete runtime files as part of a cutover. Use the
R2 inventory, migration, backup, verification, and garbage-collection
procedures in [`../docs/OPERATIONS.md`](../docs/OPERATIONS.md).
