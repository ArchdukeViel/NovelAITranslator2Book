---
trigger: when_reading_or_writing_chapters_translations_generations
description: Raw generations are byte-immutable; translation writes land in the per-chapter overlay; generations activate only after deterministic validation.
---

## project-storage-overlay

Storage contract for chapters, translations, and generations. Canonical
detail lives in `docs/STORAGE.md` and `docs/TRANSLATION.md`; this rule
carries the load-bearing invariants agents must not violate.

Rules:

- A committed raw generation under `generations/<gen-id>/` is
  byte-immutable. Never rewrite raw chapter bundles or image assets
  inside an active generation.
- Translation writes (machine translation, manual edit, QA retry,
  rollback activation) land only in the per-chapter overlay:
  `translations/<encoded-chapter-stem>.json` plus the `active/` pointer
  mirror. Readers compose the active raw generation with the active
  translation overlay on read.
- `commit_generation` runs `validate_generation_activation` before
  swapping `active_generation.json`: manifest status, metadata identity,
  every-index-entry-resolved (bundle or explicit
  `unavailable_chapter_ids`), image-asset resolution inside the staged
  generation, hash reconciliation, count reconciliation. On failure the
  stage is rolled back; `skip_validation=True` is an explicit
  operator-recovery opt-out, not a default.
- Chapter selection resolves through `resolve_chapter_selection` against
  the complete current index. Kakuyomu ids (`kakuyomu:<episode>`) are
  stable strings; never convert `chapter_id` to `int`, never use
  `chapter_id.isdigit()`, and never map a non-numeric id to `-1`.
- Source state persists `ordered_episode_ids` plus per-episode
  `source_availability` / `first_seen_at` / `last_seen_at` /
  `missing_since`. Episodes absent from the index become
  `missing_from_current_index`; raw and translated history is retained.
  Repeated crawls after reconciliation produce no reorder/removal delta.
- Cache acceptance is locked to the QA-accepted attempt. Rejected chunks
  (`needs_retry` / `needs_review` / `qa_failed`) never reach the cache;
  provider / model / prompt / glossary changes produce distinct cache
  keys.
