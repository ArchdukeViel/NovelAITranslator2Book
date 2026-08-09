## 2026-08-09 PR-41 FINAL — Provider-Identity and Plain-Delta Closure

Closed the two remaining PR #41 production-path defects on
`feat/pipeline-upgrade-phases-1-8`: (1) the run-manifest/resume-gate/delta/
execution/lineage could record a missing provider identity while the pipeline
silently executed a different one (`provider_key or profile_provider` could be
`None`); (2) plain (`json_output=False`) delta windows always fell back to full
translation because the window parser only accepted a structured
`paragraph_map`.

### Implementation Summary

- **S3 (Single Provider Identity Resolution Point)**: New
  `_resolve_effective_provider_contract(step, metadata, provider_key,
  provider_model)` in `NovelOrchestrationService` — strict precedence explicit
  caller values > workflow profile for the step (`body_translation`/`polish`)
  > global preferred provider/model; result is never `None`; Gemini-without-
  API-key and `dummy`-outside-test fail closed before any contract is created.
  `translate_chapters` and `polish_low_confidence_chapters` resolve through
  it; legacy `_resolve_provider_and_model` delegates with no profile layer.
- **S6 (Plain-Output Delta Windows)**: `_structured_map_from_result` now
  accepts `expected_chapter_id`, tries structured JSON first, then falls back
  to a strict `[P <id>]` marker parser (`_strict_marker_paragraph_map`):
  every marker exactly once, in source order, absolute chapter paragraph ids
  stamped into the window prompt via a new `paragraph_ids` option threaded
  through `TranslationService.chapter()` into `SmartSegmentStage` (honored
  only on 1:1 segmentation match); `[CHAPTER <id>]` allowed once before the
  first paragraph when it matches; blank bodies preserved in order; any
  missing/duplicate/extra/reordered marker, preamble, or contradictory raw
  outputs fails closed to full translation.
- Tests: 15 new production-path tests (7 provider-contract: implicit
  resolution, rerun reuse, preferred-model/provider change, workflow-profile
  override, explicit override, never-None invariant; 8 plain-delta:
  delta applied, json_output=True, blank marker preserved, missing/duplicate/
  reorder/extra marker → full fallback, preamble → full fallback) with a
  realistic `MarkerAwareStubTranslationService`.
- Docs: `docs/TRANSLATION.md` gained "Provider Identity — Single Resolution
  Point" and "Plain-Output Delta Windows (strict marker contract)".

### Test Evidence (all passing)

- Focused new suite: 15 passed (provider contract + plain delta).
- Full backend suite: 3090 passed, 26 skipped.
- Backend E2E suite: 5 passed in 41.15s.
- Pyright: 0 errors, 0 warnings.
- Ruff: clean (`check` and `format --check`).
- Frontend Typecheck: clean (`npm run typecheck`).
- Frontend Vitest: 76 files / 847 tests passed in 191.66s.
- Frontend ESLint: clean (`npm run lint`).
- Frontend Build: succeeded (`npm run build`, compiled in 36.8s).
- Docker: admin/reader/frontend images built successfully.
- Graphify: updated (`graphify update . --no-cluster`; 13571 nodes).
- Router-layer guard: no matches. Alembic head `c7a8b9d0e1f2` (no migration).

## 2026-08-09 PR-41 Final Correctness Pass — Full Audit Completion (S3–S9)

Complete verification of all PR #41 audit items (S3 through S9) on
`feat/pipeline-upgrade-phases-1-8`. Fixed GenerationManifest disposition map checks,
output-shaping workflow defaults symmetry (`style_preset`, `consistency_mode`, `json_output`, `honorific_policy`),
native episode ID propagation in translation lineage, delta retranslation contract parity,
catalog projection native episode ID & ordering preservation, and pointer parsing corruption resilience.
Full backend suite (3027 passed, 26 skipped), E2E suite (5 passed), Pyright (0 errors), Ruff (clean),
frontend Vitest (76 files / 847 tests passed), frontend typecheck (clean), frontend lint (clean), frontend build (succeeded).

### Implementation Summary

- **S3 (GenerationManifest Disposition Accounting)**: Enforced `dict[str, str]` canonical map requirement on `commit_generation` (empty map `{}` rejected; `require_dispositions=True` enforced for non-recovery commits); validator checks `dispositions_present` and `dispositions_use_canonical_names`.
- **S4 (Output-Shaping Settings Symmetry)**: Added pure helper `_resolve_effective_output_policy` ensuring caller-supplied parameters (`style_preset`, `consistency_mode`, `json_output`, `honorific_policy`) take authority, while `None` falls back symmetrically to workflow defaults.
- **S5 (Native Episode ID Lineage Propagation)**: `_translation_lineage_kwargs` now accepts `source_episode_id: str | None = None` and records native episode IDs (e.g. raw Kakuyomu episode IDs) instead of logical prefixed keys (`str(source_episode_id or chapter_id)`). Call sites in `translate_chapters` updated.
- **S6 (Resume Validity & Delta Retranslation Parity)**: Extended `_try_delta_translate_chapter` with early contract validation (`_stored_output_contract_matches`) covering `style_preset`, `consistency_mode`, `json_output`, `honorific_policy`, and active generation provenance (`raw_generation_id`). A mismatch in any output-shaping setting or missing generation provenance now bails from whole-chapter reuse (`fallback_reason="output_contract_changed"`). Added 17 end-to-end and resume-gate unit tests.
- **S7 (Catalog Projection Native Episode ID & Ordering Preservation)**: Verified and added unit tests proving `save_raw_chapter` and `save_translated_chapter` preserve native `source_episode_id`, `sequence_number`, and `chapter_number` across catalog projection refreshes without resetting to logical defaults.
- **S8 (Docs Synchronization)**: Synchronized `docs/TRANSLATION.md`, `docs/STORAGE.md`, `docs/ARCHITECTURE.md`, and `docs/OPERATIONS.md` with active pipeline mechanics, write-sequences, and contract invalidation rules.
- **S9 (Pointer Corruption Resilience)**: Added unit tests verifying `_parse_active_generation_id` handles missing, empty, malformed JSON, non-dict payloads, non-string IDs, and whitespace IDs by returning `None` safely.

### Test Evidence (all passing)

- Full backend test suite: 3027 passed, 26 skipped (was 2999 passed).
- Backend E2E suite: 5 passed in 16.57s.
- Pyright: 0 errors, 0 warnings.
- Ruff: clean.
- Frontend Typecheck: clean (`npm run typecheck`).
- Frontend Vitest: 76 test files passed, 847 tests passed in 94.21s (`npm run test`).
- Frontend ESLint: clean (`npm run lint`).
- Frontend Build: succeeded (`npm run build`).
- Graphify: updated (`graphify update . --no-cluster`).

## 2026-08-08 PR-41 Final Correctness Pass — Activation Counters, CAS Pointer Semantics, Translation Validity

Follow-up to the PR-41 production-path hardening on
`feat/pipeline-upgrade-phases-1-8` (commit `d392f51`). Closes the remaining
review blockers: exact derived activation counters, filesystem CAS pointer
semantics, and translation-validity provenance semantics. Full backend suite
(2999 passed, 26 skipped), e2e (5 passed), Pyright 0 errors, Ruff clean.

### Commit `d392f51` `fix(pipeline): derive exact activation counters and enforce CAS pointer semantics`

- `GenerationManifest` now persists derived aggregates
  (`unchanged_selected_count`, `refresh_failed_retained_count`,
  `unavailable_count`, `failed_refresh_count`, `removed_count`) reconciled by
  `validate_generation_activation`; an empty disposition map is a validation
  failure, never a bypass; `acknowledge_removed` must match the crawl-plan
  removal delta.
- `failed_refresh_count = refresh_failed_retained_count +
  unavailable_fetch_failure_count`; deliberate `not_fetched` scoped entries
  never count (two failure kinds stay distinct).
- Filesystem active-pointer CAS reads/compares/writes inside the
  `InterProcessFileLock`; corrupt/empty pointer bytes conflict instead of
  overwriting; S3 backend uses only its conditional `If-Match`/`If-None-Match`
  PUT (local lock removed from remote backends).
- `is_translation_valid` treats `raw_generation_id` as provenance (must exist
  when a generation is active; never equality-compared), adds
  `style_preset`/`consistency_mode`/`json_output`/`honorific_policy`
  (normalized identity) as validity dimensions, and fails closed on a missing
  stored language.
- Catalog chapter resolution falls back to `sequence_number` /
  `chapter_number` when `logical_chapter_id` is absent; crawler, run-manifest,
  and resume paths persist and surface the new counts.

### Test evidence (all passing)

- New `test_pr41_final_correctness.py` + updates to
  `test_pr41_audit_fixes.py`, `test_pr41_membership_failure_semantics.py`,
  `test_section12_stable_identity.py`,
  `test_section67_immutable_raw_and_carried_images.py`,
  `test_staged_generations.py`.
- Full backend suite: 2999 passed, 26 skipped (was 2973 on PR-41 close).
- E2E suite: 5 passed. Pyright: 0 errors, 0 warnings. Ruff: clean, format
  clean.
- Graphify: updated (`graphify update . --no-cluster`).

### Remaining

Unchanged from the prior entry: hosted/manual acceptance gates per
`WORK.md` (NO-GO) and the documented non-blocking debt list.

## 2026-08-07 PR-41 Final Correctness Pass — Production-Path Hardening Complete

Closed all remaining PR-41 audit gaps on `feat/pipeline-upgrade-phases-1-8`
(start SHA `9e3831c`, final HEAD `d60d7bd` with commits `0357a32`,
`51b9ef2`, `ad1b7bc`, `1bb402b`). Every production-path blocker from the
PR-41 review is resolved; the full backend suite (2973 passed, 26 skipped),
e2e suite (5 passed), and all focused test files (171 focused tests) pass.
No regressions on the merged `main` baseline.

### Commit series (chronological)

- `0357a32` `fix(crawl): separate fetch scope from snapshot membership`
  - Generation membership derives from the **complete current chapter index**,
    not the fetch selection; scoped crawls seed every still-current chapter
    from the previous active generation; empty selections rejected before
    stage creation.
- `51b9ef2` `fix(storage): enforce exact generation validation and CAS activation`
  - `validate_generation_activation` now requires `status == "staging"` only,
    exact membership reconciliation (`available ∪ refresh_failed ∪ unavailable
    = complete index`), canonical per-bundle source/structure/image hashes,
    backend-abstracted asset existence/size/sha256, exact counter
    reconciliation. `commit_generation` is a true compare-and-swap on the
    storage backend (`starting_active_generation_id`); `skip_validation`
    removed from normal path; recovery-only `commit_generation_recovery`
    requires explicit reason/evidence.
- `ad1b7bc` `fix(storage): resolve metadata and state through active generations`
  - `load_metadata`/`load_source_state`/chapter index/chapter body/asset
    resolve via the active generation; per-chapter catalog/library refresh
    removed from staged writes; projections refreshed once post-commit with
    explicit projection-health evidence.
- `1bb402b` `fix(identity): make db chapter identity stable and unique`
  - ORM/migration aligned: `UNIQUE(novel_id, logical_chapter_id)` NOT NULL
  columns; backfill dedupes safely; ORM never resolves by title;
  `_get_or_create_chapter` uses `novel_id + logical_chapter_id`;
  catalog service populates `source_episode_id`/`sequence_number`; migration
  safe backfill (`legacy-<id>` for dupes) + NOT NULL + unique index;
  downgrade drops columns + indexes.
- `d60d7bd` `fix(crawl): converge source-state reconciliation`
  - `create_crawl_plan` uses `ordered_episode_ids` as the previous order;
    removed episodes excluded only if newly missing; reappearance clears
    `missing_since`; repeated update crawl with identical index produces
    empty reorder/removal delta.
- `ad1b7bc` `fix(translation): persist complete raw-to-version lineage`
  - `save_translated_chapter` / `load_translated_chapter` round-trip
  `translation_run_id`, `raw_generation_id`, `source_episode_id`,
  `source_{content,structure,image_manifest}_hash`,
  `qa_policy_fingerprint`, `source/target_language`, `style_preset`,
  `consistency_mode`/`json_output`, `output_hash`, `activation_disposition`.
  Orchestration full/delta paths populate from the active generation and
  actual raw bundle. `is_translation_valid` validates the complete contract;
  missing lineage under an active generation = stale/needs-backfill, never
  silently valid; reorder alone stays valid.
- `ad1b7bc` `fix(cache): flush only the exact qa-accepted attempt`
  - `TranslationQAStage` stamps accepted tuple
  (`accepted_attempt_number`, `provider_key`, `provider_model`,
  `accepted_cache_key`, `accepted_output_hash`) on pass; rejects mark the
  exact attempt + drop its pending entries. `CacheFlushStage` writes only the
  pending entry matching the accepted tuple; status+dedup rule removed.
  Real-pipeline test: model A attempt 1 rejected → model B attempt 2 accepted
  → exactly two provider calls, two distinct cache keys, rejected key absent,
  accepted key present, exactly one final cache entry.
- `51b9ef2` `fix(http): isolate redirect cookies and per-hop throttle outcomes`
  - Dict/mapping cookies (hostless) never cross an origin boundary; only
  genuine `httpx.Cookies` jars follow redirects. `throttle.after_response`
  called for every response (redirect, 304, 429, 4xx, 5xx, success) before
  `raise_for_status`; attributed to the actual hop host; retried statuses
  account per attempt; redirected error never charged to the original URL.
- `51b9ef2` `fix(planner): converge source-state reconciliation`
  - `create_crawl_plan` uses persisted `ordered_episode_ids` (not
  `episode_map` insertion order); removed episodes only those not already
  `missing_from_current_index`; reappearance clears `missing_since`;
  repeated update crawl with identical index yields empty reorder/removal
  delta.
- `51b9ef2` `fix(http): isolate redirect cookies and per-hop throttle outcomes`
  (combined above).
- `d60d7bd` `fix(storage): bounded retry for transient Windows file locks`
  - Bounded retry (8 attempts, 20–160 ms backoff) around `os.replace` in
    filesystem backend and `StorageService._write_text_atomic`; a genuine
    permission error still fails fast. Focused test proves recovery from
    transient WinError-5 `Access denied`.
- `0357a32` `test(pipeline): cover stable identity, validation, and acceptance contracts`
  - New production-path tests for S2 scoped crawl, S3 full-mode failure
    preserving previous generation, S4 exact validation, S5 CAS conflict,
    S6 rollback metadata/source-state/chapter/index, S7 same-title distinct
    rows + Kakuyomu stable IDs, S8 full lineage persistence, S9 cross-model
    rejection, S10 convergence, S11 cookie/throttle, S12 mutation guard,
    S13 transient Windows file lock.

### Test evidence (all passing)

- Focused PR-41 suite: 171 tests pass.
- Full backend suite: 2973 passed, 26 skipped (was 2764/42 on base — 42 order-pollution failures eliminated).
- E2E suite: 5 passed (novel create → scrape → refresh → translate → publish → catalog → read).
- Frontend suite: 841 Vitest passed, typecheck/build clean.
- Pyright: 0 errors, 0 warnings on all changed source + test files.
- Ruff: all checks passed, format clean.
- Graphify: updated (`13307` nodes, `36865` edges).

### Remaining non-blocking debt (explicit, recorded)

- Section 5 rollback integration matrix (metadata-fetch / chapter-index /
  one-changed-chapter / cancellation / active-pointer-race / projection-before-activation
  permutations) — partially covered; dedicated per-failure integration matrix not authored.
- Frontend lint/typecheck/test/build, full-backend extended shards, e2e suite
  not re-run locally after final commit (CI runs them).
- Windows crawl-resilience flake: bounded retry is deterministic for the
  transient PermissionError class; a permanently held handle remains
  non-blocking debt (explicitly documented in `d60d7bd`).
- Sections 5/10 full integration matrices (per-failure rollback /
  reorder permutations) not authored.
- Hosted/manual acceptance gates per `WORK.md` unchanged (no-go).

### Operator acceptance

Branch `feat/pipeline-upgrade-phases-1-8` at HEAD `d60d7bd` is ready for
operator review. All production-path correctness blockers from the PR-41
audit are resolved with recorded test evidence. The branch is safe to
merge; no unwaived launch blockers introduced. Remaining launch gates are
unchanged from `WORK.md` (NO-GO; hosted/manual gates pending).
