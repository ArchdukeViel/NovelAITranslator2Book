---
title: Translation and Glossary
document_role: normative
authority: canonical
scope: translation quality prompts glossary cache identity lineage quotas and bounded provider execution
audience:
  - agents
  - developers
  - operators
update_triggers:
  - prompt or quality-policy changes
  - glossary or lineage changes
  - provider quota or retry-contract changes
owned_concerns:
  - translation-quality-and-lineage
---
# Translation and Glossary

This document owns translation quality, prompt and glossary lifecycle, cache identity, artifact lineage, provider bounds, and quota semantics. It does not own deployment, storage ownership, operational execution, or dated capacity results.

Current state: translation output is lineage-bound to immutable source artifacts, prompt and glossary identity, QA policy, and bounded provider execution; rejected attempts cannot become accepted cache entries.

Related contracts: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`STORAGE.md`](STORAGE.md), [`CONFIGURATION.md`](CONFIGURATION.md), and [`OPERATIONS.md`](OPERATIONS.md).

Maintenance: version any output-shaping or lineage-affecting contract, invalidate affected cache identity, and record execution outcomes in [`EVIDENCE.md`](EVIDENCE.md).

Canonical translation quality, prompt, glossary, and cache identity contract.

## Pipeline

Source chapters become deterministic paragraphs and temporary chunks. Prompt
assembly injects approved glossary terms and bounded context. Provider output is
parsed, checked by deterministic QA, post-processed, and saved as a versioned
translated chapter. Failed chapters do not erase successful siblings.

Resume reconciliation is artifact-first: when an immutable translated artifact
passes the current lineage contract, a retry repairs the PostgreSQL chapter
state to `complete` and clears any stale `translation_error` before reporting a
skip. A `complete` database state alone is never treated as proof of a valid
artifact.

## JP-EN Quality Rules

JP-EN policy applies when source is `ja|japanese` and target is `en|english`.
Policy identity is `jp_en_quality_v3`; the translation prompt template is
`v4` and metadata prompts are `metadata-literal-v4`. Changing output-shaping
instructions requires a version bump and cache invalidation.

Prompts must:

1. Preserve facts; never omit, summarize, censor, soften, or add information.
2. Do not invent omitted subjects, objects, pronouns, number, gender,
   relationships, motives, or dialogue attribution. Add an English grammatical
   subject only when context supports it; otherwise use neutral restructuring.
3. Use approved glossary translations exactly and preserve source-order names.
4. Preserve tone, register, narrator voice, paragraph order, and scene order.
5. Prefer natural publication-quality English over awkward literalness while
   preserving ambiguity when context cannot resolve it.
6. Preserve notes and structural boundaries, including fragments, ellipses,
   punctuation, counters, titles, kinship terms, embedded writing, and
   wordplay; do not introduce markup needlessly.

Honorific mode is one of `contextual`, `retain`, `translate`, or `omit`; the
default is `contextual`. Contextual handling preserves meaningful personal-name
honorifics and localizes established rank, profession, royal, kinship, and
social-role terms using the glossary. It never invents a relationship.
Dialogue and narration remain distinct.

## Glossary Lifecycle

PostgreSQL is the canonical glossary store. The R2 storage facade exposes a
small runtime-shaped projection for orchestration, but it never writes a
glossary object or maintains a second file-backed glossary. Approved DB entries
are translation truth. Suggested/candidate terms never become public or
prompt-active without approval.

Required states:

- DB entries: candidate, recommended, approved, rejected, and deprecated;
- runtime projection: pending, approved, ignored, or translated;
- novel glossary: lifecycle status used by onboarding/translation gates.

Rules:

- Glossary injection happens once per prompt; do not duplicate full blocks.
- Conflicts keep approved term and may report bounded review metadata.
- Revision/hash changes participate in translation/cache invalidation.
- Before body translation, incremental discovery inspects each selected chapter
  in bounded batches. Approved/translated entries are immutable truth; only
  structurally validated, high-confidence proposals at the configured
  `TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD` may activate immediately.
  Ambiguous or low-confidence proposals remain pending and are excluded from
  body prompts until reviewed. Discovery state is keyed by source hash, model,
  and prompt version so resumed runs skip unchanged chapters.
- Pending glossary translations use structured ID-based batches of
  `TRANSLATION_GLOSSARY_BATCH_SIZE` terms. A malformed batch retries on the
  same model and never falls back to one request per term or another model.
- Provider-level invalid-JSON responses follow the same bounded retry path as
  malformed response text. If discovery still cannot produce valid JSON, the
  discovery result is deferred: no unvalidated term is activated, and body
  translation may continue only when the caller's glossary-gate policy allows
  it. Provider rate/quota signals are classified before generic token or
  maximum markers so rate-limit failures are not mislabeled as context errors.
- Public annotations include only explicitly public-visible approved entries.
- Diagnostics and review workflows never expose private notes or credentials.

## Gemini Request Budget

The production Gemini contract is exact model `gemini-3.5-flash-lite` with no
alternate model/provider fallback. All request purposes share hard limits of
15 RPM, 250,000 TPM, and 500 RPD. The controller reserves conservative token
estimates before a call, reconciles actual usage afterward, persists rolling
minute/day state, honors provider `Retry-After`, and records sanitized purpose,
model, estimates, actual tokens, retry, chapter/chunk, cache, and outcome
metadata. Cache hits are recorded but do not consume provider quota.

The dry-run estimator makes zero provider calls. It reports known chapters,
characters, chunks, metadata/title batches, cached body chunks, known glossary
batches, an upper estimate for undiscovered glossary output, minimum provider
requests, configured retry reserve, selective QA requests, token estimates,
RPD feasibility, and the RPM-only wall-clock lower bound. Unknown glossary
terms and actual provider usage remain explicitly marked as estimates.

### Unified credential registry and contributor pooling

Owner-scoped translation resolves the explicitly imported and validated owner
row for `PROVIDER_GEMINI_API_KEY`; the environment key is never imported at
startup. Contributor-scoped translation is opt-in metadata on a durable
activity and selects only active, successfully validated Gemini rows from the
unified `provider_credentials` registry where
`contributor_pool_eligible=true`; an empty pool fails closed and never falls
back to an owner row. Each selected credential has its own Redis-backed
RPM/TPM/RPD and in-flight reservation state. Selection updates `last_used_at`
under a short row lock, and the per-request audit identity is passed locally
so parallel chunks cannot associate a request with another credential owner.

Credential replacement is race-safe: a validation result cannot activate a
different key that was submitted while the provider call was running. Provider
validation is rate-limited per authenticated user, and validation messages are
bounded with the submitted key redacted. The unified provider usage ledger
contains accounting and routing metadata for owner and contributor modes only;
it never stores prompts, raw keys, authorization headers, or provider
responses. Owner rows remain owner-job-only unless an owner explicitly shares
pool eligibility; user rows remain ineligible for owner-only work.

### Gemini response-schema compatibility

Gemini structured-output requests use the provider boundary rather than passing
the repository's full JSON Schema vocabulary directly to the SDK. Before a
request, the provider recursively removes `additionalProperties`, which is not
accepted by Gemini response schemas, without mutating the caller's schema.
This keeps glossary discovery and other structured requests valid while leaving
the repository-side parser and validation contract unchanged. The behavior is
covered by provider unit tests and a live NCode chapter translation smoke that
passed deterministic QA and persisted the translated artifact in R2.

## Optional Review Metadata

Structured responses may include `uncertainties`, `glossary_conflicts`, and
`style_notes`. Fields remain optional, parser-compatible, bounded, and excluded
from public chapter text.

## Cache Identity

Cache identity includes source/target language, provider/model, style and
consistency settings, glossary revision/hash, prompt template version, and JP-EN
policy version. Never reuse cache across changed output-shaping inputs.

## Cache Acceptance by Attempt

Cache eligibility is locked to the exact QA-accepted attempt. A `CacheEntry`
carries `attempt_number`, `translation_run_id`, `output_hash`, and
`cache_key`. `make_cache_key` includes provider key, model id, prompt template
version, and the canonical glossary hash so provider / model / prompt /
glossary changes produce different keys.

`CacheFlushStage` rejects any chunk whose status is in the rejection set
`needs_retry | needs_review | qa_failed`; pending entries for such chunks are
dropped (or permanently invalidated) before any cache write. For accepted
chunks the pending entry survives the same dedupe-by-key step. `status` is
immutable per attempt; a model switch produces a new key and a model-A
attempt never collides with model-B. Rejected attempts persist an evidence
trail; only accepted outputs land in the cache.

## Content-Addressed Translation Artifacts

Translation writes create immutable gzip-compressed JSON objects at
`novels/<novel_id>/translations/<chapter_id>/<translation_hash>.json.gz`.
The hash is computed from deterministic uncompressed logical bytes and includes
the source hash, effective provider/model, prompt version, glossary hash, QA
contract, and output-shaping contract. PostgreSQL stores the active object key,
version lineage, and edit history. There is no mutable translation overlay or
active pointer object in R2.

Raw chapters and media use the same immutable-reference rule. A retranslation,
manual edit, or QA retry writes one new translation object and changes one
PostgreSQL reference; raw chapter bytes are never rewritten. A source change
invalidates only translations whose source/structure/image contract changed.
Readers load the active key from PostgreSQL and perform an exact R2 read.

## Runtime Resource Boundary

PostgreSQL is the source of truth for compact catalog fields, scalar chapter
state, hashes, active artifact references, queue leases, and bounded progress
projections. R2 is the source of truth for immutable raw, translated, and media
artifacts. Routine ORM reads must defer history/version/media JSON unless the
caller explicitly needs it, and a translation invocation may reuse metadata,
approved glossary data, and raw bundles only for that invocation.

The worker audit found that synchronous database/storage calls still occur
inside concurrent async chapter tasks. Increasing concurrency is therefore not
a reliable throughput fix: measure provider wait, database work, R2 operations,
and event-loop blocking separately before raising limits. Full-queue runs are
not reader-capacity tests; use a bounded per-source sample first, then staged
reader load with CDN/cache and Supabase egress evidence.

## Provider Identity — Single Resolution Point

One authoritative provider/model contract per translation run, resolved in
`NovelOrchestrationService._resolve_effective_provider_contract` before the
run manifest, the resume gate, delta retranslation, pipeline execution, and
stored lineage are created. Precedence is strict:

1. Explicit caller values (`provider_key` / `provider_model`);
2. the workflow profile for the step (`body_translation` / `polish` — novel
   profiles, then global step configs, then endpoint profiles, already merged
   by `_resolve_workflow_step_config` / `resolve_step_llm_config`);
3. the global preferred provider / model.

The result is never `None`: a translation version must never record a missing
provider identity while the pipeline silently executes a different one.
Configuration errors fail closed at resolution time — Gemini without a
configured API key and `dummy` outside `ENV=test` raise the provider
configuration error before any contract is created. Non-profile steps
(metadata translation, glossary, crawler) resolve without the profile layer
through the same guards.

## Run Manifest and Translation Lineage

Each translation run produces a `TranslationRunManifest` linking:

- `translation_run_id` (stable across stages of one run);
- `raw_generation_id` (the activated generation the run fed on; **provenance only** — a new generation with identical raw content/structure/image hashes can reuse the prior translation without invalidation);
- canonical glossary hash (a SHA-256 of normalized glossary entries);
- `prompt_template_version` resolved from `novelai.prompts.PROMPT_TEMPLATE_VERSION`;
- `qa_policy_fingerprint` (mode, deterministic-QA version, LLM grader model,
  minimum score, retry budget, structured-output policy version);
- `provider_key`, `provider_model`, `source_language`, `target_language`;
- finalized counts (`expected_count`, `completed_count`, `skipped_count`,
  `review_count`, `failed_count`) and source-order `chapter_ids`.

Manifest persistence is logged but never silently swallowed so CI and
operators see when the committed manifest goes missing. Initial manifest
persistence (`status="running"`) occurs before chapter translation work;
final manifest update runs after chapter execution and records finalized counts.

### Production Reuse Gate & Delta Retranslation Contract

Before returning `already_complete` or `already_translated`, the production
resume path builds the **current effective translation contract** and calls
`is_translation_valid()` with it. The contract includes:

- `source_text_hash` (current raw text hash)
- `active_glossary_hash` (current glossary hash)
- `prompt_version` (current prompt template version)
- `provider_key`, `provider_model` (current provider/model)
- `active_raw_generation_id` (current active generation)
- `source_structure_hash` (current raw structure hash)
- `source_image_manifest_hash` (current image manifest hash)
- `qa_policy_fingerprint` (current QA policy)
- `source_language`, `target_language` (current languages; missing stored
  language fails closed)
- `style_preset`, `consistency_mode`, `json_output`, `honorific_policy`
  (current output-shaping settings — any change alters generated text and
  forces retranslation; honorific policy compares normalized identity, so
  case/whitespace spelling variation never causes spurious retranslation)

When delta retranslation is enabled (`TRANSLATION_DELTA_RETRANSLATION_ENABLED=True`,
the default), the delta execution path (`_try_delta_translate_chapter`) enforces the
identical output-shaping and generation-provenance contract before declaring a chapter
`whole_chapter_unchanged`. If the stored translation version differs in style preset,
consistency mode, JSON output, honorific policy, or lacks raw generation provenance,
the delta path bails with `fallback_reason="output_contract_changed"` and forces full
retranslation.

`is_translation_valid` **fails closed** when a required input has no stored
value on the existing translation version. A DB `COMPLETE` state is evidence
of previous completion, **not** of current validity — a stale source text,
glossary, prompt, QA policy, provider/model, target language, structure,
image manifest, or output-shaping setting forces retranslation. The previous
version is retained in the per-chapter overlay history. `raw_generation_id`
is **provenance**: a stored id must exist when a generation is active
(missing lineage is stale / needs-backfill), but the stored id is never
compared for equality with the current active generation id — an otherwise
identical translation stays reusable across generation activations (hashes
and the effective contract are the validity gate).

### Plain-Output Delta Windows (strict marker contract)

When a delta changed window runs with `json_output=False`, the window parser
(`_structured_map_from_result`) first attempts the structured `paragraph_map`,
then falls back to a **strict `[P <id>]` marker parser**
(`_strict_marker_paragraph_map`). The grammar mirrors the production prompt
contract: actual marker occurrences must exactly match the expected ordered
occurrence sequence matching the chapter's absolute paragraph ids stamped into
the window prompt via the `paragraph_ids` pipeline option; `[CHAPTER <id>]` may
appear only once, before the first paragraph, and must match the window's
chapter id. A blank body is valid — a paragraph the provider could not translate
keeps its marker with the empty body preserved in order. Any missing,
unexpected/excess, or reordered marker occurrence — or preamble, an unknown `[CHAPTER ...]` marker, or
contradictory raw outputs — is ambiguity, and the delta path fails closed to
a full translation (`fallback_reason="changed_window_qa_failed"`).

**Occurrence-aware QA accounting.** When `SmartSegmentStage` splits an oversized
source paragraph across sentence boundaries and packs multiple split pieces into
a single `TranslationChunk` (all sharing the original `paragraph_id`), `TranslationQAStage`
compares expected vs actual as ordered occurrence sequences. Expected repeated IDs
pass QA when the output contains the exact expected occurrence count in order.
Missing occurrences, excess occurrences (`paragraph_duplicate`), unexpected IDs,
or order mismatches fail closed.

**Multi-chunk windows (piecewise apply).** A changed window may span several
pipeline chunks — an oversized source paragraph split by
`split_oversized_paragraph`, or a window exceeding one chunk budget. When
`len(result.translation_chunks) > 1`, `_piecewise_map_from_result` runs first:
raw provider outputs (`metadata["raw_provider_translations"]`, aligned 1:1
with chunks) are parsed **per chunk** against that chunk's own
`paragraph_ids` — marker grammar first, then the structured `paragraph_map` —
and pieces of the same source paragraph are merged back in chunk order with
the `"\n\n"` separator the full path uses. Because `split_oversized_paragraph`
keeps the absolute `paragraph_id` on every piece, repeated ids are matched
positionally (`expected_counts` in `_strict_marker_paragraph_map`) instead of
being rejected as duplicates; a repeat beyond the expected count still fails
closed. Multi-chunk windows with no valid per-chunk parse fail closed to a
full translation like any other ambiguity.

**Context overlap is not missing output.** `[CONTEXT OVERLAP]` blocks carry
prior-chunk context the provider is not asked to translate; the QA content
strip removes the whole block before ratio checks, so overlap content never
inflates the source length or trips `translation_too_short`.

## Chapter Selection

A selection string (`"all"`, `"1-3;8"`, `"2"`, `"kakuyomu:1681809307..."`)
resolves through `resolve_chapter_selection` against the complete current
chapter index. Numeric selections resolve to the chapter sitting at the
given sequence position, then run all downstream operations against the
stable `chapter_id`. Kakuyomu percent-encoded ids (`kakuyomu:<episode>`) and
Syosetu numeric ids share one pipeline — there is no `int(chapter["id"])`
or `chapter_id.isdigit()` branch in the request flow.

## Source-Order Convergence

Source state persists `ordered_episode_ids` matching the complete current
index plus per-episode `source_availability`, `first_seen_at`,
`last_seen_at`, `missing_since`, `content_hash`, `structure_hash` where
known. Episodes absent from the index become
`source_availability == "missing_from_current_index"` (raw + translated
history is retained); on reappearance `missing_since` is cleared. Repeated
crawls after reconciliation produce no reorder / removal delta. Reorder
signals propagate to reader / export ordering without retranslation.

Optional source sections are metadata/display context attached to the existing
chapter index. Section discovery, ordinal changes, section moves, and section
title changes do not change raw chapter content, body translation identity,
glossary hashes, or body-cache keys. If translated section labels are enabled,
the exact `section_title` is sent through the existing metadata-title batching
and cache path as `translated_section_title`; it is never included in body
translation prompts and does not cause a novel-wide body retranslation.

## QA

Deterministic checks cover empty or source-identical text, suspicious length,
unresolved placeholders, provider refusals/error text, paragraph mapping, and
glossary consistency. Optional LLM QA is selective and bounded by risk/sample
policy, advisory by default, and cannot silently replace deterministic gates or
auto-publish findings.

## Change Checklist

- Update prompt/policy version when output can change.
- Update cache identity and invalidation tests.
- Preserve approved glossary terms and structural mapping.
- Keep review metadata optional and private.
- Update focused prompt snapshots intentionally.
- Run prompt, translation, glossary, and integration regression tests.
- Re-hash the canonical glossary; new hash invalidates dependents.
- Bump `qa_policy_fingerprint` and `prompt_template_version` together with
  any output-shaping change.

Deferred semantic-cache and broader advisory-QA work lives in [`STATUS.md`](STATUS.md).

## Contributor Credential Selection and Usage Accounting

Contributor-backed translation is an explicitly marked execution mode. It
never falls through to owner preferences and never changes the global provider
contract. The worker selects only an active, successfully validated Gemini
credential, decrypts it for the provider call, and keeps the raw key out of
activity metadata, cache keys, prompts, logs, and responses. Owner-only jobs
remain owner-scoped even when contributor credentials exist.

The pipeline propagates `credential_id`, `credential_owner_user_id`,
`requesting_user_id`, `credential_scope`, and `contribution_mode` as safe
metadata. Each provider attempt reserves the credential's RPM/TPM/RPD capacity
before calling Gemini. The contributor usage ledger records provider/model,
request/job/activity ids, status, actual or estimated token accounting, cost,
and timestamps only. Invalid-key and quota/rate failures pause the credential
and leave a truthful failed ledger state; successful validation activates the
credential immediately. Rejected or failed credentials are never added to the
eligible contributor pool.

## Translation activity and provider bounds

Owner translation requests are enqueue operations: the API returns `202` with
an activity id and the worker performs the staged translation under a durable
lease. An optional `Idempotency-Key` makes client retries safe; omitted keys
are derived from non-secret operation parameters. The activity id is propagated
as both `job_id` and `activity_id`, and progress/status is polled from the
activity API.

The production queue is the `activity_records` database table, not a full-file
JSON rewrite. Claims use an index-backed atomic `UPDATE ... RETURNING` with the
oldest pending row, expired leases are recovered, retries and metadata are
bounded, and queue age/claim/heartbeat/update timings are observable. Lease
heartbeats update only the lease timestamps and normally run every 15-30
seconds; an explicitly shortened test/local lease uses one-third of its lease
duration so it cannot expire before renewal. Empty-queue polling backs off from
5 to 30 seconds. The legacy queue file may be imported during migration but is
not the normal control plane.

The resource-efficiency audit now uses a bounded per-job cache: the selected
run loads novel metadata and the approved glossary once, and selected raw
chapter bundles are reused across glossary discovery, preflight, and the
chapter pipeline. The cache is scoped to one translation invocation and is
discarded at the end; there is no cross-job cache or stale-data risk. The
worker also reuses the row returned by the atomic activity claim, routine
catalog reconciliation defers the large novel metadata-history JSON, and
translation/catalog state reads defer chapter media, translation-version, and
edit-history JSON. Write paths still load a deferred value only when they must
append immutable history records.

Gemini admission reserves RPM, TPM, RPD, and in-flight capacity globally for
the owner key or per contributor credential. Each chunk has a configured
provider deadline and bounded exponential retry delay. Provider clients are
reused only inside their credential-isolated provider instance; explicit
contributor keys are never placed in owner preferences or shared clients.
Sanitized usage records and runtime metrics capture provider wait, execution,
retry, quota-reservation, and usage-ledger write duration without prompts,
keys, authorization headers, or response secrets.

The `GEMINI_*` and `CONTRIBUTOR_*` limits are local admission ceilings and do
not prove that every API key has an independent upstream quota. Google documents
Gemini limits as varying by model and usage tier and generally applying at the
project level; operators must verify the active account/project limits in
[Google AI Studio](https://ai.google.dev/gemini-api/docs/rate-limits) before
production-volume work. TPD is model-dependent and is not a separate setting
in this repository; do not infer a token-per-day allowance from RPD or TPM.

Accepted translation cache entries are disposable runtime data. They may be
evicted or lost without changing canonical translation artifacts; PostgreSQL
lineage and R2 immutable objects remain the recovery source. Cache maintenance
must never upload cache entries to R2 or use them as active references.

## Async persistence and contributor capacity checkpoint - 2026-08-24

The translation coordinator now uses a bounded `TranslationPersistencePort`
for blocking persistence/checkpoint/R2 operations. Only immutable scalar/DTO
values cross the boundary; sessions, ORM instances, transactions, provider
responses, prompts, and secrets do not. Progress events and chunk states may
be coalesced through one bounded batch; terminal lineage and active-reference
work remains critical. Shutdown drains within the configured deadline and
releases executor capacity.

Contributor leases reserve both a conservative shared Gemini project budget and
the selected credential budget. Same-project keys therefore do not multiply
RPM/TPM/RPD/in-flight capacity. Selection is limited to active, valid,
consented, contributor-pool-eligible rows, while owner-job rows remain isolated.
Reservation rejection, provider outcome, cancellation, timeout, and expiry
reconcile both controllers; the usage ledger stores bounded attribution only.

The local checkpoint measurement found a copy-shaped disposable envelope and a
smaller reference-only candidate, but no compaction threshold or migration
approval exists. The evidence-backed decision is to retain the current
envelope and restore contract. Live provider/R2 canary evidence remains
operator-deferred; no contributor credential was activated in this audit.
