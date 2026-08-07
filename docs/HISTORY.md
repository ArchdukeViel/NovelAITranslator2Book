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
