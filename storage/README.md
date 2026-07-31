# Storage

Runtime files live here during local development and production-style deployments.

- `novel_library/`: private backend runtime data: novel metadata, chapter JSON,
  assets, runtime caches, activity logs, scheduler state, and traceability.
  Layout, ownership, and restore contract live in
  [`../docs/STORAGE.md`](../docs/STORAGE.md).
- `novel_library/novels/`: canonical novel folders, one per novel by
  storage slug. Each contains `metadata.json`, bounded `metadata_backups/`,
  `chapters/<chapter_id>.json`, and chapter-scoped asset directories.
  `novels/index.json` maps logical novel IDs and source IDs to those folders.
- Source-derived caches, fetch and translation caches, activity logs, and
  scheduler state live under dedicated runtime roots inside `novel_library/`.
  They are disposable/prunable per [`../docs/OPERATIONS.md`](../docs/OPERATIONS.md)
  and never become canonical content.

These runtime subfolders are ignored by git. Configure `NOVEL_LIBRARY_DIR`
when production should mount a different disk or volume.

Do not commit runtime data from this folder unless it has been intentionally
sanitized and documented as a fixture or example. `storage/novel_library` is
private backend runtime data and must not be served directly by the frontend
or static file hosting. Generated translated-novel downloads are out of scope;
see [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the product boundary.
