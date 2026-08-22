## 2026-08-22 PR113 R2 CONTROL-PLANE AND DATABASE PERFORMANCE CHECKPOINT

Applied and verified Alembic migration `c9d1e3f5a7b9` on the authorized
Supabase PostgreSQL project. It adds the missing `novel_requests.chapter_id`
foreign-key index identified by the live performance advisor. A follow-up
advisor run reported no unindexed foreign-key finding; remaining unused-index
observations are retained for workload review rather than removed speculatively.

The Cloudflare control-plane audit independently confirmed exactly two R2
buckets: `dokushodo` and `dokushodo-backup`. Both are APAC/Standard/default-
jurisdiction. Application and backup lifecycle rules are enabled, and neither
private bucket has a custom domain or CORS policy. No object or backup data was
modified during this audit; backup/recovery remains operator-deferred.

The read-only application-bucket verifier measured 538 objects, 1,323,657
stored bytes, 5,586,652 logical uncompressed bytes, and 4,262,995 compression-
saved bytes (76.31%). It performed one paginated LIST, 538 HEAD requests, and
538 GET requests; all logical SHA-256 metadata checks passed. Repeated live
recrawl and backup-reuse counters remain unmeasured.

## 2026-08-17 DEBT-079D MINIMAL STAGING FIXTURES, ADAPTER HEALTH & PERFORMANCE ACCEPTANCE EVIDENCE

The evidence in this section predates the R2-only content rearchitecture. Its
`storage/novel_library` prefix and active-pointer files describe the historical
pre-cutover layout; they are not the current storage contract. Current
requirements and implementation evidence live in [`STORAGE.md`](STORAGE.md)
and [`R2-ONLY-CONFORMANCE.md`](R2-ONLY-CONFORMANCE.md).

Executed minimal real staging fixture ingestion from 3 operator-supplied URLs, validated source adapter parsing, verified adult content isolation, and ran hosted performance benchmarking on candidate commit `8c8c109c6886d7ac22d4ef3c49a49d50dba3bc23` on private staging instance (`https://laptop-akmalpellu.tail0b4e3e.ts.net`).

### 1. Minimal Real Fixtures Ingested & Adapter Health
- **Source A (Narou / `syosetu_ncode`)**:
  - Source URL: `https://ncode.syosetu.com/n2056dn/`
  - Slug: `n2056dn`
  - Scraped: 3 chapters (metadata, chapter index, raw chapter bundles)
  - Storage Backend: Cloudflare R2 bucket `dokushodo` (prefix `storage/novel_library/novels/n2056dn/`)
  - Active Generation: `gen-bc9b949823dd`
  - Pointer File: `storage/novel_library/novels/n2056dn/generations/active_generation.json`
  - Translated: Chapter 1 via Gemini (`gemini-2.5-flash`)
  - Publication Status: Published (`is_published = true`) in Supabase PostgreSQL 18
- **Source B (Kakuyomu / `kakuyomu`)**:
  - Source URL: `https://kakuyomu.jp/works/16817330655991571532`
  - Slug: `16817330655991571532`
  - Scraped: 3 chapters (metadata, chapter index, raw chapter bundles)
  - Storage Backend: Cloudflare R2 bucket `dokushodo` (prefix `storage/novel_library/novels/16817330655991571532/`)
  - Active Generation: `gen-4d4e855cfe88`
  - Pointer File: `storage/novel_library/novels/16817330655991571532/generations/active_generation.json`
  - Translated: Chapter 1 via Gemini (`gemini-2.5-flash`)
  - Publication Status: Published (`is_published = true`) in Supabase PostgreSQL 18
- **Source C (Novel18 / `novel18_syosetu`)**:
  - Source URL: `https://novel18.syosetu.com/n3266mn/`
  - Slug: `n3266mn`
  - Scraped: 1 chapter (metadata, chapter index, raw chapter bundles)
  - Storage Backend: Cloudflare R2 bucket `dokushodo` (prefix `storage/novel_library/novels/n3266mn/`)
  - Active Generation: `gen-ee00faf84b62`
  - Pointer File: `storage/novel_library/novels/n3266mn/generations/active_generation.json`
  - Content Classification: `is_r18 = true` / adult content
  - Publication Status: Ingested for source validation only; **NOT published** to public catalog

### 2. Live & Backup Storage Authoritative Inventory Truth
- **Live Bucket `dokushodo`**:
  - Total Objects: 31
  - Total Size: 393,841 bytes (~384.6 KB)
  - Layout: `storage/novel_library/novels/<novel_id>/...`
- **Backup Bucket `dokushodo-backup`**:
  - Total Objects: 187
  - Total Size: 4,128,176 bytes (~3.94 MB)
  - Clean Snapshot `snapshots/backup-20260817T125542Z-44705505`: 32 objects, 403,475 bytes (31 live data objects + 1 `manifest.json` at 9,634 bytes)
  - Clean Database Backup `database/database-20260817T125749Z-2cdda27f`: 2 objects, 243,663 bytes (`dump.custom.aesgcm` 243,183 bytes + `manifest.json` 480 bytes)
  - Historical Snapshots: 9 snapshots (17 objects, 386,782 bytes each) protected by Cloudflare R2 bucket-level Object Lock (`ObjectLockedByBucketPolicy`).
  - Historical Database Backups: 9 dumps (~243 KB each).
  - Note: The historical `11,438 objects / 3.61 GiB` figure reflects pre-wipe test runs prior to bucket initialization and does not represent the clean post-wipe staging baseline.

### 3. Adult Content Isolation & Public Reader Verification
- **Catalog Isolation**: `GET https://laptop-akmalpellu.tail0b4e3e.ts.net/api/public/catalog` returns exactly 2 published novels (`n2056dn`, `16817330655991571532`). Novel18 (`n3266mn`) is completely absent.
- **Novel Route Isolation**: `GET https://laptop-akmalpellu.tail0b4e3e.ts.net/api/public/novels/n3266mn` returns HTTP 404 (Not Found).
- **Chapter Reader Verification**: `GET https://laptop-akmalpellu.tail0b4e3e.ts.net/api/public/novels/n2056dn/chapters/1` returns HTTP 200 with 2,581 translated Japanese-to-English characters across 26 structured reader blocks.

### 4. DEBT-079D Hosted Performance Benchmark Results (20 samples per endpoint)

Executed via `backend/tests/run_hosted_benchmark.py`:

| Endpoint | Metric | Budget | Hosted (Tailscale) Measured | Result | Local Direct Caddy Measured |
| --- | --- | --- | --- | --- | --- |
| **Catalog API** (`GET /api/public/catalog`) | Latency p95 | $\le 500\text{ ms}$ | **$31,637.2\text{ ms}$** ($p50 = 25,088.6\text{ ms}$) | **FAIL** | $12.0\text{ ms}$ ($p50 = 3.2\text{ ms}$) |
| | Payload Size | $\le 250\text{ KiB}$ | **$3.29\text{ KiB}$** | **PASS** | $3.29\text{ KiB}$ |
| **Novel API** (`GET /api/public/novels/n2056dn`) | Latency p95 | $\le 300\text{ ms}$ | **$19,287.4\text{ ms}$** ($p50 = 7,135.3\text{ ms}$) | **FAIL** | $4.0\text{ ms}$ ($p50 = 3.4\text{ ms}$) |
| | Payload Size | $\le 100\text{ KiB}$ | **$2.55\text{ KiB}$** | **PASS** | $2.55\text{ KiB}$ |
| **Chapter API** (`GET /api/public/novels/n2056dn/chapters/1`) | Latency p95 | $\le 750\text{ ms}$ | **$11,953.9\text{ ms}$** ($p50 = 10,500.6\text{ ms}$) | **FAIL** | $4.6\text{ ms}$ ($p50 = 3.8\text{ ms}$) |
| | Payload Size | $\le 1024\text{ KiB}$ | **$6.33\text{ KiB}$** | **PASS** | $6.33\text{ KiB}$ |

### 5. Root Cause Determination: Infrastructure Topology vs Application Logic
- **Application Logic**: Extremely fast and optimal. When queried on localhost through Caddy reverse proxy, latency is $3\text{ ms} - 12\text{ ms}$, well under all performance budgets. Payload sizes ($2.5\text{ KiB} - 6.3\text{ KiB}$) are fractions of the size allowances.
- **Hosted Latency Root Cause**:
  1. Multi-hop WAN latency between local Docker containers and remote Supabase PostgreSQL 18 in Singapore (`aws-1-ap-southeast-1.pooler.supabase.com`).
  2. Sequential remote S3/R2 requests per endpoint call (metadata, active generation pointer, manifest, chapter files) over Cloudflare R2 TLS handshakes.
  3. Client-to-host Tailscale mesh tunnel overhead.
- **Resolution Path**: Co-locating the backend reader and database in the same cloud region (e.g. AWS/Fly.io in Singapore or US) alongside Redis and S3 caching will bring hosted response times to $< 50\text{ ms}$.

## 2026-08-17 DEBT-FE-01A MANUAL ACCESSIBILITY ACCEPTANCE EVIDENCE

Executed comprehensive accessibility, responsive layout, and screen-reader audit on candidate commit `8c8c109c6886d7ac22d4ef3c49a49d50dba3bc23` on private staging instance (`https://laptop-akmalpellu.tail0b4e3e.ts.net`).

### Automated & Browser Verification
- **Target Routes**: `/home`, `/browse-novels`, `/login`, `/about`, `/privacy`, `/terms`, `/dmca`, `/faq`, `/cookie-policy`, `/not-found`.
- **Landmarks & Semantics**: Verified single unique `<h1>` per page, complete `<header>`, `<main>`, `<footer>`, and `<nav>` landmarks. Form controls contain associated `<label>` or explicit `aria-label`.
- **Keyboard Navigation & Focus**:
  - Full tab order verified across 35 focusable controls on `/login?mode=signin`.
  - Visible focus indicators (two-layer ring with theme outline) confirmed on all inputs and action triggers.
  - Zero keyboard focus traps; modal close actions reachable and operable via keyboard.
- **Responsive Reflow & 200% Zoom**:
  - 320 CSS px narrow viewport reflow: 0 horizontal scrolling/page overflow. Multi-column grids cleanly collapse to 1 column.
  - 200% zoom (640x480 desktop equivalent): Zero content clipping, text overlap, or horizontal scroll barriers.
- **Color Contrast (WCAG 2.1 AA)**:
  - Primary text (`rgb(43, 40, 38)` on `#F4F1EA` paper): 12.88:1 (exceeds 4.5:1 requirement).
  - Secondary text (`rgb(101, 96, 93)` on `#F4F1EA` paper): 5.46:1 (exceeds 4.5:1 requirement).
  - Brand Accent (`rgb(182, 52, 32)` on `#F4F1EA` paper): 5.28:1 (exceeds 4.5:1 requirement).
  - Hero CTA ("Browse Catalog"): Verified rendered computed contrast of 11.5:1 (`rgb(243, 240, 235)` on `rgb(43, 40, 38)` background). Prior static warning confirmed as false positive.
- **Reduced Motion**: Confirmed CSS transitions honor `prefers-reduced-motion` and no essential functionality is animation-dependent.
- **Forced Colors**: NOT RUN — environment unavailable in automated headless browser; non-blocking supporting check.

### Operator Attestation
- **Physical Mobile & Touch Verification**: Operator attested completion of physical mobile responsiveness, bottom sheet interactions, reader touch controls, and software keyboard reflow on actual physical phone connected to Tailscale staging.
- **Native Screen Reader**: Operator attested completion of native screen-reader walkthrough (voice announcements, heading hierarchy, link descriptions, form field labeling) on physical mobile/desktop screen-reader platform.

## 2026-08-17 DEBT-075A, DEBT-075B, DEBT-079A, DEBT-079B STAGING DEPLOYMENT & RECOVERY DRILL EVIDENCE

Executed candidate deployment and operational acceptance drill on private staging instance behind Tailscale Serve HTTPS (`https://laptop-akmalpellu.tail0b4e3e.ts.net`).

### Environment & Candidate Verification
- Candidate Commit: `8c8c109c6886d7ac22d4ef3c49a49d50dba3bc23` (`8c8c109`)
- Alembic Head: `d7e4f9a1c2b3` (35 public tables, 0 invalid constraints)
- Immutable Image Digests:
  - Admin: `ghcr.io/archdukeviel/novelaitranslator2book/novelai-admin:sha-8c8c109c6886d7ac22d4ef3c49a49d50dba3bc23@sha256:21a755c79aa7ad7eaf22422e319e6bb3c2cbccfc7876ec2b6001d3fa3ce35937`
  - Reader: `ghcr.io/archdukeviel/novelaitranslator2book/novelai-reader:sha-8c8c109c6886d7ac22d4ef3c49a49d50dba3bc23@sha256:146ce9a2bbd294d82996f844642111a5e1b59d5331b7ba20ea676a6f475168dd`
  - Frontend: `ghcr.io/archdukeviel/novelaitranslator2book/novelai-frontend:sha-8c8c109c6886d7ac22d4ef3c49a49d50dba3bc23@sha256:12f80eb27ab095e2978df067a73a15e886ae6d7395e2511229455d0e3ce5985e`
  - Caddy: `caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648`
  - Redis: `redis:8.8.0-alpine@sha256:9d317178eceac8454a2284a9e6df2466b93c745529947f0cd42a0fa9609d7005`
  - Restore DB: `postgres:18.6-alpine@sha256:432b3b824c0769275ec9b0947736ef8b376d6997bcaa9de29818f613819c2feb`
- Reverse Proxy: Tailscale Serve TLS termination on `https://laptop-akmalpellu.tail0b4e3e.ts.net/` proxying to `http://127.0.0.1:8080`.

### DEBT-079A & DEBT-079B Shipped Verification
- **Smoke Suite (`deploy-smoke.ps1`)**: 8/8 endpoints returned 200 OK (`/health/live`, `/health/ready`, `/`, `/login`, `/privacy`, `/terms`, `/novels`, `/api/public/novels`).
- **Security & Cookie Invariants**:
  - `SESSION_COOKIE_SECURE=true` verified: `Set-Cookie` emits `Secure; HttpOnly; SameSite=Lax`.
  - Security headers present: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
  - CSRF protection: POST `/api/admin/novels` and `/api/auth/register` reject missing/invalid `X-CSRF-Token` with HTTP 403.
  - Reader isolation: `/api/admin/*` unreachable through reader port (8001); properly routed to admin on port 8000 via Caddy.

### DEBT-075A Managed Services Verification
- **PostgreSQL**: Connected via least-privilege `novelai_runtime` role against Supabase pooler (`aws-1-ap-southeast-1.pooler.supabase.com:5432`). Verified schema isolation, RLS constraints, and lease contention locks.
- **R2 Storage & S3 Integration**: Executed `test_r2_snapshot_integration.py` against isolated prefix on Cloudflare R2 bucket `dokushodo`. Verified atomic write, read, and delete operations.

### DEBT-075B Current-Head Recovery Drill
- **Object Snapshot**: Created fresh snapshot `backup-20260817T013754Z-0a73f437` into R2 bucket `dokushodo-backup`. Verified AES-GCM encryption, plaintext checksum, and manifest integrity.
- **Encrypted Database Backup**: Created backup `database-20260817T013953Z-b5777e92` into R2 bucket `dokushodo-backup`.
- **Automated Restore Drill**: Restored backup into isolated disposable container `novel-ai-restore-db-1` (`postgres:18.6-alpine`) target database `novelai_restore_verify`.
  - Result: `DatabaseBackupService.verify_latest_restore()` status `succeeded`.
  - Restored Alembic Head: `d7e4f9a1c2b3`
  - Public Tables: 35
  - Invalid Constraints: 0

## 2026-08-11 PR-41 CLOSURE — Provider Exception Sanitization, Shared Atomic Replacement & Final Documentation Synchronization

Final documentation synchronization pass for PR #41 on `feat/pipeline-upgrade-phases-1-8`.

### Implementation Summary

- **Provider Exception & Sanitization Safety**: Standardized provider exception cause-chain sanitization across Gemini and provider error paths; public API responses, error logs, and activity records never leak raw API keys, internal credentials, host details, or raw stack traces.
- **Shared Atomic File Replacement**: Consolidated atomic write operations into `novelai.utils.filesystem.replace_with_retry` with bounded retry (8 attempts, `attempts >= 1` validation, `PermissionError` handling). Removed destructive delete-then-replace fallbacks across storage handlers, ensuring atomic target preservation and cleanup of temporary files on exhausted retries.
- **CAS & Storage Integrity**: Verified `FilesystemBackend` save, compare-and-swap (CAS), and generation pointer activation invariants under inter-process locks, preserving atomic state and checkpoint safety.
- **Pre-documentation production-head evidence**: PR state at `ee046c0` contained 94 commits; the `ee046c0` head passed the required CI matrix across backend lint/tests/shards, frontend lint/typecheck/vitest/build, E2E, Docker, CodeQL, GitGuardian, Dependency Review, and Vercel Preview.
- **Documentation synchronization head**: `9561cef` (commit 95) passed current-head CI #572, Dependency Review, GitGuardian, CodeQL/security analyses, and Vercel.

## 2026-08-10 PR-41 FINAL — Provider-Pair Validation and Real-Pipeline Evidence Closure

Final PR #41 closure pass on `feat/pipeline-upgrade-phases-1-8`: the resolver
hardening from S3/S6 is validated end-to-end through the real production
pipeline, and two cache-related fail-closed defects found by that evidence are
fixed in production code.

### Implementation Summary

- **Resolver hardening (S3 final)**: `_resolve_effective_provider_contract`
  now normalizes identities (whitespace-stripped, empty treated as absent),
  validates provider existence at resolution time through the registered
  factory (`_provider_instance`, factory `KeyError` → `ProviderConfigError`),
  validates an explicit model against the resolved provider's own
  `available_models()` (authoritative list; `[]` = free-form), and resolves
  workflow/global models only when coherent with the resolved provider —
  a manifest is never created for an unknown provider or an unsupported
  explicit model pair.
- **Delta fallback forces a fresh full retranslation**: when unsafe post-provider
  delta rejection occurs, `_try_delta_translate_chapter` surfaces `fresh_full_required=True`,
  and full fallback runs with `force_retranslate=True`, realizing
  `TRANSLATION_DELTA_FORCE_FULL_ON_UNSAFE`: the full path no longer reuses the
  very window output the strict marker gate rejected. Benign pre-provider declines
  retain normal full-cache behavior.
- **`force_retranslate` bypasses the translation cache**: `TranslateStage` skips
  the sharded `TranslationCacheService` lookup when `force_retranslate` is set
  (contract already documented by `test_translation_cache_contract.py`); a
  forced retranslation is a fresh provider request, never a cache reuse.
- **Real-pipeline evidence suite** (`test_novel_orchestration_service.py`):
  `DeterministicTranslationProvider` + `_parse_marker_source` + a
  `_real_pipeline_orchestrator` running the real stage set (Fetch/Parse/
  SmartSegment/Translate/QA/CacheFlush/PostProcess) with per-test isolated
  `TranslationCacheService`; 9 tests prove absolute paragraph ids reach the
  provider verbatim, the structured `paragraph_map` path, and fail-closed
  behavior for missing/duplicate/extra/reordered/preamble/oversized output —
  plus 11 provider-contract tests (explicit/omitted model, model validated
  against the resolved provider only, unknown provider, whitespace identity,
  Gemini/dummy guards, free-form provider, no-provider fail closed, resume
  reuse identity) exercising the real `translate_chapters` entry point.
- **Oversized-paragraph delta debt resolved**: a changed window spanning
  several pipeline chunks (an oversized source paragraph split by
  `split_oversized_paragraph`, or a window exceeding one chunk budget) now
  applies instead of failing closed. `_structured_map_from_result` gains a
  piecewise path (`_piecewise_map_from_result`): each chunk's raw provider
  output is parsed strictly against that chunk's own `paragraph_ids` (marker
  grammar, then structured `paragraph_map`), and pieces of the same source
  paragraph are merged back in chunk order with the same `"\n\n"` separator
  the full path uses. `_strict_marker_paragraph_map` now matches repeated ids
  positionally (split pieces of one paragraph can share a chunk). Multi-chunk
  windows with no valid per-chunk parse still fail closed; the old
  whole-window accumulation could never validate them.
- **Context-overlap QA ratio fix**: `[CONTEXT OVERLAP]` blocks carry
  prior-chunk context the provider is not asked to translate; `_strip_markers`
  now removes the whole block so the `translation_too_short` ratio no longer
  counts overlap content as missing output (this also unblocked multi-chunk
  windows on the full path).
- **Occurrence-aware QA for split paragraph IDs**: `_paragraph_diagnostics`
  in `qa.py` is refactored to use occurrence counts (`Counter`) instead of set
  uniqueness. When `SmartSegmentStage` splits an oversized paragraph across
  sentence boundaries and packs multiple split pieces into ONE
  `TranslationChunk` (all carrying the original `paragraph_id`), QA compares
  expected vs actual as ordered occurrence sequences — permitting expected
  repeats while rejecting missing occurrences, excess occurrences
  (`paragraph_duplicate`), unexpected IDs (`paragraph_unexpected`), or order
  mismatches (`paragraph_order_mismatch`).
- **Strict structured delta maps**: `_json_map_for_expected_ids` now enforces
  `len(actual_map) == len(expected_ids)` and exact positional `paragraph_id`
  matching (and `chapter_id` matching when present) with zero truncation or
  loose positional fallback, shared by both single-chunk and multi-chunk delta
  paths.
- **Provider model discovery exception handling**: `_available_models_for` in
  `novel_orchestration_service.py` now raises `ProviderConfigError` when
  `provider.available_models()` raises an exception, distinguishing exception
  failures from `[]` (free-form allowed), failing closed before manifest creation.
- **Audited fresh-full cache bypass scope**: `_try_delta_translate_chapter`
  now surfaces `fresh_full_required: bool`. Unsafe post-provider delta rejection
  (`changed_window_qa_failed`, `final_qa_failed`) sets `fresh_full_required=True`
  forcing `force_retranslate=True` on full fallback to bypass cache; benign
  pre-provider declines allow normal full cache lookup.
- Docs: `docs/HISTORY.md` records this pass; `docs/TRANSLATION.md` already
  documents the authoritative contract resolution.

### Test Evidence (all passing)

- Full backend suite: 3114 passed, 26 skipped.
- Backend E2E suite: 5 passed in 17.63s.
- Focused PR-41 suite: `test_novel_orchestration_service.py` 166 passed
  (137 stored + 11 contract + 18 real-pipeline/matrix/model/overlap tests);
  cache/scheduler suites 191 passed.
- Pyright: 0 errors, 0 warnings. Ruff: clean (`check` + `format --check`).
- Frontend Typecheck / ESLint clean; Vitest 76 files passed; production build
  compiled successfully.
- Graphify: updated (`graphify update . --no-cluster`; 13635 nodes).
- Router-layer guard: no matches. Alembic head unchanged (no migration).

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
  through `TranslationService.translate_chapter()` into `SmartSegmentStage` (honored
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
## 2026-08-19 DEBT-079D STAGE A + FE-07 STAGE B LOCAL ACCEPTANCE

Completed the hierarchy-persistence hardening and the docs-first public novel-detail redesign on branch `perf/debt-079d-public-path-hardening`. Evidence was collected at `2026-08-18T23:13:51Z` on the local Windows workspace; no production mutation, push, or merge was performed.

### Stage A Review and Acceptance

- Candidate commits: `50a743c` (`fix: make hierarchy reconciliation durable`) and the Stage B implementation commit `c61083a`.
- Root cause: the synchronous scrape wrapper performed sequential per-chapter remote object staging and manifest I/O, so the wrapper could time out even when chapter reconciliation had no failed chapters. The fix uses native storage copy semantics and preserves immutable raw/translation generations, durable activity state, and atomic publication.
- Representative persisted records were re-run twice each with zero failed chapters: Syosetu `n2056dn` (148 chapters; `1章　8歳`, `2章　12歳`, `閑話`, `3章　14歳`), Novel18 `n3266mn` (25 flat chapters; unpublished), and Kakuyomu `16817330655991571532` (88 chapters; `第一部　天国篇`, `第二部　世界樹篇`, `第三部　地獄篇`). Raw hashes, translated IDs, glossary hashes, active generation pointers, and section order remained unchanged.
- Public probes returned 200 for the published Syosetu and Kakuyomu records and 404 for unpublished Novel18. No provider calls were made during acceptance.

### Stage B Design and Implementation Evidence

- Canonical docs updated: `docs/DESIGN.md`, `docs/design/public/novel-detail.md`, and `docs/WORK.md`. The page keeps Overview/Chapters/Reviews; Recommendations are deferred because there is no bounded related-novels public contract.
- The implementation adds a reading-first hero, truthful persisted metadata, deterministic bookplate fallback, semantic URL tabs, real section grouping and source titles, honest availability labels, First unread/Latest anchors, closed request disclosure, quiet report link, language-aware taxonomy text, and guest/personalized CTA states. No fake popularity metrics, author routes, cover artwork, client catalog download, or new backend contract was added.
- Validation: `frontend` typecheck and ESLint passed; `npx vitest run --reporter=verbose --no-file-parallelism --maxWorkers=1` passed 77 files / 856 tests; `npm run build` passed and generated 51 static pages; `graphify update . --no-cluster` completed with the known four zero-node configuration-file warning; `git diff --check`, router import guard, and AGENTS heading guard passed.
- Local browser acceptance used the production frontend with same-origin `/api` rewrite and a combined local FastAPI app. At 1440, 390, and 320 CSS pixels, the page had no horizontal overflow, one H1, three semantic tabs, and no Recommendations text. Screenshots were captured under `output/playwright/`. The persisted local record had 0 translated of 148 chapters, so the page correctly showed unavailable chapter states rather than inventing a Start Reading target; the Novel18 route correctly rendered not found.

### Remaining Scope

Authenticated saved-progress CTA behavior is covered by deterministic frontend tests but was not exercised with credentials. Native screen-reader, forced-colors, hosted, and physical-device acceptance remain outside this local evidence record.
## 2026-08-19 LIVE CONTRIBUTIONS, RANKINGS & CURRENT PUBLIC ROUTES

Implemented the approved live contributor and ranking contracts while preserving
the current public route set. Authenticated users can register one encrypted
Gemini contributor credential, validate it immediately, pause/resume/replace or
delete it, and inspect masked usage accounting. Contributor translation is
provider-isolated, quota-reserved, and recorded in a sanitized ledger with
retention maintenance. Public rankings now use distinct authenticated and
signed-anonymous novel-detail viewers for Daily, Weekly, and Monthly windows;
Trending uses Weekly, and no All Time or V2 surface remains.

Removed the obsolete `/contribute` route and design brief. `/request-novel`
remains absent; `/account/contributions` is the sole contribution surface.
Active architecture, configuration, operations, translation, design, legal,
and public page briefs were refreshed, including the first-party anonymous
viewer-token privacy contract.

Evidence includes focused contributor, ranking, analytics, translation-pipeline,
frontend API, route, and honesty tests. The local migration reached the new
revision but requires a migration role with schema DDL permission in the
configured database before it can be accepted as applied.

## 2026-08-20 PUBLIC RANKING PERFORMANCE HARDENING

The ranking path now performs one distinct-viewer aggregation joined to the
published projection, uses composite analytics indexes for authenticated and
anonymous viewer identities, and avoids per-result storage-backed summary
enrichment. Successful non-empty responses use a bounded process-local TTL/LRU
cache with observable hit, miss, and entry metrics; disabled and no-data states
remain explicit and uncached. Migration `c8d2e4f6a1b3` was applied by the
Compose migration service and verified as the live database head with both
ranking indexes present.

Focused ranking, metrics, public-router, and catalog-projection tests passed
with `157 passed`. Production-volume PostgreSQL query plans, seeded ranking
latency, and cross-replica cache behavior remain open acceptance work.

## 2026-08-20 PUBLIC READINESS, PROJECTION CACHE & ANALYTICS PATH HARDENING

Phase 4 made public readiness bounded and stable: readiness results use the
configured short TTL with single-flight refresh, public storage checks are
non-mutating, and full storage write/read/delete plus S3 usage diagnostics
remain owner-only or scheduled. Fresh backend/reader images passed Caddy
readiness with the protected one-second probe setting and no temporary
two-second override.

Safe catalog pages, novel summaries, and chapter metadata now use a bounded
process-local TTL/LRU projection cache with version-aware keys and
publish/reconciliation/takedown invalidation. Public/server analytics events
are sanitized before admission to a bounded asynchronous writer; queue drops
and worker failures are explicit metrics, and raw IPs/prompts/authorization
headers never cross the queue.

Focused Phase 4 source tests passed, including health single-flight,
analytics backpressure, projection-cache copy/invalidation, public routes,
rankings, and metrics. Production percentile readiness, slow-writer loss,
populated ranking load, and multi-reader/shared-cache economics remain open.
## 2026-08-20 PUBLIC READER PROJECTION FIXTURE & POLICY REPAIR

Closed the Phase 1 public-reader availability fixture gap recorded as F-32.
The fixture now seeds the published `Novel`/`Chapter` projection through
`CatalogService`, and the full focused availability suite passes (`22 tests`).
Projection-first reads preserve the existing per-novel unavailable policy via
`Novel.public_reader_unavailable_policy` and migration `e5f7a9c1d3b2`, without
restoring request-time object-storage fallback. Catalog, public-router, Ruff,
Pyright, Graphify, migration smoke, and local Caddy route checks passed.
