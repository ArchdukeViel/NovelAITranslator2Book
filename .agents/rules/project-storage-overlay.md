---
trigger: always_on
description: Raw novel generations are byte-immutable; translation writes land in per-chapter overlays; generations activate only after deterministic validation.
---

# Project Storage Overlay Contract

This rule enforces the load-bearing storage invariants for novel content, chapters, translations, and generation lifecycles. Detailed architectural definitions live in `docs/STORAGE.md` and `docs/TRANSLATION.md`.

## Immutability & Overlay Architecture

- **Byte-Immutable Raw Generations**: A committed generation under `generations/<gen-id>/` is strictly byte-immutable. Never modify, rewrite, or overwrite raw chapter bundles or image assets in place.
- **Per-Chapter Translation Overlay**: Translation writes (machine translation, manual edit, QA retry, rollback activation) land exclusively in the per-chapter overlay:
  `translations/<encoded-chapter-stem>.json` alongside the `active/` pointer mirror.
- **Composition on Read**: Reader services dynamically compose the immutable raw generation with the active translation overlay at request time.

## Deterministic Generation Activation Gate

- **Validation Before Activation**: `commit_generation` executes `validate_generation_activation` before swapping `active_generation.json`.
- **Validation Criteria**: Manifest status, metadata identity, every index entry resolved (either physical bundle or explicit entry in `unavailable_chapter_ids`), image asset integrity, hash reconciliation, and chapter count reconciliation.
- **Fail-Closed Rollback**: If validation fails, the staged generation is rolled back. Explicit emergency recovery uses `commit_generation_recovery(reason=..., evidence=...)` requiring operator consent.

## Chapter Identity & Source Integrity

- **String-Typed Identifiers**: Episode identifiers across sources (Kakuyomu `kakuyomu:<episode>`, Syosetu ncode, generic) and external chapter IDs are stable strings.
  - **PROHIBITED**: Never cast `chapter_id` to `int`.
  - **PROHIBITED**: Never use `chapter_id.isdigit()`.
  - **PROHIBITED**: Never fallback non-numeric IDs to `-1`.
- **Source Index Tracking**: Source state tracks `ordered_episode_ids` and per-episode timestamps (`first_seen_at`, `last_seen_at`, `missing_since`). Episodes absent from new crawls are marked `missing_from_current_index` without deleting historical raw or translated data.

## Cache & QA Acceptance

- **QA Acceptance Locking**: Cache acceptance is locked strictly to QA-accepted attempts.
- **Never Cache Rejected Chunks**: Chunks marked `needs_retry`, `needs_review`, or `qa_failed` never enter cache. Changes to provider, model, prompt, or glossary automatically yield distinct cache keys.
