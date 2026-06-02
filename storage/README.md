# Storage

Runtime files live here during local development and production-style deployments.

- `novel_library/`: novel metadata, chapter JSON, images, preferences, cache, usage logs, and exports.
- `output/`, `input/`, `logs/`: optional runtime folders for future deployment workflows.

These runtime subfolders are ignored by git. Configure `NOVEL_LIBRARY_DIR` when production should mount a different disk or volume.
