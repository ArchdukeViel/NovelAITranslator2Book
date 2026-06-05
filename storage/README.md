# Storage

Runtime files live here during local development and production-style deployments.

- `novel_library/`: novel metadata, chapter JSON, images, preferences, translation/fetch cache, usage logs, activity logs, scheduler state, provider request records, runtime traceability, and exports.
- `output/`, `input/`, `logs/`: optional runtime folders for future deployment workflows.

These runtime subfolders are ignored by git. Configure `NOVEL_LIBRARY_DIR` when production should mount a different disk or volume.

Do not commit runtime data from this folder unless it has been intentionally sanitized and documented as a fixture or example. `storage/novel_library` is private backend runtime data and should not be served directly by the frontend or static file hosting.
