# Storage

Runtime files live here during local development and production-style deployments.

- `novel_library/`: private backend runtime data: novel metadata, chapter JSON, images, preferences, translation/fetch cache, usage logs, activity logs, scheduler state, provider request records, runtime traceability, and exports.
- `novel_library/novel/{storage_slug}/`: canonical title-slug layout for new novel saves.
- `novel_library/novels/`: legacy source-ID folders plus `index.json`, which maps logical novel IDs/source IDs to actual folder names.
- `output/`, `input/`, `logs/`: optional runtime folders for future deployment workflows.

These runtime subfolders are ignored by git. Configure `NOVEL_LIBRARY_DIR` when production should mount a different disk or volume.

Do not commit runtime data from this folder unless it has been intentionally sanitized and documented as a fixture or example. `storage/novel_library` is private backend runtime data and should not be served directly by the frontend or static file hosting.

See `docs/reference/DATA_OUTPUT_STRUCTURE.md` for the detailed JSON layout,
deletion-safety table, backup/restore guidance, and notes about translated
metadata and public `/novels/{slug}` routes.
